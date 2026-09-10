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
from digest.s2 import S2Client
from digest.select import mark_seen, select_candidates
from digest.store import build_digest, load_digests, write_digest

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
    def s2_cache(self) -> Path:
        return self.state / "s2_cache.json"

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
    state = {"calls": 0}

    def fetch(url: str) -> str:
        if state["calls"]:
            sleep(float(arxiv["delay_seconds"]))
        state["calls"] += 1
        last: Exception | None = None
        for attempt in range(1 + int(arxiv["retries"])):
            if attempt:
                sleep(float(arxiv["retry_wait_seconds"]))
            try:
                response = client.get(url)
                response.raise_for_status()
                return response.text
            except (httpx.HTTPError, OSError) as exc:  # 503, timeouts, resets
                last = exc
        raise RuntimeError(f"arXiv request failed after {1 + int(arxiv['retries'])} attempts: {last}")

    return fetch


# -- Semantic Scholar ------------------------------------------------------


def _s2_client(config: dict[str, Any], paths: Paths) -> S2Client | None:
    if not config["s2"].get("enabled"):
        return None
    return S2Client(cache_path=paths.s2_cache, api_key=os.environ.get("S2_API_KEY") or None)


def _enrich(candidates: list[Candidate], client: S2Client | None, status: dict[str, Any]) -> None:
    if client is None:
        status["s2"] = "disabled"
        return
    try:
        found = client.enrich([c.id for c in candidates if not c.url])
        for c in candidates:
            c.s2 = found.get(c.id)
        status["s2"] = f"ok ({len(found)}/{len(candidates)} found)" + ("" if client.api_key else ", unauthenticated")
    except Exception as exc:  # S2 down: digest still goes out, banner explains
        status["s2"] = f"error: {exc}"
        _add_error(status, f"S2 enrichment failed: {exc}")


def _add_error(status: dict[str, Any], message: str) -> None:
    status["error"] = f"{status['error']} | {message}" if status.get("error") else message


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
            _add_error(status, f"pool {name}: {exc}")

    seen: dict[str, str] = _read_json(paths.seen, {})
    selection = select_candidates(
        pools, seen=seen, today=today, window_days=int(run_cfg["window_days"]), cap=int(run_cfg["cap"])
    )
    status["counts"] = {name: selection.per_pool.get(name, 0) for name in config["pools"]}
    status["dropped_seen"] = selection.dropped_seen
    status["dropped_old"] = selection.dropped_old
    if selection.overflow:
        status["overflow"] = selection.overflow
        _add_error(status, f"{selection.overflow} candidates over the cap of {run_cfg['cap']} were dropped")

    _enrich(selection.candidates, _s2_client(config, paths), status)

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

    client = _s2_client(config, paths)
    if client is not None:
        try:
            after = (today - timedelta(days=int(weekly["s2_lookback_days"]))).isoformat()
            for record in client.search_bulk(weekly["s2_search_query"], published_after=after):
                ext = record.get("externalIds") or {}
                if ext.get("ArXiv") or not record.get("paperId"):
                    continue  # arXiv papers are already covered by the daily pool
                candidates.append(
                    Candidate(
                        id=f"s2:{record['paperId']}",
                        title=record.get("title") or "",
                        authors=[a.get("name", "") for a in record.get("authors") or []],
                        abstract=(record.get("tldr") or {}).get("text") or "",
                        categories=[],
                        submitted=date.fromisoformat(record["publicationDate"]) if record.get("publicationDate") else today,
                        pool="weekly",
                        tags=["source:s2"],
                        s2=S2Client._slim(record),
                        url=f"https://www.semanticscholar.org/paper/{record['paperId']}",
                    )
                )
            status["s2_search"] = "ok"
        except Exception as exc:
            status["s2_search"] = f"error: {exc}"
            _add_error(status, f"S2 search failed: {exc}")

    _enrich(candidates, client, status)
    candidates.sort(key=lambda c: c.submitted, reverse=True)
    status["counts"] = {"weekly": len(candidates)}
    _write_json(paths.candidates, [c.to_json() for c in candidates])
    _write_json(paths.status, status)
    return status


# -- publish ---------------------------------------------------------------


def publish(paths: Paths, *, mode: str, today: date, error: str | None = None) -> dict[str, Any] | None:
    """Merge out/ into a digest file (unless the run failed), then regenerate docs/."""
    digest: dict[str, Any] | None = None
    if error is None:
        candidates = [Candidate.from_json(c) for c in _read_json(paths.candidates, [])]
        ranking = _read_json(paths.ranking, None)
        status = _read_json(paths.status, {})
        digest = build_digest(candidates, ranking, status=status, run=today, mode=mode)
        write_digest(paths.digests, digest)
        if mode == "daily" and paths.seen_next.exists():
            _write_json(paths.seen, _read_json(paths.seen_next, {}))
    render_site(load_digests(paths.digests), paths.docs, today=today, error=error)
    return digest
