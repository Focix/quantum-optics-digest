from datetime import date, timedelta
from pathlib import Path
from typing import Any

from digest.render import Site, render_archive, render_feed, render_page, render_site


def item(id: str, section: str, score: int | None, why: str | None = "does a thing", kind: str | None = "E") -> dict[str, Any]:
    return {
        "id": id, "title": f"Title {id}", "authors": ["A One", "B Two", "C Three", "D Four"],
        "abstract": "abs", "categories": ["quant-ph"], "submitted": "2026-09-09", "pool": section,
        "tags": [], "cite": {"citationCount": 2, "venue": "PRL"} if id == "a1" else None,
        "section": section, "score": score, "why": why, "kind": kind,
    }


def digest(run: str, items: list[dict[str, Any]], mode: str = "daily", status: dict[str, Any] | None = None, ranked: bool = True) -> dict[str, Any]:
    return {"run": run, "mode": mode, "generated": "x", "ranked": ranked, "status": status or {}, "items": items}


TODAY = date(2026, 9, 10)


def test_section_page_shows_only_its_section_with_top_ten_and_collapsed_rest() -> None:
    a_items = [item(f"a{i}", "A", 95 - i) for i in range(12)]
    b_items = [item("b1", "B", 70, kind="T")]
    digests = [digest("2026-09-10", a_items + b_items)]

    a_page = render_page(digests, page="A", today=TODAY)
    assert "2026-09-10" in a_page
    assert 'href="https://arxiv.org/abs/a1"' in a_page
    assert "A One, B Two, C Three et al." in a_page
    assert "does a thing" in a_page
    assert "2 citations" in a_page and "PRL" in a_page
    assert a_page.index("Title a0") < a_page.index("also matched") < a_page.index("Title a10")
    assert "Title b1" not in a_page
    assert 'class="kind kind-E"' in a_page
    assert 'class="banner"' not in a_page
    # navigation between the three pages
    assert 'href="b.html"' in a_page and 'href="weekly.html"' in a_page

    b_page = render_page(digests, page="B", today=TODAY)
    assert "Title b1" in b_page and "Title a0" not in b_page
    assert 'class="kind kind-T"' in b_page


def test_banner_on_every_page_for_error_and_stale() -> None:
    err = [digest("2026-09-10", [], status={"error": "arXiv 503 on pool A"})]
    for page in ("A", "B", "weekly"):
        html = render_page(err, page=page, today=TODAY)
        assert 'class="banner"' in html and "arXiv 503 on pool A" in html

    stale = render_page([digest("2026-09-07", [])], page="A", today=TODAY)  # Monday's digest on Thursday
    assert "stale" in stale
    friday_ok = render_page([digest("2026-09-11", [])], page="A", today=date(2026, 9, 14))
    assert 'class="banner"' not in friday_ok
    explicit = render_page([digest("2026-09-10", [])], page="A", today=TODAY, error="fetch.py exited 1", log_url="https://x/log")
    assert "fetch.py exited 1" in explicit and 'href="https://x/log"' in explicit


def test_unranked_digest_lists_candidates_without_scores() -> None:
    html = render_page([digest("2026-09-10", [item("a1", "A", None, None, None)], ranked=False)], page="A", today=TODAY)
    assert "Title a1" in html and "unranked" in html


def test_weekly_page_shows_latest_weekly_and_upcoming_pool() -> None:
    digests = [
        digest("2026-09-12", [item("w1", "weekly", 88)], mode="weekly"),
        digest("2026-09-14", [item("c1", "computing", 30), item("a1", "A", 90)]),
        digest("2026-09-05", [item("w0", "weekly", 70)], mode="weekly"),
    ]
    html = render_page(digests, page="weekly", today=date(2026, 9, 14))
    assert "Title w1" in html
    assert "Title c1" in html          # computing items after the last weekly digest
    assert "Title a1" not in html
    assert html.index("Title w1") < html.index("Title w0")   # previous weekly digests below, collapsed


def test_previous_days_archive_and_site_files(tmp_path: Path) -> None:
    digests = [digest("2026-09-12", [item("w1", "weekly", 88)], mode="weekly")]
    for day in range(1, 20):
        run = date(2026, 9, 12) - timedelta(days=day)
        digests.append(digest(run.isoformat(), [item(f"p{day}", "A", 50), item(f"q{day}", "B", 40)]))
    html = render_page(digests, page="A", today=date(2026, 9, 12))
    assert "Title p1" in html
    assert "Title p14" in html and "Title p16" not in html
    assert "Title q1" not in html
    assert 'href="archive/2026-08-27.html"' in html

    archive = render_archive(digests[-1])
    assert "Title p19" in archive and "Title q19" in archive

    docs = tmp_path / "docs"
    render_site(digests, docs, today=date(2026, 9, 12))
    for name in ("index.html", "b.html", "weekly.html", "style.css", "archive/2026-09-12-weekly.html", "archive/2026-08-24.html"):
        assert (docs / name).exists(), name


