#!/usr/bin/env -S uv run
"""Pull 👍/👎 feedback issues from GitHub into state/feedback.json and close them.

Usage: uv run scripts/feedback.py [--keep-open]
Needs `gh` authenticated for the repo in config/settings.toml [site].repo. Never fails the run:
on any error it prints a warning and exits 0 so the digest still publishes.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from digest.feedback import load_feedback, merge_feedback, parse_issue, save_feedback  # noqa: E402
from digest.pipeline import Paths, load_config  # noqa: E402


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, timeout=60).stdout


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep-open", action="store_true", help="record the issues but do not close them")
    args = parser.parse_args()

    paths = Paths(root=Path(__file__).resolve().parent.parent)
    repo = load_config(paths).get("site", {}).get("repo")
    if not repo:
        print("feedback: no [site].repo in settings.toml, skipping")
        return 0
    try:
        raw = gh("issue", "list", "-R", repo, "--label", "feedback", "--state", "open", "--limit", "200",
                 "--json", "number,title,body,labels,createdAt")
        issues = json.loads(raw)
    except Exception as exc:  # network, auth, gh missing
        print(f"feedback: warning, could not list issues: {exc}")
        return 0

    records = [r for r in (parse_issue(i) for i in issues) if r is not None]
    merged = merge_feedback(load_feedback(paths.feedback), records)
    save_feedback(paths.feedback, merged)
    print(f"feedback: {len(records)} new, {len(merged)} total in {paths.feedback.relative_to(paths.root)}")

    if not args.keep_open:
        for r in records:
            try:
                gh("issue", "close", "-R", repo, str(r["issue"]), "-c",
                   "Recorded in state/feedback.json; the next ranking run reads it.")
            except Exception as exc:
                print(f"feedback: warning, could not close #{r['issue']}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
