"""Static site rendering: index page, archive pages and stylesheet."""

from __future__ import annotations

import html
from datetime import date, timedelta
from pathlib import Path
from typing import Any

SECTION_TITLES = {
    "A": "A · Superconducting artificial atoms",
    "B": "B · Quantum optics on other platforms",
    "C": "C · Dark matter with superconducting devices",
    "computing": "Superconducting quantum computing (held for Saturday)",
    "weekly": "This week in superconducting quantum computing",
}
SECTION_ORDER = ["A", "B", "C", "weekly", "computing"]
TOP_N = 10
PREVIOUS_DAYS = 14
SITE_TITLE = "Quantum Optics Digest"

STYLE = """
:root { --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6b66; --line:#e2e0d9; --accent:#8a3b12; --hi:#fff4e5; --warn:#b3261e; --warnbg:#fde7e5; }
@media (prefers-color-scheme: dark) { :root { --bg:#161614; --fg:#ebe8e0; --muted:#9c9a92; --line:#33322e; --accent:#f0a06a; --hi:#2a2118; --warn:#ff8a80; --warnbg:#3a1c1a; } }
html { color-scheme: light dark; }
body { margin:0; padding:1.5rem 1rem 3rem; background:var(--bg); color:var(--fg); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:52rem; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .25rem; }
h1 a { color:inherit; text-decoration:none; }
h2 { font-size:1.25rem; margin:2rem 0 .5rem; border-bottom:1px solid var(--line); padding-bottom:.25rem; }
h3 { font-size:1.05rem; margin:1.25rem 0 .5rem; color:var(--accent); }
.sub { color:var(--muted); margin:0; }
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


def _paper_li(item: dict[str, Any]) -> str:
    score = item.get("score")
    cls = ' class="read"' if isinstance(score, int) and score >= 80 else ""
    score_html = f'<span class="score">{score}</span>' if score is not None else ""
    meta = [_authors(item.get("authors", [])), item.get("submitted", "")]
    cite = item.get("cite") or {}
    if cite.get("citationCount"):
        meta.append(f"{cite['citationCount']} citations")
    if cite.get("venue"):
        meta.append(cite["venue"])
    why = f'<p class="why">{_esc(item["why"])}</p>' if item.get("why") else ""
    return (
        f"<li{cls}>{score_html}<span class=\"title\"><a href=\"{_esc(_url(item))}\">"
        f"{_esc(item['title'])}</a></span>"
        f"<div class=\"meta\">{_esc(' · '.join(m for m in meta if m))}</div>{why}</li>"
    )


def _title_li(item: dict[str, Any]) -> str:
    score = item.get("score")
    score_html = f'<span class="score">{score}</span>' if score is not None else ""
    return f"<li>{score_html}<a href=\"{_esc(_url(item))}\">{_esc(item['title'])}</a></li>"


def _section(title: str, items: list[dict[str, Any]], *, top_n: int, collapsed: bool) -> str:
    if not items:
        return ""
    top, rest = items[:top_n], items[top_n:]
    parts = [f"<h3>{_esc(title)} <span class=\"meta\">({len(items)})</span></h3>"]
    if collapsed:
        parts.append(f"<details><summary>{len(items)} papers</summary><ul class=\"titles\">")
        parts.extend(_title_li(i) for i in items)
        parts.append("</ul></details>")
        return "\n".join(parts)
    parts.append('<ol class="papers">' + "".join(_paper_li(i) for i in top) + "</ol>")
    if rest:
        parts.append(f"<details><summary>also matched ({len(rest)} more)</summary><ul class=\"titles\">")
        parts.extend(_title_li(i) for i in rest)
        parts.append("</ul></details>")
    return "\n".join(parts)


def _group(digest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in digest.get("items", []):
        groups.setdefault(item.get("section", "A"), []).append(item)
    return groups


def render_digest_body(digest: dict[str, Any], *, top_n: int = TOP_N) -> str:
    parts: list[str] = []
    if not digest.get("ranked", True):
        parts.append('<p class="meta">unranked: the model output was rejected, showing the raw candidate list.</p>')
    groups = _group(digest)
    if not groups:
        parts.append('<p class="meta">No new papers.</p>')
    for key in SECTION_ORDER + [k for k in groups if k not in SECTION_ORDER]:
        if key in groups:
            parts.append(_section(SECTION_TITLES.get(key, key), groups[key], top_n=top_n, collapsed=(key == "computing")))
    return "\n".join(parts)


def _pretty_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return d.strftime("%A %-d %B %Y")


def previous_working_day(today: date) -> date:
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _banner(latest_daily: dict[str, Any] | None, today: date, error: str | None, log_url: str | None = None) -> str:
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
    link = f' <a href="{_esc(log_url)}">run log</a>' if log_url else ""
    return f'<div class="banner"><strong>Problem.</strong> {body}{link}</div>'


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


def render_index(
    digests: list[dict[str, Any]], *, today: date, error: str | None = None, log_url: str | None = None
) -> str:
    dailies = [d for d in digests if d["mode"] == "daily"]
    weeklies = [d for d in digests if d["mode"] == "weekly"]
    latest = dailies[0] if dailies else None
    latest_weekly = weeklies[0] if weeklies else None

    parts = [
        f"<h1><a href=\"./\">{SITE_TITLE}</a></h1>",
        '<p class="sub">New arXiv papers on superconducting artificial atoms, quantum optics and dark matter searches, ranked each weekday morning.</p>',
        _banner(latest, today, error, log_url),
    ]
    if latest:
        parts.append(f"<h2>Today · {_pretty_date(latest['run'])}</h2>")
        parts.append(render_digest_body(latest))
    if latest_weekly and date.fromisoformat(latest_weekly["run"]) >= today - timedelta(days=7):
        parts.append(f"<h2>This week · {_pretty_date(latest_weekly['run'])}</h2>")
        parts.append(render_digest_body(latest_weekly))

    previous = dailies[1 : 1 + PREVIOUS_DAYS]
    if previous:
        parts.append("<h2>Previous days</h2>")
        for d in previous:
            n = len(d.get("items", []))
            top = next((i["title"] for i in d.get("items", []) if i.get("score") is not None), None)
            hint = f" · {_esc(top)}" if top else ""
            parts.append(
                f"<details class=\"day\"><summary>{_pretty_date(d['run'])} · {n} papers{hint}</summary>"
                f"{render_digest_body(d)}</details>"
            )

    parts.append("<footer><h2>Archive</h2><ul>")
    for d in digests:
        label = d["run"] + (" (weekly)" if d["mode"] == "weekly" else "")
        parts.append(f"<li><a href=\"archive/{_archive_name(d)}\">{label}</a></li>")
    parts.append("</ul></footer>")
    return _page(SITE_TITLE, "\n".join(p for p in parts if p), css_href="style.css")


def render_archive(digest: dict[str, Any]) -> str:
    label = f"{_pretty_date(digest['run'])}" + (" · weekly" if digest["mode"] == "weekly" else "")
    body = f"<h1><a href=\"../\">{SITE_TITLE}</a></h1><h2>{label}</h2>" + render_digest_body(digest)
    return _page(f"{SITE_TITLE} · {digest['run']}", body, css_href="../style.css")


def render_site(
    digests: list[dict[str, Any]], docs: Path, *, today: date, error: str | None = None, log_url: str | None = None
) -> None:
    (docs / "archive").mkdir(parents=True, exist_ok=True)
    (docs / "style.css").write_text(STYLE.strip() + "\n")
    (docs / "index.html").write_text(render_index(digests, today=today, error=error, log_url=log_url))
    (docs / ".nojekyll").touch()
    for d in digests:
        (docs / "archive" / _archive_name(d)).write_text(render_archive(d))
