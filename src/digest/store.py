"""Digest files: merge a run's candidates with the model ranking and read them back."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from digest.models import Candidate
from digest.ranking import validate_ranking


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
        detail = "; ".join(errors[:5])
        status["error"] = f"ranking invalid: {detail}" if "error" not in status else f"{status['error']} | ranking invalid: {detail}"

    items: list[dict[str, Any]] = []
    for c in candidates:
        entry = c.to_json()
        r = by_id.get(c.id)
        entry["section"] = r["section"] if r else c.pool
        entry["score"] = r["score"] if r else None
        entry["why"] = r["why"].strip() if r else None
        items.append(entry)
    items.sort(key=lambda e: (-(e["score"] if e["score"] is not None else -1), e["submitted"]), reverse=False)

    return {
        "run": run.isoformat(),
        "mode": mode,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ranked": ranked,
        "status": status,
        "items": items,
    }


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
