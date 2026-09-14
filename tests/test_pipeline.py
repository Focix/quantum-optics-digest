import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from digest.models import Paper
from digest.pipeline import (
    FetchXml,
    Paths,
    fetch_daily,
    fetch_weekly,
    load_config,
    make_arxiv_fetcher,
    publish,
)

FIXTURE = (Path(__file__).parent / "fixtures" / "arxiv_transmon.xml").read_text()
ROOT = Path(__file__).parent.parent
TODAY = date(2026, 9, 10)


@pytest.fixture
def paths(tmp_path: Path) -> Paths:
    p = Paths(root=tmp_path)
    (tmp_path / "config").mkdir()
    for name in ("queries.toml", "settings.toml"):
        (tmp_path / "config" / name).write_text((ROOT / "config" / name).read_text())
    # tests never touch the network: this disables both [citations] and [backup]
    settings = tmp_path / "config" / "settings.toml"
    settings.write_text(settings.read_text().replace("enabled = true", "enabled = false"))
    return p


def test_fetch_daily_writes_candidates_status_and_next_seen(paths: Paths) -> None:
    urls: list[str] = []

    def fetch_xml(url: str) -> str:
        urls.append(url)
        return FIXTURE

    status = fetch_daily(load_config(paths), paths, fetch_xml=fetch_xml, today=TODAY)

    assert len(urls) == 2
    candidates = json.loads(paths.candidates.read_text())
    # the same two papers come back for every pool; A wins, so B and C add nothing; newest id first
    assert [(c["id"], c["pool"]) for c in candidates] == [("2609.09426", "A"), ("2609.08348", "A")]
    assert candidates[0]["tags"] == ["platform:sc"]
    assert status["pools"] == {"A": "ok", "B": "ok"}
    assert status["counts"] == {"A": 2, "B": 0}
    assert status["citations"] == "disabled"
    assert "error" not in status
    assert json.loads(paths.status.read_text()) == status
    assert set(json.loads(paths.seen_next.read_text())) == {"2609.08348", "2609.09426"}
    assert not paths.seen.exists()  # state only advances on publish


def test_overflow_is_noted_in_status_without_error(paths: Paths) -> None:
    config = load_config(paths)
    config["run"]["cap"] = 1
    status = fetch_daily(config, paths, fetch_xml=lambda url: FIXTURE, today=TODAY)

    assert status["overflow"].startswith("1 oldest candidates dropped")
    assert "error" not in status
    assert len(json.loads(paths.candidates.read_text())) == 1


def test_fetch_daily_records_pool_failure_and_keeps_going(paths: Paths) -> None:
    def fetch_xml(url: str) -> str:
        if "physics.optics" in url:
            raise RuntimeError("503 Service Unavailable")
        return FIXTURE

    status = fetch_daily(load_config(paths), paths, fetch_xml=fetch_xml, today=TODAY)

    assert status["pools"]["B"].startswith("error: 503")
    assert "pool B" in status["error"]
    assert len(json.loads(paths.candidates.read_text())) == 2


def test_publish_writes_digest_promotes_seen_and_renders(paths: Paths) -> None:
    fetch_daily(load_config(paths), paths, fetch_xml=lambda url: FIXTURE, today=TODAY)
    ranking = {"run": "2026-09-10", "mode": "daily", "items": [
        {"id": "2609.09426", "section": "computing", "score": 30, "why": "Computes E_J for amorphous barriers.", "kind": "T"},
        {"id": "2609.08348", "section": "computing", "score": 35, "why": "Instantaneous-frame theory of parametric gates.", "kind": "T"},
    ]}
    paths.ranking.write_text(json.dumps(ranking))

    digest = publish(paths, mode="daily", today=TODAY)

    assert digest is not None
    assert digest["ranked"] is True
    assert (paths.digests / "2026-09-10.json").exists()
    assert set(json.loads(paths.seen.read_text())) == {"2609.08348", "2609.09426"}
    weekly = (paths.docs / "weekly.html").read_text()  # computing items feed the weekly pool
    assert "Instantaneous-Frame Theory" in weekly
    assert 'class="banner"' not in (paths.docs / "index.html").read_text()


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
         "pool": "A", "tags": ["platform:sc"], "cite": None, "section": "computing", "score": 40, "why": "x"}]}
    recent = {"run": "2026-09-09", "mode": "daily", "ranked": True, "status": {}, "items": [
        {"id": "new", "title": "New", "authors": [], "abstract": "", "categories": [], "submitted": "2026-09-09",
         "pool": "A", "tags": ["platform:sc"], "cite": None, "section": "computing", "score": 40, "why": "x"},
        {"id": "optics", "title": "Optics", "authors": [], "abstract": "", "categories": [], "submitted": "2026-09-09",
         "pool": "A", "tags": ["platform:sc"], "cite": None, "section": "A", "score": 90, "why": "x"}]}
    for d in (old, recent):
        (paths.digests / f"{d['run']}.json").write_text(json.dumps(d))

    status = fetch_weekly(load_config(paths), paths, today=date(2026, 9, 12))

    candidates = json.loads(paths.candidates.read_text())
    assert [(c["id"], c["pool"]) for c in candidates] == [("new", "weekly")]
    assert status["counts"] == {"weekly": 1}
    assert status["citations"] == "disabled"


