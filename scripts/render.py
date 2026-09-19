#!/usr/bin/env -S uv run
"""Merge out/ into digests/ and regenerate docs/.

Usage: uv run scripts/render.py [--mode daily|weekly] [--error "what failed"] [--backfill-only]
With --error no digest is written and state is untouched; the page shows a banner.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from digest.pipeline import Paths, load_config, publish, refresh, site_from, today_in  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["daily", "weekly"], default="daily")
    parser.add_argument("--error", help="the run failed at some step; render a banner instead of a digest")
    parser.add_argument("--log-url", help="link to the run log, shown in the banner")
    parser.add_argument("--today", help="override the run date (YYYY-MM-DD), default: today in Moscow")
    parser.add_argument(
        "--backfill-only",
        action="store_true",
        help="retry the citation counts past runs missed and re-render; do not merge out/",
    )
    args = parser.parse_args()

    paths = Paths(root=Path(__file__).resolve().parent.parent)
    config = load_config(paths)
    today = date.fromisoformat(args.today) if args.today else today_in(config)
    if args.backfill_only:
        print(f"citation backfill: {refresh(paths, config, today=today, site=site_from(config))}")
        return 0
    digest = publish(
        paths, mode=args.mode, today=today, error=args.error, log_url=args.log_url,
        site=site_from(config), config=config,
    )
    if digest is None:
        print(f"rendered error banner: {args.error}")
        return 0
    n = len(digest["items"])
    print(f"digest {digest['run']} ({digest['mode']}): {n} items, ranked={digest['ranked']}")
    if digest["status"].get("backfill"):
        print(f"citation backfill: {digest['status']['backfill']}")
    if digest["status"].get("error"):
        print(f"status error: {digest['status']['error']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
