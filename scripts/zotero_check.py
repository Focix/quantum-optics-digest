#!/usr/bin/env -S uv run
"""Check a Zotero API key the way the page's "Connect" button does, without echoing the key.

Usage: uv run scripts/zotero_check.py      (prompts for user ID and key; the key is not shown or stored)
"""

from __future__ import annotations

import getpass
import sys

import httpx

API = "https://api.zotero.org"


def main() -> int:
    user_id = input("Zotero user ID (a number, from zotero.org/settings/keys): ").strip()
    key = getpass.getpass("API key (hidden): ").strip()
    headers = {"Zotero-API-Key": key, "Zotero-API-Version": "3"}
    client = httpx.Client(timeout=30, headers=headers)

    r = client.get(f"{API}/keys/current")
    if r.status_code != 200:
        print(f"FAIL key check: HTTP {r.status_code} {r.text[:200]}")
        print("  The key itself is wrong (copied with spaces? revoked?).")
        return 1
    info = r.json()
    print(f"ok   key belongs to userID {info.get('userID')} (username {info.get('username')!r})")
    if str(info.get("userID")) != user_id:
        print(f"FAIL the user ID you typed ({user_id}) is not this key's userID ({info.get('userID')}). Use {info.get('userID')}.")
        return 1
    user_access = (info.get("access") or {}).get("user") or {}
    print(f"ok   access: library={user_access.get('library')} write={user_access.get('write')} notes={user_access.get('notes')}")
    if not user_access.get("write"):
        print("FAIL the key has no write access to your personal library. Edit the key at zotero.org/settings/keys and tick 'Allow write access'.")
        return 1

    r = client.get(f"{API}/users/{user_id}/collections", params={"limit": 100})
    if r.status_code != 200:
        print(f"FAIL listing collections: HTTP {r.status_code} {r.text[:200]}")
        return 1
    names = [c["data"]["name"] for c in r.json()]
    print(f"ok   {len(names)} collections: {', '.join(names[:15])}{' …' if len(names) > 15 else ''}")
    print("All good: this user ID and key will work in the page's Zotero dialog.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
