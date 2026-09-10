#!/usr/bin/env -S uv run
"""Fetch candidates for the digest. Usage: uv run scripts/fetch.py --mode daily|weekly"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from digest.pipeline import Paths, fetch_daily, fetch_weekly, load_config, make_arxiv_fetcher, today_in  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--today", help="override the run date (YYYY-MM-DD), default: today in Moscow")
    parser.add_argument("--window-days", type=int, help="override run.window_days (useful for backfill)")
    args = parser.parse_args()

    paths = Paths(root=Path(__file__).resolve().parent.parent)
    config = load_config(paths)
    if args.window_days is not None:
        config["run"]["window_days"] = args.window_days
    today = date.fromisoformat(args.today) if args.today else today_in(config)

    if args.mode == "daily":
        status = fetch_daily(config, paths, fetch_xml=make_arxiv_fetcher(config), today=today)
    else:
        status = fetch_weekly(config, paths, today=today)
    print(json.dumps(status, indent=1))
    return 1 if status.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
