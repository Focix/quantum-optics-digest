"""End-to-end steps used by the scripts: fetch (daily/weekly) and publish."""

from __future__ import annotations

import json
import os
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from digest.arxiv import build_query_url, parse_feed
from digest.models import Candidate, Paper
from digest.render import render_site
from digest.openalex import OpenAlexClient
from digest.select import mark_seen, select_candidates
from digest.store import add_error, build_digest, digest_path, load_digests, merge_digests, write_digest

FetchXml = Callable[[str], str]


@dataclass
class Paths:
    root: Path

    @property
    def config(self) -> Path:
        return self.root / "config"

    @property
    def state(self) -> Path:
        return self.root / "state"

    @property
    def seen(self) -> Path:
        return self.state / "seen.json"

    @property
    def cite_cache(self) -> Path:
        return self.state / "openalex_cache.json"

    @property
    def out(self) -> Path:
        return self.root / "out"

    @property
    def candidates(self) -> Path:
        return self.out / "candidates.json"

    @property
    def status(self) -> Path:
        return self.out / "status.json"

    @property
    def ranking(self) -> Path:
        return self.out / "ranking.json"

    @property
    def seen_next(self) -> Path:
        return self.out / "seen_next.json"

    @property
    def digests(self) -> Path:
        return self.root / "digests"

    @property
    def docs(self) -> Path:
        return self.root / "docs"


def load_config(paths: Paths) -> dict[str, Any]:
    settings = tomllib.loads((paths.config / "settings.toml").read_text())
    queries = tomllib.loads((paths.config / "queries.toml").read_text())
    return {**settings, "pools": queries["pools"]}


def today_in(config: dict[str, Any]) -> date:
    return datetime.now(ZoneInfo(config["run"]["timezone"])).date()


def _read_json(path: Path, default: Any) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


# -- arXiv transport -------------------------------------------------------


def make_arxiv_fetcher(config: dict[str, Any], sleep: Callable[[float], None] = time.sleep) -> FetchXml:
    arxiv = config["arxiv"]
    client = httpx.Client(timeout=60, headers={"User-Agent": "quantum-optics-digest (github.com/Focix)"})
    calls = 0

    def fetch(url: str) -> str:
        nonlocal calls
        if calls:
            sleep(float(arxiv["delay_seconds"]))
        calls += 1
        last: Exception | None = None
        for attempt in range(1 + int(arxiv["retries"])):
            if attempt:
                sleep(float(arxiv["retry_wait_seconds"]))
            try:
                response = client.get(url)
            except (httpx.TransportError, OSError) as exc:  # timeouts, resets
                last = exc
                continue
            if response.status_code >= 500:  # arXiv's occasional 503
                last = RuntimeError(f"HTTP {response.status_code}")
                continue
            response.raise_for_status()  # 4xx: a bad query, do not retry
            return response.text
        raise RuntimeError(f"arXiv request failed after {1 + int(arxiv['retries'])} attempts: {last}")

    return fetch


# -- citations (OpenAlex) --------------------------------------------------


def _citation_client(config: dict[str, Any], paths: Paths) -> OpenAlexClient | None:
    cfg = config.get("citations", {})
    if not cfg.get("enabled"):
        return None
    return OpenAlexClient(cache_path=paths.cite_cache, mailto=cfg.get("mailto") or None)


def _enrich(candidates: list[Candidate], client: OpenAlexClient | None, status: dict[str, Any]) -> None:
    if client is None:
        status["citations"] = "disabled"
        return
    arxiv_papers = [c for c in candidates if not c.url]  # journal-search items already carry cite
    try:
        found = client.enrich([c.id for c in arxiv_papers])
        for c in arxiv_papers:
            c.cite = found.get(c.id)
        status["citations"] = f"ok ({len(found)}/{len(arxiv_papers)} found)"
    except Exception as exc:  # OpenAlex down: digest still goes out, banner explains
        status["citations"] = f"error: {exc}"
        add_error(status, f"citation lookup failed: {exc}")


# -- daily -----------------------------------------------------------------


