"""Static site rendering: one page per section (A, B, weekly), archive pages, stylesheet."""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from digest.watch import watched_names

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
FEED_MIN_SCORE = 50  # feed entries list papers at or above this score, plus watched ones
FEED_ENTRIES = 30
SITE_TITLE = "Quantum Optics Digest"


@dataclass(frozen=True)
class Site:
    """Where the site lives; needed for absolute feed links and the feedback issue links."""

    url: str | None = None  # e.g. https://focix.github.io/quantum-optics-digest/
    repo: str | None = None  # e.g. Focix/quantum-optics-digest

    @property
    def base(self) -> str:
        return self.url.rstrip("/") + "/" if self.url else ""

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
.watch { color:var(--accent); margin-right:.35rem; font-size:.9em; }
.fb { margin-left:.5rem; white-space:nowrap; }
.fb a { text-decoration:none; opacity:.55; filter:grayscale(1); }
.fb a:hover { opacity:1; filter:none; }
footer { margin-top:3rem; color:var(--muted); font-size:.9rem; }
footer p a { color:inherit; }
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


def _watched(item: dict[str, Any]) -> list[str]:
    return watched_names(list(item.get("tags") or []))


def _watch(item: dict[str, Any]) -> str:
    names = _watched(item)
    if not names:
        return ""
    return f'<span class="watch" title="watchlist: {_esc(", ".join(names))}">★</span>'


def feedback_url(item: dict[str, Any], verdict: str, *, site: Site, run: str | None = None) -> str | None:
    """A GitHub 'new issue' link prefilled so scripts/feedback.py can parse it back."""
    if not site.repo:
        return None
    lines = [
        f"id: {item['id']}",
        f"verdict: {verdict}",
        f"section: {item.get('section') or ''}",
        f"score: {item.get('score') if item.get('score') is not None else ''}",
        f"run: {run or ''}",
        f"title: {item['title']}",
        f"link: {_url(item)}",
        "",
        "Note (optional):",
        "",
    ]
    mark = "👍" if verdict == "up" else "👎"
    query = urlencode({"title": f"{mark} {item['id']} {item['title']}"[:200], "labels": f"feedback,{verdict}", "body": "\n".join(lines)})
    return f"https://github.com/{site.repo}/issues/new?{query}"


def _feedback(item: dict[str, Any], *, site: Site, run: str | None) -> str:
    up = feedback_url(item, "up", site=site, run=run)
    down = feedback_url(item, "down", site=site, run=run)
    if not up or not down:
        return ""
    return (
        f'<span class="fb"><a href="{_esc(up)}" title="relevant, more like this">👍</a> '
        f'<a href="{_esc(down)}" title="not relevant, less like this">👎</a></span>'
    )


def _score(item: dict[str, Any]) -> str:
    score = item.get("score")
    return f'<span class="score">{score}</span>' if score is not None else ""


def _meta(item: dict[str, Any]) -> list[str]:
    meta = [_authors(item.get("authors", [])), item.get("submitted", "")]
    cite = item.get("cite") or {}
    if cite.get("citationCount"):
        meta.append(f"{cite['citationCount']} citations")
    if cite.get("venue"):
        meta.append(cite["venue"])
    names = _watched(item)
    if names:
        meta.append("watchlist: " + ", ".join(names))
    return [m for m in meta if m]


def _paper_li(item: dict[str, Any], *, site: Site, run: str | None) -> str:
    score = item.get("score")
    cls = ' class="read"' if isinstance(score, int) and score >= 80 else ""
    why = f'<p class="why">{_esc(item["why"])}</p>' if item.get("why") else ""
    return (
        f"<li{cls}>{_score(item)}{_kind(item)}{_watch(item)}<span class=\"title\"><a href=\"{_esc(_url(item))}\">"
        f"{_esc(item['title'])}</a></span>"
        f"<div class=\"meta\">{_esc(' · '.join(_meta(item)))}{_feedback(item, site=site, run=run)}</div>{why}</li>"
    )


