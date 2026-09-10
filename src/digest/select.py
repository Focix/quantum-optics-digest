"""Candidate selection: window filter, dedupe, pool precedence, tags, cap."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from digest.models import Candidate, Paper

# Pools are processed in this order; a paper already placed stays in its first pool.
POOL_ORDER = ["A", "B"]

_COMPUTING_RE = re.compile(
    r"surface code|error[- ]correct|logical qubit|quantum processor|gate fidelit|"
    r"two-qubit gate|randomized benchmarking|quantum error|fault[- ]tolera|"
    r"quantum volume|crosstalk|calibration|readout fidelity|syndrome",
    re.IGNORECASE,
)


@dataclass
class Selection:
    candidates: list[Candidate]
    dropped_old: int = 0
    dropped_seen: int = 0
    overflow: int = 0
    per_pool: dict[str, int] = field(default_factory=dict)


def tags_for(pool: str, paper: Paper) -> list[str]:
    tags: list[str] = []
    if pool == "A":
        tags.append("platform:sc")
        if _COMPUTING_RE.search(f"{paper.title} {paper.abstract}"):
            tags.append("computing")
    return tags


def select_candidates(
    pools: dict[str, list[Paper]],
    *,
    seen: dict[str, str],
    today: date,
    window_days: int,
    cap: int,
) -> Selection:
    cutoff = today - timedelta(days=window_days)
    result = Selection(candidates=[])
    placed: set[str] = set()
    for pool in [p for p in POOL_ORDER if p in pools] + [p for p in pools if p not in POOL_ORDER]:
        for paper in pools[pool]:
            if paper.id in placed:
                continue
            if paper.submitted < cutoff:
                result.dropped_old += 1
                continue
            if paper.id in seen:
                result.dropped_seen += 1
                continue
            placed.add(paper.id)
            result.candidates.append(Candidate.from_paper(paper, pool, tags_for(pool, paper)))

    if len(result.candidates) > cap:
        result.candidates.sort(key=lambda c: c.submitted, reverse=True)
        result.overflow = len(result.candidates) - cap
        result.candidates = result.candidates[:cap]

    # pool order, then newest first
    result.candidates.sort(key=lambda c: (c.submitted, c.id), reverse=True)
    result.candidates.sort(key=lambda c: POOL_ORDER.index(c.pool) if c.pool in POOL_ORDER else 99)
    result.per_pool = {p: sum(1 for c in result.candidates if c.pool == p) for p in pools}
    return result


def mark_seen(
    seen: dict[str, str], candidates: list[Candidate], *, today: date, keep_days: int
) -> dict[str, str]:
    cutoff = today - timedelta(days=keep_days)
    kept = {k: v for k, v in seen.items() if date.fromisoformat(v) >= cutoff}
    for c in candidates:
        kept.setdefault(c.id, today.isoformat())
    return kept
