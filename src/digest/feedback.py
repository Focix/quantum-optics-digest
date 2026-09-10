"""Reader feedback: 👍/👎 issues opened from the page, folded into state/feedback.json."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

FIELDS = ("id", "verdict", "section", "score", "run", "title", "link")
KEEP = 200  # newest entries kept in the file; the ranking prompt reads the last 50


def parse_issue(issue: dict[str, Any]) -> dict[str, Any] | None:
    """Turn one GitHub issue (gh --json shape) into a feedback record; None if not ours."""
    labels = {(l.get("name") if isinstance(l, dict) else str(l)) for l in issue.get("labels", [])}
    if "feedback" not in labels:
        return None
    fields: dict[str, str] = {}
    note: list[str] = []
    in_note = False
    for raw in str(issue.get("body") or "").splitlines():
        line = raw.strip()
        if in_note:
            note.append(line)
            continue
        if line.lower().startswith("note"):
            in_note = True
            after = line.split(":", 1)[1].strip() if ":" in line else ""
            if after:
                note.append(after)
            continue
        m = re.match(r"^([a-z]+):\s*(.*)$", line)
        if m and m.group(1) in FIELDS:
            fields[m.group(1)] = m.group(2).strip()
    verdict = fields.get("verdict") or ("up" if "up" in labels else "down" if "down" in labels else "")
    if verdict not in ("up", "down") or not fields.get("id"):
        return None
    score: int | None
    try:
        score = int(fields.get("score", ""))
    except ValueError:
        score = None
    return {
        "issue": issue.get("number"),
        "id": fields["id"],
        "verdict": verdict,
        "section": fields.get("section") or None,
        "score": score,
        "run": fields.get("run") or None,
        "title": fields.get("title") or str(issue.get("title") or "").lstrip("👍👎 ").split(" ", 1)[-1],
        "note": " ".join(n for n in note if n).strip() or None,
        "created": str(issue.get("createdAt") or "")[:10] or None,
    }


def merge_feedback(existing: list[dict[str, Any]], new: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """By issue number, newest issue last; a re-opened and edited issue replaces its older record."""
    by_issue = {int(r["issue"]): r for r in existing if r.get("issue") is not None}
    for r in new:
        by_issue[int(r["issue"])] = r
    rows = sorted(by_issue.values(), key=lambda r: int(r["issue"]))
    return rows[-KEEP:]


def load_feedback(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return list(data) if isinstance(data, list) else []


def save_feedback(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=1, ensure_ascii=False) + "\n")
