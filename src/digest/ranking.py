"""Validation of the model-written ranking against the candidate list."""

from __future__ import annotations

from typing import Any

from digest.models import Candidate

DAILY_SECTIONS = {"A", "B", "computing"}
WEEKLY_SECTIONS = {"weekly"}
KINDS = {"T", "E", "TE"}  # theory, experiment, both


def sections_for(mode: str) -> set[str]:
    return WEEKLY_SECTIONS if mode == "weekly" else DAILY_SECTIONS


def validate_ranking(ranking: Any, candidates: list[Candidate], *, mode: str) -> list[str]:
    """Return a list of human-readable violations; empty means the ranking is usable."""
    if not isinstance(ranking, dict):
        return ["ranking is not an object"]
    items = ranking.get("items")
    if not isinstance(items, list):
        return ["ranking has no items list"]

    errors: list[str] = []
    if ranking.get("mode") != mode:
        errors.append(f"mode {ranking.get('mode')!r} does not match run mode {mode!r}")

    allowed = sections_for(mode)
    known = {c.id for c in candidates}
    covered: set[str] = set()
    for n, item in enumerate(items):
        if not isinstance(item, dict):
            errors.append(f"item {n} is not an object")
            continue
        item_id = item.get("id")
        if item_id not in known:
            errors.append(f"item {n}: unknown id {item_id}")
        else:
            covered.add(item_id)
        section = item.get("section")
        if section not in allowed:
            errors.append(f"item {n}: section {section} not in {sorted(allowed)}")
        score = item.get("score")
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
            errors.append(f"item {n}: score {score} not an integer 0-100")
        if not isinstance(item.get("why"), str) or not item["why"].strip():
            errors.append(f"item {n}: why is missing")
        kind = item.get("kind")
        if kind is None:
            errors.append(f"item {n}: kind is missing")
        elif kind not in KINDS:
            errors.append(f"item {n}: kind {kind} not in {sorted(KINDS)}")

    missing = known - covered
    if missing:
        errors.append(f"missing {len(missing)} candidate(s): {', '.join(sorted(missing)[:10])}")
    return errors
