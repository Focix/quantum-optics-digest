"""Static site rendering: one page per section (A, B, weekly), archive pages, stylesheet."""

from __future__ import annotations

import html
from datetime import date, timedelta
from pathlib import Path
from typing import Any

SECTION_TITLES = {
    "A": "Superconducting artificial atoms",
    "B": "Quantum optics on other platforms",
    "weekly": "Superconducting quantum computing, weekly",
    "computing": "Superconducting quantum computing (held for Saturday)",
}
PAGES = {"A": "index.html", "B": "b.html", "weekly": "weekly.html"}
NAV_LABELS = {"A": "A · Superconducting atoms", "B": "B · Other platforms", "weekly": "Weekly · Computing"}
SECTION_ORDER = ["A", "B", "weekly", "computing"]
KIND_TITLES = {"T": "theory", "E": "experiment", "TE": "theory and experiment"}
TOP_N = 10
PREVIOUS_DAYS = 14
SITE_TITLE = "Quantum Optics Digest"

STYLE = """
:root { --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6b66; --line:#e2e0d9; --accent:#8a3b12; --hi:#fff4e5; --warn:#b3261e; --warnbg:#fde7e5; --t:#2b5f9e; --e:#2e7d4f; --te:#7a4b9d; }
@media (prefers-color-scheme: dark) { :root { --bg:#161614; --fg:#ebe8e0; --muted:#9c9a92; --line:#33322e; --accent:#f0a06a; --hi:#2a2118; --warn:#ff8a80; --warnbg:#3a1c1a; --t:#7fb0e8; --e:#7fd0a0; --te:#c39ae6; } }
html { color-scheme: light dark; }
body { margin:0; padding:1.5rem 1rem 3rem; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:52rem; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .25rem; }
h1 a { color:inherit; text-decoration:none; }
h2 { font-size:1.25rem; margin:2rem 0 .5rem; border-bottom:1px solid var(--line); padding-bottom:.25rem; }
h3 { font-size:1.05rem; margin:1.25rem 0 .5rem; color:var(--accent); }
.sub { color:var(--muted); margin:0; }
nav { display:flex; flex-wrap:wrap; gap:.25rem 1rem; margin:1rem 0; padding:.5rem 0; border-bottom:1px solid var(--line); }
nav a { color:var(--muted); text-decoration:none; font-weight:600; }
nav a.current { color:var(--accent); border-bottom:2px solid var(--accent); }
.legend { color:var(--muted); font-size:.85rem; margin:.25rem 0 0; }
.banner { background:var(--warnbg); color:var(--warn); border:1px solid var(--warn); border-radius:6px; padding:.75rem 1rem; margin:1rem 0; }
.banner code { white-space:pre-wrap; word-break:break-word; }
ol.papers { list-style:none; padding:0; margin:0; }
ol.papers > li { padding:.6rem 0; border-bottom:1px solid var(--line); }
ol.papers > li.read { background:var(--hi); margin:0 -.5rem; padding:.6rem .5rem; border-radius:4px; }
.title { font-weight:600; }
.title a { color:inherit; text-decoration:none; }
.title a:hover { text-decoration:underline; }
.meta { color:var(--muted); font-size:.9rem; }
.why { margin:.15rem 0 0; }
.score { display:inline-block; min-width:2.2em; text-align:right; font-variant-numeric:tabular-nums; color:var(--muted); margin-right:.5rem; }
li.read .score { color:var(--accent); font-weight:600; }
.kind { display:inline-block; min-width:1.6em; text-align:center; font-size:.75rem; font-weight:700; line-height:1.4; border-radius:3px; padding:0 .3em; margin-right:.5rem; color:#fff; vertical-align:middle; }
.kind-T { background:var(--t); } .kind-E { background:var(--e); } .kind-TE { background:var(--te); }
details { margin:.5rem 0; }
summary { cursor:pointer; color:var(--muted); }
details.day { border-bottom:1px solid var(--line); padding:.4rem 0; }
details.day > summary { color:var(--fg); }
ul.titles { padding-left:1.25rem; margin:.5rem 0; }
ul.titles li { margin:.2rem 0; }
footer { margin-top:3rem; color:var(--muted); font-size:.9rem; }
footer ul { columns:2; padding-left:1.25rem; }
"""


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _authors(authors: list[str]) -> str:
    shown = ", ".join(authors[:3])
    return f"{shown} et al." if len(authors) > 3 else shown


def _url(item: dict[str, Any]) -> str:
    url = item.get("url")
    return str(url) if url else f"https://arxiv.org/abs/{item['id']}"


def _kind(item: dict[str, Any]) -> str:
    kind = item.get("kind")
    if kind not in KIND_TITLES:
        return ""
    return f'<span class="kind kind-{kind}" title="{KIND_TITLES[kind]}">{kind}</span>'


