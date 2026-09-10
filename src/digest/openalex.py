"""OpenAlex client: citation counts and venues for arXiv papers, plus a journal search.

No API key. A `mailto` parameter puts requests in the polite pool. Every answer is
cached with a fetch date so unknown papers are retried after a day and counts
refresh after a week.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import httpx

WORKS_URL = "https://api.openalex.org/works"
FIELDS = "id,doi,title,cited_by_count,publication_date,primary_location,locations,authorships,abstract_inverted_index"
BATCH_SIZE = 50  # OpenAlex caps OR'ed filter values at 50
MAX_ATTEMPTS = 5
FIRST_BACKOFF = 2.0
MIN_INTERVAL = 1.0  # seconds between requests
MISS_TTL_DAYS = 1
HIT_TTL_DAYS = 7
ARXIV_DOI_PREFIX = "10.48550/arxiv."


def reconstruct_abstract(inverted: dict[str, list[int]] | None) -> str:
    if not inverted:
        return ""
    positions = sorted((pos, word) for word, poss in inverted.items() for pos in poss)
    return " ".join(word for _, word in positions)


def _venue(work: dict[str, Any]) -> str:
    """First journal or conference location; empty for preprint-only works."""
    for loc in [work.get("primary_location") or {}] + list(work.get("locations") or []):
        source = loc.get("source") or {}
        if source.get("type") in ("journal", "conference") and source.get("display_name"):
            return str(source["display_name"])
    return ""


def _has_arxiv(work: dict[str, Any]) -> bool:
    doi = (work.get("doi") or "").lower()
    if ARXIV_DOI_PREFIX in doi:
        return True
    return any(
        "arxiv" in (((loc.get("source") or {}).get("display_name") or "").lower())
        for loc in work.get("locations") or []
    )


def slim(work: dict[str, Any]) -> dict[str, Any]:
    """The fields the digest keeps per paper."""
    return {"citationCount": work.get("cited_by_count") or 0, "venue": _venue(work), "openalex": work.get("id") or ""}


def _arxiv_id_from_doi(doi: str) -> str | None:
    doi = doi.lower()
    idx = doi.find(ARXIV_DOI_PREFIX)
    return doi[idx + len(ARXIV_DOI_PREFIX):] if idx >= 0 else None


class OpenAlexClient:
    def __init__(
        self,
        cache_path: Path,
        mailto: str | None = None,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        today: Callable[[], date] = date.today,
    ) -> None:
        self.cache_path = cache_path
        self.mailto = mailto or None
        self.http = http or httpx.Client(timeout=30, headers={"User-Agent": "quantum-optics-digest"})
        self.sleep = sleep
        self.clock = clock
        self.today = today
        self._last_request = float("-inf")
        self.cache: dict[str, dict[str, Any]] = (
            json.loads(cache_path.read_text()) if cache_path.exists() else {}
        )

    # -- cache -------------------------------------------------------------

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.cache_path.write_text(json.dumps(self.cache, indent=0, sort_keys=True) + "\n")

    def _fresh(self, arxiv_id: str) -> bool:
        entry = self.cache.get(arxiv_id)
        if entry is None:
            return False
        ttl = HIT_TTL_DAYS if entry.get("data") is not None else MISS_TTL_DAYS
        return date.fromisoformat(entry["fetched"]) + timedelta(days=ttl) > self.today()

    # -- transport ---------------------------------------------------------

    def _get(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.mailto:
            params = {**params, "mailto": self.mailto}
        backoff = FIRST_BACKOFF
        for attempt in range(1, MAX_ATTEMPTS + 1):
            wait = MIN_INTERVAL - (self.clock() - self._last_request)
            if wait > 0:
                self.sleep(wait)
            self._last_request = self.clock()
            response = self.http.get(WORKS_URL, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt == MAX_ATTEMPTS:
                    response.raise_for_status()
                self.sleep(backoff)
                backoff *= 2
                continue
            response.raise_for_status()
            data: dict[str, Any] = response.json()
            return data
        raise AssertionError("unreachable")

    # -- public API --------------------------------------------------------

    def enrich(self, arxiv_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Return {arxiv_id: {citationCount, venue, openalex}} for the papers OpenAlex knows."""
        missing = [i for i in arxiv_ids if not self._fresh(i)]
        fetched = self.today().isoformat()
        for start in range(0, len(missing), BATCH_SIZE):
            chunk = missing[start : start + BATCH_SIZE]
            dois = "|".join(f"10.48550/arXiv.{i}" for i in chunk)
            data = self._get({"filter": f"doi:{dois}", "select": FIELDS, "per-page": BATCH_SIZE})
            found: dict[str, dict[str, Any]] = {}
            for work in data.get("results", []):
                arxiv_id = _arxiv_id_from_doi(work.get("doi") or "")
                if arxiv_id:
                    found[arxiv_id] = slim(work)
            for i in chunk:
                self.cache[i] = {"fetched": fetched, "data": found.get(i)}
            self._save_cache()
        result: dict[str, dict[str, Any]] = {}
        for i in arxiv_ids:
            data_ = (self.cache.get(i) or {}).get("data")
            if data_ is not None:
                result[i] = data_
        return result

    def search_journal(self, query: str, *, published_after: str, limit: int = 100) -> list[dict[str, Any]]:
        """Journal articles matching the query, newest first, as normalised records."""
        filters = [
            f"title_and_abstract.search:{query}",
            f"from_publication_date:{published_after}",
            "primary_location.source.type:journal",
        ]
        data = self._get(
            {"filter": ",".join(filters), "select": FIELDS, "per-page": limit, "sort": "publication_date:desc"}
        )
        records: list[dict[str, Any]] = []
        for work in data.get("results", []):
            records.append(
                {
                    "id": (work.get("id") or "").rsplit("/", 1)[-1],
                    "url": work.get("doi") or work.get("id") or "",
                    "title": work.get("title") or "",
                    "authors": [a.get("author", {}).get("display_name", "") for a in work.get("authorships") or []],
                    "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
                    "publicationDate": work.get("publication_date") or "",
                    "hasArxiv": _has_arxiv(work),
                    "cite": slim(work),
                }
            )
        return records