# -- arXiv transport -------------------------------------------------------

RETRY_CONFIG = {
    "arxiv": {
        "max_results": 200,
        "delay_seconds": 3,
        "retries": 3,
        "retry_wait_seconds": 10,
        "retry_max_wait_seconds": 120,
    }
}


def make_fetcher(responses: list[httpx.Response | Exception]) -> tuple[FetchXml, list[float]]:
    """A fetcher whose transport replays `responses`; returns it with the sleeps it recorded."""
    remaining = list(responses)
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        item = remaining.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    client = httpx.Client(transport=httpx.MockTransport(handler))
    # jitter is identity here so the backoff schedule is exact; test_fetcher_jitters_the_backoff covers it
    fetcher = make_arxiv_fetcher(RETRY_CONFIG, sleep=sleeps.append, client=client, jitter=lambda w: w)
    return fetcher, sleeps


def test_fetcher_retries_429_with_doubling_backoff() -> None:
    fetch, sleeps = make_fetcher(
        [httpx.Response(429), httpx.Response(429), httpx.Response(200, text="<feed/>")]
    )

    assert fetch("https://export.arxiv.org/api/query?q=1") == "<feed/>"
    assert sleeps == [10, 20]  # 429 is throttling, not a bad query


def test_fetcher_honours_retry_after_over_its_own_backoff() -> None:
    fetch, sleeps = make_fetcher(
        [httpx.Response(429, headers={"Retry-After": "45"}), httpx.Response(200, text="<feed/>")]
    )

    assert fetch("https://export.arxiv.org/api/query?q=1") == "<feed/>"
    assert sleeps == [45]


def test_fetcher_caps_retry_after_and_ignores_a_malformed_one() -> None:
    capped, sleeps = make_fetcher(
        [httpx.Response(429, headers={"Retry-After": "9999"}), httpx.Response(200, text="<feed/>")]
    )
    capped("https://export.arxiv.org/api/query?q=1")
    assert sleeps == [120]

    malformed, sleeps = make_fetcher(
        [httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), httpx.Response(200, text="<feed/>")]
    )
    malformed("https://export.arxiv.org/api/query?q=1")
    assert sleeps == [10]  # falls back to the normal backoff


def test_fetcher_gives_up_on_429_after_the_configured_attempts() -> None:
    fetch, sleeps = make_fetcher([httpx.Response(429) for _ in range(4)])

    with pytest.raises(RuntimeError, match="failed after 4 attempts: HTTP 429"):
        fetch("https://export.arxiv.org/api/query?q=1")
    assert sleeps == [10, 20, 40]


def test_fetcher_still_retries_503_and_transport_errors() -> None:
    fetch, _ = make_fetcher(
        [httpx.Response(503), httpx.ConnectTimeout("timeout"), httpx.Response(200, text="<feed/>")]
    )

    assert fetch("https://export.arxiv.org/api/query?q=1") == "<feed/>"


def test_fetcher_does_not_retry_other_4xx() -> None:
    fetch, sleeps = make_fetcher([httpx.Response(400)])

    with pytest.raises(httpx.HTTPStatusError):  # a bad query never becomes good
        fetch("https://export.arxiv.org/api/query?q=1")
    assert sleeps == []


def test_fetcher_paces_successive_calls() -> None:
    fetch, sleeps = make_fetcher([httpx.Response(200, text="<feed/>") for _ in range(2)])

    fetch("https://export.arxiv.org/api/query?q=1")
    fetch("https://export.arxiv.org/api/query?q=2")
    assert sleeps == [3]  # no pause before the first call, delay_seconds before the next