def _score(item: dict[str, Any]) -> str:
    score = item.get("score")
    return f'<span class="score">{score}</span>' if score is not None else ""


def _paper_li(item: dict[str, Any]) -> str:
    score = item.get("score")
    cls = ' class="read"' if isinstance(score, int) and score >= 80 else ""
    meta = [_authors(item.get("authors", [])), item.get("submitted", "")]
    cite = item.get("cite") or {}
    if cite.get("citationCount"):
        meta.append(f"{cite['citationCount']} citations")
    if cite.get("venue"):
        meta.append(cite["venue"])
    why = f'<p class="why">{_esc(item["why"])}</p>' if item.get("why") else ""
    return (
        f"<li{cls}>{_score(item)}{_kind(item)}<span class=\"title\"><a href=\"{_esc(_url(item))}\">"
        f"{_esc(item['title'])}</a></span>"
        f"<div class=\"meta\">{_esc(' · '.join(m for m in meta if m))}</div>{why}</li>"
    )


def _title_li(item: dict[str, Any]) -> str:
    return f"<li>{_score(item)}{_kind(item)}<a href=\"{_esc(_url(item))}\">{_esc(item['title'])}</a></li>"


def _titles_details(summary: str, items: list[dict[str, Any]]) -> str:
    inner = "".join(_title_li(i) for i in items)
    return f"<details><summary>{_esc(summary)}</summary><ul class=\"titles\">{inner}</ul></details>"


def _papers(items: list[dict[str, Any]], *, top_n: int = TOP_N) -> str:
    """Top-N with why-lines, the rest collapsed titles-only. Nothing dropped."""
    if not items:
        return '<p class="meta">No new papers.</p>'
    top, rest = items[:top_n], items[top_n:]
    out = '<ol class="papers">' + "".join(_paper_li(i) for i in top) + "</ol>"
    if rest:
        out += _titles_details(f"also matched ({len(rest)} more)", rest)
    return out