def fetch_daily(config: dict[str, Any], paths: Paths, *, fetch_xml: FetchXml, today: date) -> dict[str, Any]:
    run_cfg = config["run"]
    status: dict[str, Any] = {"run": today.isoformat(), "mode": "daily", "pools": {}, "counts": {}}
    pools: dict[str, list[Paper]] = {}
    for name, pool in config["pools"].items():
        url = build_query_url(pool["categories"], pool["query"], int(config["arxiv"]["max_results"]))
        try:
            pools[name] = parse_feed(fetch_xml(url))
            status["pools"][name] = "ok"
        except Exception as exc:
            status["pools"][name] = f"error: {exc}"
            add_error(status, f"pool {name}: {exc}")

    seen: dict[str, str] = _read_json(paths.seen, {})
    selection = select_candidates(
        pools, seen=seen, today=today, window_days=int(run_cfg["window_days"]), cap=int(run_cfg["cap"])
    )
    status["counts"] = {name: selection.per_pool.get(name, 0) for name in config["pools"]}
    status["dropped_seen"] = selection.dropped_seen
    status["dropped_old"] = selection.dropped_old
    if selection.overflow:  # noted, not an error: the page stays green
        status["overflow"] = f"{selection.overflow} oldest candidates dropped over the cap of {run_cfg['cap']}"

    _enrich(selection.candidates, _citation_client(config, paths), status)

    _write_json(paths.candidates, [c.to_json() for c in selection.candidates])
    _write_json(paths.seen_next, mark_seen(seen, selection.candidates, today=today, keep_days=int(run_cfg["seen_keep_days"])))
    _write_json(paths.status, status)
    return status


# -- weekly ----------------------------------------------------------------


def fetch_weekly(config: dict[str, Any], paths: Paths, *, today: date) -> dict[str, Any]:
    weekly = config["weekly"]
    status: dict[str, Any] = {"run": today.isoformat(), "mode": "weekly", "counts": {}}
    since = today - timedelta(days=int(weekly["lookback_days"]))
    candidates: list[Candidate] = []
    seen_ids: set[str] = set()
    for digest in load_digests(paths.digests):
        if digest["mode"] != "daily" or date.fromisoformat(digest["run"]) < since:
            continue
        for item in digest["items"]:
            if item.get("section") == "computing" and item["id"] not in seen_ids:
                seen_ids.add(item["id"])
                c = Candidate.from_json(item)
                c.pool = "weekly"
                candidates.append(c)

    client = _citation_client(config, paths)
    if client is not None and weekly.get("journal_search_query"):
        try:
            after = (today - timedelta(days=int(weekly["journal_lookback_days"]))).isoformat()
            for record in client.search_journal(weekly["journal_search_query"], published_after=after):
                if record["hasArxiv"] or record["id"] in seen_ids:
                    continue  # arXiv papers are already covered by the daily pool
                seen_ids.add(record["id"])
                candidates.append(
                    Candidate(
                        id=record["id"],
                        title=record["title"],
                        authors=record["authors"],
                        abstract=record["abstract"],
                        categories=[],
                        submitted=date.fromisoformat(record["publicationDate"]) if record["publicationDate"] else today,
                        pool="weekly",
                        tags=["source:openalex"],
                        cite=record["cite"],
                        url=record["url"],
                    )
                )
            status["journal_search"] = "ok"
        except Exception as exc:
            status["journal_search"] = f"error: {exc}"
            add_error(status, f"journal search failed: {exc}")

    _enrich(candidates, client, status)
    candidates.sort(key=lambda c: c.submitted, reverse=True)
    status["counts"] = {"weekly": len(candidates)}
    _write_json(paths.candidates, [c.to_json() for c in candidates])
    _write_json(paths.status, status)
    return status


# -- publish ---------------------------------------------------------------


def publish(
    paths: Paths, *, mode: str, today: date, error: str | None = None, log_url: str | None = None
) -> dict[str, Any] | None:
    """Merge out/ into a digest file (unless the run failed), then regenerate docs/."""
    digest: dict[str, Any] | None = None
    if error is None:
        candidates = [Candidate.from_json(c) for c in _read_json(paths.candidates, [])]
        ranking = _read_json(paths.ranking, None)
        status = _read_json(paths.status, {})
        digest = build_digest(candidates, ranking, status=status, run=today, mode=mode)
        existing = digest_path(paths.digests, today, mode)
        if existing.exists():  # a second run today (manual or retried) must not lose the first
            digest = merge_digests(json.loads(existing.read_text()), digest)
        write_digest(paths.digests, digest)
        if mode == "daily" and paths.seen_next.exists():
            _write_json(paths.seen, _read_json(paths.seen_next, {}))
    render_site(load_digests(paths.digests), paths.docs, today=today, error=error, log_url=log_url)
    return digest