SITE = Site(url="https://focix.github.io/quantum-optics-digest/", repo="Focix/quantum-optics-digest")


def test_watched_paper_escapes_the_collapsed_list_and_gets_a_star() -> None:
    items = [item(f"a{i}", "A", 95 - i) for i in range(12)]
    items[11]["tags"] = ["platform:sc", "watch:A. Wallraff"]
    html = render_page([digest("2026-09-10", items)], page="A", today=TODAY, site=SITE)
    assert html.index("Title a11") < html.index("also matched") < html.index("Title a10")
    assert 'class="watch" title="watchlist: A. Wallraff"' in html
    assert "watchlist: A. Wallraff" in html
    assert "also matched (1 more)" in html


def test_feedback_links_present_only_with_repo() -> None:
    d = [digest("2026-09-10", [item("a1", "A", 90), item("b1", "B", 10)])]
    html = render_page(d, page="A", today=TODAY, site=SITE)
    assert "issues/new?" in html and "labels=feedback%2Cup" in html and "labels=feedback%2Cdown" in html
    assert "run%3A+2026-09-10" in html
    assert 'href="feed.xml"' in html
    plain = render_page(d, page="A", today=TODAY)
    assert "issues/new?" not in plain


def test_feed_lists_scored_and_watched_papers(tmp_path: Path) -> None:
    items = [item("a1", "A", 90), item("a2", "A", 55), item("a3", "A", 20), item("b1", "B", 10, kind="T"), item("c1", "computing", 70)]
    items[3]["tags"] = ["watch:Someone"]
    digests = [digest("2026-09-10", items), digest("2026-09-12", [item("w1", "weekly", 85)], mode="weekly")]
    feed = render_feed(digests, site=SITE)
    assert feed.startswith('<?xml version="1.0"')
    assert '<link rel="self" href="https://focix.github.io/quantum-optics-digest/feed.xml"/>' in feed
    assert feed.count("<entry>") == 2
    assert "1 to read, 1 worth the title" in feed
    assert "Title a1" in feed and "Title a2" in feed and "Title b1" in feed
    assert "Title a3" not in feed and "Title c1" not in feed
    assert "archive/2026-09-10.html" in feed and "archive/2026-09-12-weekly.html" in feed
    assert "does a thing" in feed

    docs = tmp_path / "docs"
    render_site(digests, docs, today=date(2026, 9, 12), site=SITE)
    assert (docs / "feed.xml").exists()
    assert 'type="application/atom+xml"' in (docs / "index.html").read_text()
    assert 'href="../feed.xml"' in (docs / "archive" / "2026-09-10.html").read_text()
    import xml.etree.ElementTree as ET
    ET.fromstring((docs / "feed.xml").read_text())  # well-formed


def test_zotero_button_data_files_and_script(tmp_path: Path) -> None:
    items = [item("a1", "A", 90), item("c1", "computing", 30)]
    digests = [digest("2026-09-14", items), digest("2026-09-12", [item("w1", "weekly", 85)], mode="weekly")]
    html = render_page(digests, page="A", today=date(2026, 9, 14), site=SITE)
    assert '<button type="button" class="zot" data-id="a1" data-src="2026-09-14"' in html
    assert 'class="zot-setup"' in html and '<dialog id="zot-dialog">' in html
    assert '<body data-root="">' in html and '<script src="zotero.js" defer>' in html
    weekly = render_page(digests, page="weekly", today=date(2026, 9, 14), site=SITE)
    assert 'data-id="w1" data-src="2026-09-12-weekly"' in weekly
    assert 'data-id="c1" data-src="2026-09-14"' in weekly      # pool items point at their own day's file
    assert "_data" not in weekly

    docs = tmp_path / "docs"
    render_site(digests, docs, today=date(2026, 9, 14), site=SITE)
    assert (docs / "zotero.js").exists()
    import json
    data = json.loads((docs / "data" / "2026-09-14.json").read_text())
    assert data["items"]["a1"]["abstract"] == "abs" and data["items"]["a1"]["authors"][0] == "A One"
    assert set(data["items"]) == {"a1", "c1"}
    assert (docs / "data" / "2026-09-12-weekly.json").exists()
    archive = (docs / "archive" / "2026-09-14.html").read_text()
    assert '<body data-root="../">' in archive and '<script src="../zotero.js" defer>' in archive