def _title_li(item: dict[str, Any], *, site: Site, run: str | None) -> str:
    return (
        f"<li>{_score(item)}{_kind(item)}{_watch(item)}<a href=\"{_esc(_url(item))}\">{_esc(item['title'])}</a>"
        f"{_feedback(item, site=site, run=run)}</li>"
    )


def _titles_details(summary: str, items: list[dict[str, Any]], *, site: Site, run: str | None) -> str:
    inner = "".join(_title_li(i, site=site, run=run) for i in items)
    return f"<details><summary>{_esc(summary)}</summary><ul class=\"titles\">{inner}</ul></details>"


def split_top(items: list[dict[str, Any]], top_n: int = TOP_N) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """The first top_n plus every watched paper get a why-line; the rest are titles-only."""
    top = items[:top_n] + [i for i in items[top_n:] if _watched(i)]
    rest = [i for i in items[top_n:] if not _watched(i)]
    return top, rest


def _papers(items: list[dict[str, Any]], *, site: Site, run: str | None, top_n: int = TOP_N) -> str:
    """Top-N (and watched) with why-lines, the rest collapsed titles-only. Nothing dropped."""
    if not items:
        return '<p class="meta">No new papers.</p>'
    top, rest = split_top(items, top_n)
    out = '<ol class="papers">' + "".join(_paper_li(i, site=site, run=run) for i in top) + "</ol>"
    if rest:
        out += _titles_details(f"also matched ({len(rest)} more)", rest, site=site, run=run)
    return out


def _items(digest: dict[str, Any], section: str) -> list[dict[str, Any]]:
    return [i for i in digest.get("items", []) if i.get("section") == section]


def _unranked_note(digest: dict[str, Any]) -> str:
    if digest.get("ranked", True):
        return ""
    return '<p class="meta">unranked: the model output was rejected, showing the raw candidate list.</p>'


def render_digest_body(digest: dict[str, Any], *, site: Site = Site()) -> str:
    """All sections of one digest (archive pages)."""
    run = str(digest.get("run") or "")
    parts = [_unranked_note(digest)]
    present = {i.get("section", "A") for i in digest.get("items", [])}
    if not present:
        parts.append('<p class="meta">No new papers.</p>')
    for key in SECTION_ORDER + sorted(present - set(SECTION_ORDER)):
        if key not in present:
            continue
        items = _items(digest, key)
        parts.append(f"<h3>{_esc(SECTION_TITLES.get(key, str(key)))} <span class=\"meta\">({len(items)})</span></h3>")
        if key == "computing":
            parts.append(_titles_details(f"{len(items)} papers", items, site=site, run=run))
        else:
            parts.append(_papers(items, site=site, run=run))
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


def _page(title: str, body: str, *, css_href: str, root: str) -> str:
    return (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{_esc(title)}</title>\n<link rel=\"stylesheet\" href=\"{css_href}\">\n"
        f"<link rel=\"alternate\" type=\"application/atom+xml\" title=\"{_esc(SITE_TITLE)}\" href=\"{root}feed.xml\">\n"
        "</head>\n<body>\n<main>\n"
        f"{body}\n</main>\n</body>\n</html>\n"
    )


def _archive_name(digest: dict[str, Any]) -> str:
    suffix = "" if digest["mode"] == "daily" else f"-{digest['mode']}"
    return f"{digest['run']}{suffix}.html"


def _archive_footer(digests: list[dict[str, Any]], *, site: Site) -> str:
    links = "".join(
        f"<li><a href=\"archive/{_archive_name(d)}\">{d['run']}{' (weekly)' if d['mode'] == 'weekly' else ''}</a></li>"
        for d in digests
    )
    about = '<p><a href="feed.xml">Atom feed</a>'
    if site.repo:
        about += (
            f' · 👍 👎 open a prefilled issue in <a href="https://github.com/{_esc(site.repo)}/issues?q=label%3Afeedback">'
            f"{_esc(site.repo)}</a>; the ranking prompt reads them back as calibration examples."
        )
    return f"<footer><h2>Archive</h2><ul>{links}</ul>{about}</p></footer>"


