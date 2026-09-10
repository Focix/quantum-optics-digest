"""Semantic Scholar client: batch enrichment with rate limiting, backoff and a JSON cache."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

BATCH_URL = "https://api.semanticscholar.org/graph/v1/paper/batch"
SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
FIELDS = "externalIds,citationCount,venue,tldr,title,authors,publicationDate,year"
BATCH_SIZE = 100
MAX_ATTEMPTS = 5
FIRST_BACKOFF = 2.0
MIN_INTERVAL = 1.0  # seconds between requests


class S2Client:
    def __init__(
        self,
        cache_path: Path,
        api_key: str | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cache_path = cache_path
        self.api_key = api_key
        self.http = http or httpx.Client(timeout=30)
        self.sleep = sleep
        self.clock = clock
        self._last_request = float("-inf")
        self.cache: dict[str, dict[str, Any] | None] = self._load_cache()

    # -- cache -------------------------------------------------------------

    def _load_cache(self) -> dict[str, dict[str, Any] | None]:
        if self.cache_path.exists():
            data: dict[str, dict[str, Any] | None] = json.loads(self.cache_path.read_text())
            return data
        return {}

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=0, sort_keys=True) + "\n")

    # -- transport ---------------------------------------------------------

    def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        headers = {"x-api-key": self.api_key} if self.api_key else {}
        backoff = FIRST_BACKOFF
        for attempt in range(1, MAX_ATTEMPTS + 1):
            wait = MIN_INTERVAL - (self.clock() - self._last_request)
            if wait > 0:
                self.sleep(wait)
            self._last_request = self.clock()
            response = self.http.request(method, url, headers=headers, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_ATTEMPTS:
                    response.raise_for_status()
                self.sleep(backoff)
                backoff *= 2
                continue
            response.raise_for_status()
            return response
        raise AssertionError("unreachable")

    # -- public API --------------------------------------------------------

    @staticmethod
    def _slim(record: dict[str, Any]) -> dict[str, Any]:
        tldr = record.get("tldr") or {}
        return {
            "citationCount": record.get("citationCount") or 0,
            "venue": record.get("venue") or "",
            "tldr": tldr.get("text") or "",
        }

    def enrich(self, arxiv_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return {arxiv_id: {citationCount, venue, tldr}} for IDs Semantic Scholar knows."""
        missing = [i for i in arxiv_ids if i not in self.cache]
        for start in range(0, len(missing), BATCH_SIZE):
            chunk = missing[start : start + BATCH_SIZE]
            response = self._request(
                "POST",
                BATCH_URL,
                params={"fields": FIELDS},
                json={"ids": [f"ARXIV:{i}" for i in chunk]},
            )
            records = response.json()
            for arxiv_id, record in zip(chunk, records, strict=True):
                self.cache[arxiv_id] = self._slim(record) if record else None
            self._save_cache()
        return {i: self.cache[i] for i in arxiv_ids if self.cache.get(i) is not None}  # type: ignore[misc]

    def search_bulk(self, query: str, *, published_after: str, limit: int = 100) -> list[dict[str, Any]]:
        """Bulk search; returns raw Semantic Scholar records (used weekly for non-arXiv papers)."""
        response = self._request(
            "GET",
            SEARCH_URL,
            params={
                "query": query,
                "fields": FIELDS,
                "publicationDateOrYear": f"{published_after}:",
                "fieldsOfStudy": "Physics",
                "limit": limit,
            },
        )
        data: list[dict[str, Any]] = response.json().get("data", [])
        return data
