import json
from datetime import date
from pathlib import Path

from digest.models import Candidate
from digest.store import build_digest, digest_path, load_digests


def cand(id: str, pool: str = "A") -> Candidate:
    return Candidate(id=id, title=f"T{id}", authors=["X"], abstract="a", categories=["quant-ph"], submitted=date(2026, 9, 9), pool=pool)


def test_build_digest_merges_ranking_and_orders_by_score() -> None:
    ranking = {"run": "2026-09-10", "mode": "daily", "items": [
        {"id": "1", "section": "A", "score": 40, "why": "meh", "kind": "T"},
        {"id": "2", "section": "A", "score": 90, "why": "wow", "kind": "E"},
    ]}
    digest = build_digest([cand("1"), cand("2")], ranking, status={"arxiv": "ok"}, run=date(2026, 9, 10), mode="daily")

    assert digest["run"] == "2026-09-10"
    assert digest["mode"] == "daily"
    assert digest["ranked"] is True
    assert [(i["id"], i["score"], i["why"]) for i in digest["items"]] == [("2", 90, "wow"), ("1", 40, "meh")]
    assert digest["items"][0]["section"] == "A"
    assert [i["kind"] for i in digest["items"]] == ["E", "T"]
    assert digest["items"][0]["title"] == "T2"
    assert digest["status"] == {"arxiv": "ok"}


def test_invalid_ranking_falls_back_to_unranked_with_error() -> None:
    digest = build_digest([cand("1"), cand("2", "B")], {"items": [{"id": "1"}]}, status={}, run=date(2026, 9, 10), mode="daily")

    assert digest["ranked"] is False
    assert "ranking invalid" in digest["status"]["error"]
    assert [(i["id"], i["section"], i["score"]) for i in digest["items"]] == [("1", "A", None), ("2", "B", None)]


def test_digest_path_and_load_newest_first(tmp_path: Path) -> None:
    for run, mode in [(date(2026, 9, 8), "daily"), (date(2026, 9, 12), "weekly"), (date(2026, 9, 10), "daily")]:
        p = digest_path(tmp_path, run, mode)
        p.write_text(json.dumps({"run": run.isoformat(), "mode": mode, "items": []}))
    assert digest_path(tmp_path, date(2026, 9, 12), "weekly").name == "2026-09-12-weekly.json"

    digests = load_digests(tmp_path)
    assert [(d["run"], d["mode"]) for d in digests] == [("2026-09-12", "weekly"), ("2026-09-10", "daily"), ("2026-09-08", "daily")]


def test_merge_digests_keeps_earlier_items_and_prefers_new_ranking() -> None:
    from digest.store import merge_digests

    earlier = {"run": "2026-09-10", "mode": "daily", "ranked": True, "status": {"counts": {"A": 2}},
               "items": [{"id": "1", "section": "A", "score": 80, "why": "old"}, {"id": "2", "section": "B", "score": 40, "why": "old"}]}
    later = {"run": "2026-09-10", "mode": "daily", "ranked": True, "status": {"counts": {"A": 1}},
             "items": [{"id": "3", "section": "A", "score": 90, "why": "new"}, {"id": "2", "section": "B", "score": 45, "why": "new"}]}

    merged = merge_digests(earlier, later)

    assert [(i["id"], i["why"]) for i in merged["items"]] == [("3", "new"), ("1", "old"), ("2", "new")]
    assert merged["status"]["merged"] == "1 item(s) kept from an earlier run today"
    assert merged["ranked"] is True