def _day_details(d: dict[str, Any], items: list[dict[str, Any]], *, site: Site) -> str:
    top = next((i["title"] for i in items if i.get("score") is not None), None)
    hint = f" · {_esc(top)}" if top else ""
    return (
        f"<details class=\"day\"><summary>{_pretty_date(d['run'])} · {len(items)} papers{hint}</summary>"
        f"{_unranked_note(d)}{_papers(items, site=site, run=d['run'])}</details>"
    )


def _section_body(digests: list[dict[str, Any]], section: str, *, site: Site) -> str:
    dailies = [d for d in digests if d["mode"] == "daily"]
    parts = [f"<h2>{_esc(SECTION_TITLES[section])}</h2>"]
    if dailies:
        latest = dailies[0]
        parts.append(f"<h3>Today · {_pretty_date(latest['run'])}</h3>")
        parts.append(_unranked_note(latest) + _papers(_items(latest, section), site=site, run=latest["run"]))
    previous = dailies[1 : 1 + PREVIOUS_DAYS]
    if previous:
        parts.append("<h2>Previous days</h2>")
        parts.extend(_day_details(d, _items(d, section), site=site) for d in previous)
    return "\n".join(parts)


def _weekly_body(digests: list[dict[str, Any]], today: date, *, site: Site) -> str:
    weeklies = [d for d in digests if d["mode"] == "weekly"]
    dailies = [d for d in digests if d["mode"] == "daily"]
    parts = [f"<h2>{_esc(SECTION_TITLES['weekly'])}</h2>"]
    if weeklies:
        latest = weeklies[0]
        parts.append(f"<h3>Week ending {_pretty_date(latest['run'])}</h3>")
        parts.append(_unranked_note(latest) + _papers(_items(latest, "weekly"), site=site, run=latest["run"]))
        since = date.fromisoformat(latest["run"])
    else:
        parts.append('<p class="meta">No weekly digest yet. The first one comes on Saturday.</p>')
        since = today - timedelta(days=7)
    pool = [i for d in dailies if date.fromisoformat(d["run"]) > since for i in _items(d, "computing")]
    if pool:
        parts.append(f"<h3>Pool for the next weekly digest <span class=\"meta\">({len(pool)})</span></h3>")
        parts.append(_titles_details(f"{len(pool)} computing papers since {since.isoformat()}", pool, site=site, run=None))
    if len(weeklies) > 1:
        parts.append("<h2>Previous weeks</h2>")
        parts.extend(_day_details(d, _items(d, "weekly"), site=site) for d in weeklies[1 : 1 + PREVIOUS_DAYS])
    return "\n".join(parts)


def render_page(
    digests: list[dict[str, Any]],
    *,
    page: str,
    today: date,
    error: str | None = None,
    log_url: str | None = None,
    site: Site = Site(),
) -> str:
    dailies = [d for d in digests if d["mode"] == "daily"]
    body = _weekly_body(digests, today, site=site) if page == "weekly" else _section_body(digests, page, site=site)
    parts = [
        _header(page, root=""),
        _banner(dailies[0] if dailies else None, today, error, log_url),
        body,
        _archive_footer(digests, site=site),
    ]
    return _page(f"{SITE_TITLE} · {NAV_LABELS[page]}", "\n".join(p for p in parts if p), css_href="style.css", root="")


def render_archive(digest: dict[str, Any], *, site: Site = Site()) -> str:
    label = _pretty_date(digest["run"]) + (" · weekly" if digest["mode"] == "weekly" else "")
    body = _header(None, root="../") + f"<h2>{label}</h2>" + render_digest_body(digest, site=site)
    return _page(f"{SITE_TITLE} · {digest['run']}", body, css_href="../style.css", root="../")