def _items(digest: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return [i for i in digest.get("items", []) if i.get("section") == section]


def _unranked_note(digest: dict[str, Any]) -> str:
    if digest.get("ranked", True):
        return ""
    return '<p class="meta">unranked: the model output was rejected, showing the raw candidate list.</p>'


def render_digest_body(digest: dict[str, Any]) -> str:
    """All sections of one digest (archive pages)."""
    parts = [_unranked_note(digest)]
    present = {i.get("section", "A") for i in digest.get("items", [])}
    if not present:
        parts.append('<p class="meta">No new papers.</p>')
    for key in SECTION_ORDER + sorted(present - set(SECTION_ORDER)):
        if key not in present:
            continue
        items = _items(digest, key)
        parts.append(f"<h3>{_esc(SECTION_TITLES.get(key, str(key)))} <span class=\"meta\">({len(items)})</span></h3>")
        parts.append(_titles_details(f"{len(items)} papers", items) if key == "computing" else _papers(items))
    return "\n".join(p for p in parts if p)


def _pretty_date(iso: str) -> str:
    return date.fromisoformat(iso).strftime("%A %-d %B %Y")


def previous_working_day(today: date) -> date:
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _banner(latest_daily: dict[str, Any] | None, today: date, error: str | None, log_url: str | None) -> str:
    messages: list[str] = []
    if error:
        messages.append(error)
    if latest_daily is None:
        messages.append("No digest has been generated yet.")
    else:
        status_error = (latest_daily.get("status") or {}).get("error")
        if status_error:
            messages.append(f"Run {latest_daily['run']}: {status_error}")
        if date.fromisoformat(latest_daily["run"]) < previous_working_day(today):
            messages.append(f"Digest is stale: newest run is {latest_daily['run']}, today is {today.isoformat()}.")
    if not messages:
        return ""
    body = "<br>".join(f"<code>{_esc(m)}</code>" for m in messages)
    link = "" if not log_url else f' <a href="{_esc(log_url)}">run log</a>'
    return f'<div class="banner"><strong>Problem.</strong> {body}{link}</div>'


def _header(current: str | None, *, root: str) -> str:
    links = "".join(
        f'<a href="{root}{PAGES[key]}"{" class=\"current\"" if key == current else ""}>{_esc(NAV_LABELS[key])}</a>'
        for key in PAGES
    )
    return (
        f"<h1><a href=\"{root or './'}\">{SITE_TITLE}</a></h1>"
        '<p class="sub">New arXiv papers ranked each weekday morning against a written interest statement.</p>'
        f"<nav>{links}</nav>"
        '<p class="legend"><span class="kind kind-T">T</span>theory &nbsp; <span class="kind kind-E">E</span>experiment '
        '&nbsp; <span class="kind kind-TE">TE</span>both &nbsp; score ≥80 highlighted</p>'
    )


def _page(title: str, body: str, *, css_href: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{_esc(title)}</title>\n<link rel=\"stylesheet\" href=\"{css_href}\">\n</head>\n<body>\n<main>\n"
        f"{body}\n</main>\n</body>\n</html>\n"
    )


def _archive_name(digest: dict[str, Any]) -> str:
    suffix = "" if digest["mode"] == "daily" else f"-{digest['mode']}"
    return f"{digest['run']}{suffix}.html"


def _archive_footer(digests: list[dict[str, Any]]) -> str:
    links = "".join(
        f"<li><a href=\"archive/{_archive_name(d)}\">{d['run']}{' (weekly)' if d['mode'] == 'weekly' else ''}</a></li>"
        for d in digests
    )
    return f"<footer><h2>Archive</h2><ul>{links}</ul></footer>"


def _day_details(d: dict[str, Any], items: list[dict[str, Any]]) -> str:
    top = next((i["title"] for i in items if i.get("score") is not None), None)
    hint = f" · {_esc(top)}" if top else ""
    return (
        f"<details class=\"day\"><summary>{_pretty_date(d['run'])} · {len(items)} papers{hint}</summary>"
        f"{_unranked_note(d)}{_papers(items)}</details>"
    )


def _section_body(digests: list[dict[str, Any]], section: str) -> str:
    dailies = [d for d in digests if d["mode"] == "daily"]
    parts = [f"<h2>{_esc(SECTION_TITLES[section])}</h2>"]
    if dailies:
        latest = dailies[0]
        parts.append(f"<h3>Today · {_pretty_date(latest['run'])}</h3>")
        parts.append(_unranked_note(latest) + _papers(_items(latest, section)))
    previous = dailies[1 : 1 + PREVIOUS_DAYS]
    if previous:
        parts.append("<h2>Previous days</h2>")
        parts.extend(_day_details(d, _items(d, section)) for d in previous)
    return "\n".join(parts)


def _weekly_body(digests: list[dict[str, Any]], today: date) -> str:
    weeklies = [d for d in digests if d["mode"] == "weekly"]
    dailies = [d for d in digests if d["mode"] == "daily"]
    parts = [f"<h2>{_esc(SECTION_TITLES['weekly'])}</h2>"]
    if weeklies:
        latest = weeklies[0]
        parts.append(f"<h3>Week ending {_pretty_date(latest['run'])}</h3>")
        parts.append(_unranked_note(latest) + _papers(_items(latest, "weekly")))
        since = date.fromisoformat(latest["run"])
    else:
        parts.append('<p class="meta">No weekly digest yet. The first one comes on Saturday.</p>')
        since = today - timedelta(days=7)
    pool = [i for d in dailies if date.fromisoformat(d["run"]) > since for i in _items(d, "computing")]
    if pool:
        parts.append(f"<h3>Pool for the next weekly digest <span class=\"meta\">({len(pool)})</span></h3>")
        parts.append(_titles_details(f"{len(pool)} computing papers since {since.isoformat()}", pool))
    if len(weeklies) > 1:
        parts.append("<h2>Previous weeks</h2>")
        parts.extend(_day_details(d, _items(d, "weekly")) for d in weeklies[1 : 1 + PREVIOUS_DAYS])
    return "\n".join(parts)


def render_page(
    digests: list[dict[str, Any]], *, page: str, today: date, error: str | None = None, log_url: str | None = None
) -> str:
    dailies = [d for d in digests if d["mode"] == "daily"]
    body = _weekly_body(digests, today) if page == "weekly" else _section_body(digests, page)
    parts = [_header(page, root=""), _banner(dailies[0] if dailies else None, today, error, log_url), body, _archive_footer(digests)]
    return _page(f"{SITE_TITLE} · {NAV_LABELS[page]}", "\n".join(p for p in parts if p), css_href="style.css")


def render_archive(digest: dict[str, Any]) -> str:
    label = _pretty_date(digest["run"]) + (" · weekly" if digest["mode"] == "weekly" else "")
    body = _header(None, root="../") + f"<h2>{label}</h2>" + render_digest_body(digest)
    return _page(f"{SITE_TITLE} · {digest['run']}", body, css_href="../style.css")


def render_site(
    digests: list[dict[str, Any]], docs: Path, *, today: date, error: str | None = None, log_url: str | None = None
) -> None:
    (docs / "archive").mkdir(parents=True, exist_ok=True)
    (docs / "style.css").write_text(STYLE.strip() + "\n")
    (docs / ".nojekyll").touch()
    for page, filename in PAGES.items():
        (docs / filename).write_text(render_page(digests, page=page, today=today, error=error, log_url=log_url))
    for d in digests:
        (docs / "archive" / _archive_name(d)).write_text(render_archive(d))
