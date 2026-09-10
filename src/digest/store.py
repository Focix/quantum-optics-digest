"""Digest files: merge a run's candidates with the model ranking and read them back."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from digest.models import Candidate
from digest.ranking import validate_ranking


def add_error(status: dict[str, Any], message: str) -> None:
    """Append a failure message to status["error"], keeping earlier ones."""
    status["error"] = f"{status['error']} | {message}" if status.get("error") else message


def build_digest(
    candidates: list[Candidate],
    ranking: Any,
    *,
    status: dict[str, Any],
    run: date,
    mode: str,
) -> dict[str, Any]:
    status = dict(status)
    errors = validate_ranking(ranking, candidates, mode=mode)
    ranked = not errors
    by_id: dict[str, dict[str, Any]] = {}
    if ranked:
        by_id = {item["id"]: item for item in ranking["items"]}
    else:
        add_error(status, "ranking invalid: " + "; ".join(errors[:5]))

    items: list[dict[str, Any]] = []
    for c in candidates:
        entry = c.to_json()
        r = by_id.get(c.id)
        entry["section"] = r["section"] if r else c.pool
        entry["score"] = r["score"] if r else None
        entry["why"] = r["why"].strip() if r else None
        entry["kind"] = r.get("kind") if r else None
        items.append(entry)
    # highest score first; unranked items keep the newest-first order they arrived in
    if ranked:
        items.sort(key=lambda e: -(e["score"] if e["score"] is not None else -1))

    return {
        "run": run.isoformat(),
        "mode": mode,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ranked": ranked,
        "status": status,
        "items": items,
    }


def merge_digests(earlier: dict[str, Any], later: dict[str, Any]) -> dict[str, Any]:
    """Combine two digests for the same run: the later run's items win, earlier-only items are kept."""
    later_ids = {i["id"] for i in later["items"]}
    kept = [i for i in earlier["items"] if i["id"] not in later_ids]
    merged = dict(later)
    merged["items"] = list(later["items"]) + kept
    merged["items"].sort(key=lambda e: -(e["score"] if e.get("score") is not None else -1))
    merged["ranked"] = bool(later.get("ranked", True) and earlier.get("ranked", True))
    merged["status"] = {**later.get("status", {}), "merged": f"{len(kept)} item(s) kept from an earlier run today"}
    return merged


def digest_path(directory: Path, run: date, mode: str) -> Path:
    suffix = "" if mode == "daily" else f"-{mode}"
    return directory / f"{run.isoformat()}{suffix}.json"


def write_digest(directory: Path, digest: dict[str, Any]) -> Path:
    path = digest_path(directory, date.fromisoformat(digest["run"]), digest["mode"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(digest, indent=1, ensure_ascii=False) + "\n")
    return path


def load_digests(directory: Path) -> list[dict[str, Any]]:
    digests: list[dict[str, Any]] = []
    if not directory.exists():
        return digests
    for path in directory.glob("*.json"):
        digests.append(json.loads(path.read_text()))
    digests.sort(key=lambda d: (d["run"], d["mode"]), reverse=True)
    return digests