# -- Atom feed -------------------------------------------------------------


def _feed_entry(digest: dict[str, Any], *, site: Site) -> str:
    run = digest["run"]
    link = f"{site.base}archive/{_archive_name(digest)}"
    picked: list[tuple[str, list[dict[str, Any]]]] = []
    for key in SECTION_ORDER:
        if key == "computing":
            continue
        items = [i for i in _items(digest, key) if (i.get("score") or 0) >= FEED_MIN_SCORE or _watched(i)]
        if items:
            picked.append((key, items))
    shown = [i for _, items in picked for i in items]
    n_read = sum(1 for i in shown if (i.get("score") or 0) >= 80)
    n_title = sum(1 for i in shown if FEED_MIN_SCORE <= (i.get("score") or 0) < 80)
    mode = " · weekly" if digest["mode"] == "weekly" else ""
    title = f"{_pretty_date(run)}{mode}: {n_read} to read, {n_title} worth the title"
    body = []
    for key, items in picked:
        body.append(f"<h3>{_esc(SECTION_TITLES[key])}</h3><ul>")
        for i in items:
            meta = " · ".join(_meta(i))
            why = f"<br>{_esc(i['why'])}" if i.get("why") else ""
            star = "★ " if _watched(i) else ""
            body.append(
                f"<li>{star}<b>{i.get('score', '')}</b> {_esc(i.get('kind') or '')} "
                f"<a href=\"{_esc(_url(i))}\">{_esc(i['title'])}</a><br><small>{_esc(meta)}</small>{why}</li>"
            )
        body.append("</ul>")
    if not body:
        body.append("<p>Nothing scored above the threshold today.</p>")
    body.append(f'<p><a href="{_esc(link)}">Full digest</a></p>')
    updated = str(digest.get("generated") or f"{run}T06:00:00+00:00")
    return (
        f"<entry><title>{_esc(title)}</title><id>{_esc(link)}</id><link href=\"{_esc(link)}\"/>"
        f"<updated>{_esc(updated)}</updated>"
        f"<content type=\"html\">{_esc(''.join(body))}</content></entry>"
    )


def render_feed(digests: list[dict[str, Any]], *, site: Site) -> str:
    """Atom feed, one entry per digest run, newest first; only scored-or-watched papers inside."""
    entries = [_feed_entry(d, site=site) for d in digests[:FEED_ENTRIES]]
    updated = str(digests[0].get("generated")) if digests else datetime.now(timezone.utc).isoformat(timespec="seconds")
    self_link = f"{site.base}feed.xml"
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<feed xmlns="http://www.w3.org/2005/Atom">\n'
        f"<title>{_esc(SITE_TITLE)}</title><id>{_esc(site.base or self_link)}</id>"
        f"<link href=\"{_esc(site.base)}\"/><link rel=\"self\" href=\"{_esc(self_link)}\"/>"
        f"<updated>{_esc(updated)}</updated>\n" + "\n".join(entries) + "\n</feed>\n"
    )


def render_site(
    digests: list[dict[str, Any]],
    docs: Path,
    *,
    today: date,
    error: str | None = None,
    log_url: str | None = None,
    site: Site = Site(),
) -> None:
    (docs / "archive").mkdir(parents=True, exist_ok=True)
    (docs / "style.css").write_text(STYLE.strip() + "\n")
    (docs / ".nojekyll").touch()
    for page, filename in PAGES.items():
        (docs / filename).write_text(
            render_page(digests, page=page, today=today, error=error, log_url=log_url, site=site)
        )
    (docs / "feed.xml").write_text(render_feed(digests, site=site))
    for d in digests:
        (docs / "archive" / _archive_name(d)).write_text(render_archive(d, site=site))