def test_fetcher_jitters_the_backoff() -> None:
    sleeps: list[float] = []
    responses: list[httpx.Response] = [httpx.Response(429), httpx.Response(200, text="<feed/>")]
    client = httpx.Client(transport=httpx.MockTransport(lambda request: responses.pop(0)))
    fetch = make_arxiv_fetcher(
        RETRY_CONFIG, sleep=sleeps.append, client=client, jitter=lambda wait: wait * 0.8
    )

    fetch("https://export.arxiv.org/api/query?q=1")
    assert sleeps == [8]  # the 10s backoff passed through the jitter, not used raw


def test_real_settings_keep_a_run_short_and_backed_up() -> None:
    """A throttled pool must fail fast and have somewhere to fall back to; see 2026-09-14."""
    paths = Paths(root=ROOT)
    config = load_config(paths)
    arxiv = config["arxiv"]

    # Worst case per pool, ignoring jitter: the sum of the doubling backoffs.
    worst_case = sum(min(arxiv["retry_wait_seconds"] * 2**i, arxiv["retry_max_wait_seconds"])
                     for i in range(arxiv["retries"]))
    # Latency dominates when arXiv is throttling, so bound the requests too, not just the waits.
    attempts = 1 + arxiv["retries"]
    assert worst_case + attempts * arxiv["timeout_seconds"] <= 90, (
        "a throttled pool should give up in about a minute and fall back, not wait arXiv out"
    )

    assert config["backup"]["enabled"]
    for name, pool in config["pools"].items():
        assert pool.get("backup_query"), f"pool {name} has no OpenAlex backup query"


# -- OpenAlex backup -------------------------------------------------------


def boom(url: str) -> str:
    raise RuntimeError("arXiv request failed after 4 attempts: HTTP 429 (rate limited)")


def backup_paper(arxiv_id: str) -> Paper:
    return Paper(
        id=arxiv_id,
        title=f"Backup {arxiv_id}",
        authors=["A One"],
        abstract="a superconducting qubit abstract",
        categories=[],  # OpenAlex carries no arXiv categories
        submitted=TODAY,
    )


def test_pool_falls_back_to_openalex_when_arxiv_fails(paths: Paths) -> None:
    asked: list[str] = []

    def backup(pool: dict[str, object]) -> list[Paper]:
        asked.append(str(pool["backup_query"]))
        return [backup_paper("2609.09426")]

    status = fetch_daily(load_config(paths), paths, fetch_xml=boom, today=TODAY, backup=backup)

    assert len(asked) == 2  # both pools fell back
    assert status["pools"]["A"].startswith("backup: 1 from OpenAlex after arXiv failed")
    assert status["counts"]["A"] == 1
    # the reader is told the digest is thin, not just that something broke
    assert "indexes preprints a few days late" in status["error"]
    assert [c["id"] for c in json.loads(paths.candidates.read_text())] == ["2609.09426"]


def test_backup_is_not_used_when_arxiv_works(paths: Paths) -> None:
    def backup(pool: dict[str, object]) -> list[Paper]:
        raise AssertionError("backup must not run when arXiv answers")

    status = fetch_daily(load_config(paths), paths, fetch_xml=lambda url: FIXTURE, today=TODAY, backup=backup)

    assert status["pools"] == {"A": "ok", "B": "ok"}
    assert "error" not in status


def test_backup_failure_reports_both_errors(paths: Paths) -> None:
    def backup(pool: dict[str, object]) -> list[Paper]:
        raise RuntimeError("OpenAlex 500")

    status = fetch_daily(load_config(paths), paths, fetch_xml=boom, today=TODAY, backup=backup)

    assert "backup failed: OpenAlex 500" in status["pools"]["A"]
    assert "429" in status["error"] and "OpenAlex backup also failed" in status["error"]


def test_pool_without_a_backup_query_just_reports_the_arxiv_error(paths: Paths) -> None:
    status = fetch_daily(load_config(paths), paths, fetch_xml=boom, today=TODAY, backup=lambda pool: None)

    assert status["pools"]["A"].startswith("error: arXiv request failed")
    assert "OpenAlex" not in status["error"]
    assert status["counts"] == {"A": 0, "B": 0}
