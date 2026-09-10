from pathlib import Path
from typing import Any

from digest.feedback import load_feedback, merge_feedback, parse_issue, save_feedback
from digest.render import Site, feedback_url


def issue(number: int, body: str, labels: list[str] | None = None, title: str = "👍 2609.00001 Some title") -> dict[str, Any]:
    return {"number": number, "title": title, "body": body, "createdAt": "2026-09-11T07:00:00Z",
            "labels": [{"name": l} for l in (labels or ["feedback", "up"])]}


BODY = "id: 2609.00001\nverdict: up\nsection: A\nscore: 42\nrun: 2026-09-10\ntitle: Some title\nlink: https://arxiv.org/abs/2609.00001\n\nNote (optional): should be higher\nreally\n"


def test_parse_issue_reads_prefilled_fields_and_note() -> None:
    rec = parse_issue(issue(7, BODY))
    assert rec == {
        "issue": 7, "id": "2609.00001", "verdict": "up", "section": "A", "score": 42, "run": "2026-09-10",
        "title": "Some title", "note": "should be higher really", "created": "2026-09-11",
    }


def test_parse_issue_ignores_foreign_issues_and_falls_back_to_labels() -> None:
    assert parse_issue(issue(1, BODY, labels=["bug"])) is None
    assert parse_issue(issue(2, "hello", labels=["feedback", "down"])) is None      # no id
    rec = parse_issue(issue(3, "id: 2609.00002\nscore: n/a\n", labels=["feedback", "down"]))
    assert rec is not None and rec["verdict"] == "down" and rec["score"] is None and rec["title"] == "Some title"


def test_merge_replaces_same_issue_and_round_trips(tmp_path: Path) -> None:
    a = parse_issue(issue(1, BODY))
    b = parse_issue(issue(2, BODY.replace("up", "down")))
    a2 = parse_issue(issue(1, BODY.replace("score: 42", "score: 43")))
    assert a and b and a2
    merged = merge_feedback([a], [b, a2])
    assert [(r["issue"], r["score"]) for r in merged] == [(1, 43), (2, 42)]
    path = tmp_path / "state" / "feedback.json"
    save_feedback(path, merged)
    assert load_feedback(path) == merged
    assert load_feedback(tmp_path / "missing.json") == []


def test_feedback_url_round_trips_through_parse_issue() -> None:
    from urllib.parse import parse_qs, urlsplit

    item = {"id": "2609.00001", "title": "Some <title> & more", "section": "B", "score": 61}
    url = feedback_url(item, "down", site=Site(repo="Focix/quantum-optics-digest"), run="2026-09-10")
    assert url is not None and url.startswith("https://github.com/Focix/quantum-optics-digest/issues/new?")
    q = parse_qs(urlsplit(url).query)
    assert q["labels"] == ["feedback,down"]
    rec = parse_issue({"number": 9, "title": q["title"][0], "body": q["body"][0], "labels": [{"name": "feedback"}, {"name": "down"}]})
    assert rec is not None
    assert (rec["id"], rec["verdict"], rec["section"], rec["score"], rec["run"], rec["title"]) == (
        "2609.00001", "down", "B", 61, "2026-09-10", "Some <title> & more")
    assert feedback_url(item, "up", site=Site()) is None
