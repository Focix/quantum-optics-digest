#!/usr/bin/env -S uv run
"""Pull 👍/👎 feedback issues from GitHub into state/feedback.json and close them.

Usage: uv run scripts/feedback.py [--keep-open]
Uses `gh` for the repo in config/settings.toml [site].repo when it is installed and
authenticated; otherwise falls back to the REST API, which needs no token to read a public
repo's issues but does need GH_TOKEN/GITHUB_TOKEN to close them. Unclosed issues are re-read
next run and merged by issue number, so leaving them open costs nothing but the open issue.
Never fails the run: on any error it prints a warning and exits 0 so the digest still publishes.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from digest.feedback import load_feedback, merge_feedback, parse_issue, save_feedback  # noqa: E402
from digest.pipeline import Paths, load_config  # noqa: E402


API = "https://api.github.com"


def gh(*args: str) -> str:
    return subprocess.run(["gh", *args], check=True, capture_output=True, text=True, timeout=60).stdout


def token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def rest(method: str, path: str, **kwargs: Any) -> httpx.Response:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token():
        headers["Authorization"] = f"Bearer {token()}"
    response = httpx.request(method, f"{API}{path}", headers=headers, timeout=30, **kwargs)
    response.raise_for_status()
    return response


def list_issues(repo: str) -> list[dict[str, Any]]:
    """Open feedback issues, via `gh` when it works and the REST API when it does not."""
    try:
        raw = gh("issue", "list", "-R", repo, "--label", "feedback", "--state", "open", "--limit", "200",
                 "--json", "number,title,body,labels,createdAt")
        issues: list[dict[str, Any]] = json.loads(raw)
        return issues
    except Exception as exc:  # gh missing, or not authenticated
        print(f"feedback: gh unavailable ({exc}), falling back to the REST API")
    params = {"labels": "feedback", "state": "open", "per_page": "100"}
    results: list[dict[str, Any]] = []
    for issue in rest("GET", f"/repos/{repo}/issues", params=params).json():
        if "pull_request" in issue:  # the issues endpoint lists PRs too
            continue
        results.append({**issue, "createdAt": issue.get("created_at")})  # match the gh --json shape
    return results


def close_issue(repo: str, number: int, comment: str) -> None:
    try:
        gh("issue", "close", "-R", repo, str(number), "-c", comment)
        return
    except Exception:
        pass
    if not token():
        raise RuntimeError("no gh and no GH_TOKEN/GITHUB_TOKEN, leaving the issue open")
    rest("POST", f"/repos/{repo}/issues/{number}/comments", json={"body": comment})
    rest("PATCH", f"/repos/{repo}/issues/{number}", json={"state": "closed"})


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
        issues = list_issues(repo)
    except Exception as exc:  # network, auth
        print(f"feedback: warning, could not list issues: {exc}")
        return 0

    records = [r for r in (parse_issue(i) for i in issues) if r is not None]
    merged = merge_feedback(load_feedback(paths.feedback), records)
    save_feedback(paths.feedback, merged)
    print(f"feedback: {len(records)} new, {len(merged)} total in {paths.feedback.relative_to(paths.root)}")

    if not args.keep_open:
        for r in records:
            try:
                close_issue(repo, int(r["issue"]),
                            "Recorded in state/feedback.json; the next ranking run reads it.")
            except Exception as exc:
                print(f"feedback: warning, could not close #{r['issue']}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
