import json
from datetime import date
from pathlib import Path

import pytest

from digest.pipeline import Paths, fetch_daily, fetch_weekly, load_config, publish

FIXTURE = (Path(__file__).parent / "fixtures" / "arxiv_transmon.xml").read_text()
ROOT = Path(__file__).parent.parent
TODAY = date(2026, 9, 10)


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    p = Paths(root=tmp_path)
    (tmp_path / "config").mkdir()
    for name in ("queries.toml", "settings.toml"):
        (tmp_path / "config" / name).write_text((ROOT / "config" / name).read_text())
    return p


def test_fetch_daily_writes_candidates_status_and_next_seen(paths: Paths) -> None:
    urls: list[str] = []

    def fetch_xml(url: str) -> str:
        urls.append(url)
        return FIXTURE

    status = fetch_daily(load_config(paths), paths, fetch_xml=fetch_xml, today=TODAY)

    assert len(urls) == 3
    candidates = json.loads(paths.candidates.read_text())
    # the same two papers come back for every pool; A wins, so B and C add nothing; newest id first
    assert [(c["id"], c["pool"]) for c in candidates] == [("2609.09426", "A"), ("2609.08348", "A")]
    assert candidates[0]["tags"] == ["platform:sc"]
    assert status["pools"] == {"A": "ok", "B": "ok", "C": "ok"}
    assert status["counts"] == {"A": 2, "B": 0, "C": 0}
    assert status["s2"] == "disabled"
    assert "error" not in status
    assert json.loads(paths.status.read_text()) == status
    assert set(json.loads(paths.seen_next.read_text())) == {"2609.08348", "2609.09426"}
    assert not paths.seen.exists()  # state only advances on publish


def test_fetch_daily_records_pool_failure_and_keeps_going(paths: Paths) -> None:
    def fetch_xml(url: str) -> str:
        if "hep-ex" in url:
            raise RuntimeError("503 Service Unavailable")
        return FIXTURE

    status = fetch_daily(load_config(paths), paths, fetch_xml=fetch_xml, today=TODAY)

    assert status["pools"]["C"].startswith("error: 503")
    assert "pool C" in status["error"]
    assert len(json.loads(paths.candidates.read_text())) == 2


def test_publish_writes_digest_promotes_seen_and_renders(paths: Paths) -> None:
    fetch_daily(load_config(paths), paths, fetch_xml=lambda url: FIXTURE, today=TODAY)
    ranking = {"run": "2026-09-10", "mode": "daily", "items": [
        {"id": "2609.09426", "section": "computing", "score": 30, "why": "Computes E_J for amorphous barriers."},
        {"id": "2609.08348", "section": "computing", "score": 35, "why": "Instantaneous-frame theory of parametric gates."},
    ]}
    paths.ranking.write_text(json.dumps(ranking))

    digest = publish(paths, mode="daily", today=TODAY)

    assert digest is not None
    assert digest["ranked"] is True
    assert (paths.digests / "2026-09-10.json").exists()
    assert set(json.loads(paths.seen.read_text())) == {"2609.08348", "2609.09426"}
    index = (paths.docs / "index.html").read_text()
    assert "Instantaneous-Frame Theory" in index
    assert 'class="banner"' not in index


def test_publish_with_error_renders_banner_and_leaves_state_alone(paths: Paths) -> None:
    fetch_daily(load_config(paths), paths, fetch_xml=lambda url: FIXTURE, today=TODAY)
    digest = publish(paths, mode="daily", today=TODAY, error="fetch.py exited 1")

    assert digest is None
    assert not paths.seen.exists()
    assert "fetch.py exited 1" in (paths.docs / "index.html").read_text()


def test_fetch_weekly_collects_computing_items_from_recent_digests(paths: Paths) -> None:
    paths.digests.mkdir()
    old = {"run": "2026-09-01", "mode": "daily", "ranked": True, "status": {}, "items": [
        {"id": "old", "title": "Old", "authors": [], "abstract": "", "categories": [], "submitted": "2026-09-01",
         "pool": "A", "tags": ["platform:sc"], "s2": None, "section": "computing", "score": 40, "why": "x"}]}
    recent = {"run": "2026-09-09", "mode": "daily", "ranked": True, "status": {}, "items": [
        {"id": "new", "title": "New", "authors": [], "abstract": "", "categories": [], "submitted": "2026-09-09",
         "pool": "A", "tags": ["platform:sc"], "s2": None, "section": "computing", "score": 40, "why": "x"},
        {"id": "optics", "title": "Optics", "authors": [], "abstract": "", "categories": [], "submitted": "2026-09-09",
         "pool": "A", "tags": ["platform:sc"], "s2": None, "section": "A", "score": 90, "why": "x"}]}
    for d in (old, recent):
        (paths.digests / f"{d['run']}.json").write_text(json.dumps(d))

    status = fetch_weekly(load_config(paths), paths, today=date(2026, 9, 12))

    candidates = json.loads(paths.candidates.read_text())
    assert [(c["id"], c["pool"]) for c in candidates] == [("new", "weekly")]
    assert status["counts"] == {"weekly": 1}
    assert status["s2"] == "disabled"
