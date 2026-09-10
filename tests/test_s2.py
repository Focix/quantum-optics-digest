import itertools
import json
from pathlib import Path

import httpx
import pytest

from digest.s2 import S2Client


def make_client(handler, tmp_path: Path, api_key: str | None = "k") -> S2Client:  # type: ignore[no-untyped-def]
    transport = httpx.MockTransport(handler)
    sleeps: list[float] = []
    client = S2Client(
        cache_path=tmp_path / "s2_cache.json",
        api_key=api_key,
        http=httpx.Client(transport=transport),
        sleep=sleeps.append,
        clock=itertools.count(0, 10).__next__,  # far apart: no rate-limit sleeps
    )
    client._sleeps = sleeps  # type: ignore[attr-defined]
    return client


def test_batch_enrich_returns_fields_and_caches(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        ids = json.loads(request.content)["ids"]
        return httpx.Response(
            200,
            json=[
                {"paperId": "x", "externalIds": {"ArXiv": i.removeprefix("ARXIV:")},
                 "citationCount": 3, "venue": "PRL", "tldr": {"text": "short"}}
                for i in ids
            ],
        )

    client = make_client(handler, tmp_path)
    result = client.enrich(["2609.00001", "2609.00002"])

    assert result["2609.00001"] == {"citationCount": 3, "venue": "PRL", "tldr": "short"}
    assert calls[0].headers["x-api-key"] == "k"
    assert json.loads(calls[0].content)["ids"] == ["ARXIV:2609.00001", "ARXIV:2609.00002"]

    # second call for one cached and one new ID: only the new one is requested
    client.enrich(["2609.00001", "2609.00003"])
    assert json.loads(calls[1].content)["ids"] == ["ARXIV:2609.00003"]
    cached = json.loads((tmp_path / "s2_cache.json").read_text())
    assert set(cached) == {"2609.00001", "2609.00002", "2609.00003"}


def test_missing_papers_are_recorded_as_null_and_not_refetched(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[None])

    client = make_client(handler, tmp_path)
    assert client.enrich(["2609.00009"]) == {}
    cached = json.loads((tmp_path / "s2_cache.json").read_text())
    assert cached["2609.00009"] is None


def test_429_is_retried_with_backoff_then_raises(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429)

    client = make_client(handler, tmp_path)
    with pytest.raises(httpx.HTTPStatusError):
        client.enrich(["2609.00001"])
    assert client._sleeps[-4:] == [2.0, 4.0, 8.0, 16.0]  # type: ignore[attr-defined]


def test_without_api_key_no_header_is_sent(tmp_path: Path) -> None:
    seen_headers: list[dict[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        return httpx.Response(200, json=[None])

    client = make_client(handler, tmp_path, api_key=None)
    client.enrich(["2609.00001"])
    assert "x-api-key" not in seen_headers[0]
