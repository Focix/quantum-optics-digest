"""Author watchlist: papers by listed authors always surface with a why-line."""

from __future__ import annotations

import re
import tomllib
import unicodedata
from pathlib import Path

WATCH_PREFIX = "watch:"


def load_watchlist(path: Path) -> list[str]:
    """Read `authors = [...]` from a TOML file; a missing file means an empty list."""
    if not path.exists():
        return []
    data = tomllib.loads(path.read_text())
    return [str(a).strip() for a in data.get("authors", []) if str(a).strip()]


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _key(name: str) -> tuple[str, str]:
    """(last name, first initial). 'A. Wallraff' and 'Andreas Wallraff' share a key."""
    parts = [p for p in re.split(r"[\s.\-]+", _ascii(name)) if p]
    if not parts:
        return ("", "")
    if len(parts) == 1:
        return (parts[0], "")
    return (parts[-1], parts[0][0])


def _matches(watched: str, author: str) -> bool:
    w_last, w_init = _key(watched)
    a_last, a_init = _key(author)
    if not w_last or w_last != a_last:
        return False
    return not w_init or not a_init or w_init == a_init  # a bare surname on either side matches


def watch_tags(authors: list[str], watchlist: list[str]) -> list[str]:
    """One `watch:<name>` tag per watched author found on the paper, in watchlist order."""
    tags: list[str] = []
    for watched in watchlist:
        if any(_matches(watched, a) for a in authors):
            tags.append(f"{WATCH_PREFIX}{watched}")
    return tags


def watched_names(tags: list[str]) -> list[str]:
    return [t[len(WATCH_PREFIX) :] for t in tags if t.startswith(WATCH_PREFIX)]
