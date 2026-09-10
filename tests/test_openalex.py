import itertools
import json
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from digest.openalex import OpenAlexClient, reconstruct_abstract


def work(arxiv_id: str, cites: int = 3, journal: str | None = None) -> dict[str, Any]:
    locations = [{"source": {"display_name": "arXiv (Cornell University)", "type": "repository"}}]
    if journal:
        locations.insert(0, {"source": {"display_name": journal, "type": "journal"}})
    return {
        "id": f"https://openalex.org/W{arxiv_id.replace('.', '')}",
        "doi": f"https://doi.org/10.48550/arxiv.{arxiv_id}",
        "title": f"Title {arxiv_id}",
        "cited_by_count": cites,
        "publication_date": "2026-09-07",
        "primary_location": locations[0],
        "locations": locations,
        "authorships": [{"author": {"display_name": "A One"}}, {"author": {"display_name": "B Two"}}],
        "abstract_inverted_index": {"Quantum": [0], "optics": [1], "wins": [2]},
    }


def make_client(handler, tmp_path: Path, today: date = date(2026, 9, 10)) -> tuple[OpenAlexClient, list[float]]:  # type: ignore[no-untyped-def]
    sleeps: list[float] = []
    client = OpenAlexClient(
        cache_path=tmp_path / "cache.json",
        mailto="digest@example.org",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
        clock=itertools.count(0, 10).__next__,  # far apart: no rate-limit sleeps
        today=lambda: today,
    )
    return client, sleeps


def test_enrich_batches_dois_and_maps_results_back_to_arxiv_ids(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"results": [work("2609.00001", 3, journal="PRL"), work("2609.00002", 0)]})

    client, _ = make_client(handler, tmp_path)
    result = client.enrich(["2609.00001", "2609.00002", "2609.00003"])

    assert result == {
        "2609.00001": {"citationCount": 3, "venue": "PRL", "openalex": "https://openalex.org/W260900001"},
        "2609.00002": {"citationCount": 0, "venue": "", "openalex": "https://openalex.org/W260900002"},
    }
    params = dict(requests[0].url.params)
    assert params["filter"] == "doi:10.48550/arXiv.2609.00001|10.48550/arXiv.2609.00002|10.48550/arXiv.2609.00003"
    assert params["mailto"] == "digest@example.org"
    assert params["per-page"] == "50"

    # the miss is cached for a day, the hits for a week; nothing is refetched today
    client.enrich(["2609.00001", "2609.00003"])
    assert len(requests) == 1
    cached = json.loads((tmp_path / "cache.json").read_text())
    assert cached["2609.00003"] == {"fetched": "2026-09-10", "data": None}

    tomorrow, _ = make_client(handler, tmp_path, today=date(2026, 9, 11))
    tomorrow.enrich(["2609.00001", "2609.00003"])
    assert dict(requests[1].url.params)["filter"] == "doi:10.48550/arXiv.2609.00003"


def test_enrich_splits_requests_at_fifty_ids(tmp_path: Path) -> None:
    sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sizes.append(dict(request.url.params)["filter"].count("|") + 1)
        return httpx.Response(200, json={"results": []})

    client, _ = make_client(handler, tmp_path)
    client.enrich([f"2609.{i:05d}" for i in range(120)])
    assert sizes == [50, 50, 20]


def test_429_is_retried_with_backoff_then_raises(tmp_path: Path) -> None:
    client, sleeps = make_client(lambda request: httpx.Response(429), tmp_path)
    with pytest.raises(httpx.HTTPStatusError):
        client.enrich(["2609.00001"])
    assert sleeps == [2.0, 4.0, 8.0, 16.0]


def test_search_journal_returns_normalised_records(tmp_path: Path) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        w = work("2609.00001", 5, journal="Physical Review Applied")
        w["doi"] = "https://doi.org/10.1103/abcd-1234"
        return httpx.Response(200, json={"results": [w]})

    client, _ = make_client(handler, tmp_path)
    records = client.search_journal('"superconducting qubit" OR transmon', published_after="2026-08-27")

    params = dict(requests[0].url.params)
    assert "title_and_abstract.search:\"superconducting qubit\" OR transmon" in params["filter"]
    assert "from_publication_date:2026-08-27" in params["filter"]
    assert "primary_location.source.type:journal" in params["filter"]
    assert records == [{
        "id": "W260900001",
        "url": "https://doi.org/10.1103/abcd-1234",
        "title": "Title 2609.00001",
        "authors": ["A One", "B Two"],
        "abstract": "Quantum optics wins",
        "publicationDate": "2026-09-07",
        "hasArxiv": True,
        "cite": {"citationCount": 5, "venue": "Physical Review Applied", "openalex": "https://openalex.org/W260900001"},
    }]


def test_reconstruct_abstract_orders_words_by_position() -> None:
    assert reconstruct_abstract({"b": [1], "a": [0, 2]}) == "a b a"
    assert reconstruct_abstract(None) == ""
