from datetime import date, timedelta
from pathlib import Path
from typing import Any

from digest.render import Site, render_archive, render_feed, render_page, render_site


def item(
    id: str,
    section: str,
    score: int | None,
    why: str | None = "does a thing",
    kind: str | None = "E",
    eli5: dict[str, str] | None = None,
) -> dict[str, Any]:
    return {
        "id": id, "title": f"Title {id}", "authors": ["A One", "B Two", "C Three", "D Four"],
        "abstract": "abs", "categories": ["quant-ph"], "submitted": "2026-09-09", "pool": section,
        "tags": [], "cite": {"citationCount": 2, "venue": "PRL"} if id == "a1" else None,
        "section": section, "score": score, "why": why, "kind": kind, "eli5": eli5,
    }


def digest(run: str, items: list[dict[str, Any]], mode: str = "weekly", status: dict[str, Any] | None = None, ranked: bool = True) -> dict[str, Any]:
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
    # navigation between the four pages
    assert 'href="b.html"' in a_page and 'href="c.html"' in a_page and 'href="weekly.html"' in a_page
    assert "This week · Thursday 10 September 2026" in a_page

    b_page = render_page(digests, page="B", today=TODAY)
    assert "Title b1" in b_page and "Title a0" not in b_page
    assert 'class="kind kind-T"' in b_page


def test_every_page_banners_the_newest_weekly_error_and_staleness() -> None:
    err = [digest("2026-09-28", [], status={"error": "arXiv 503 on pool A"})]
    for page in ("A", "B", "C", "computing"):
        html = render_page(err, page=page, today=date(2026, 9, 28))
        assert 'class="banner"' in html and "arXiv 503 on pool A" in html

    weekly = [digest("2026-09-21", [])]
    # The week until the next Monday, and that Monday's own day in case it lands late.
    for today in (date(2026, 9, 22), date(2026, 9, 28), date(2026, 9, 29)):
        assert 'class="banner"' not in render_page(weekly, page="A", today=today)
    assert "stale" in render_page(weekly, page="A", today=date(2026, 9, 30))

    explicit = render_page(err, page="A", today=date(2026, 9, 28), error="fetch.py exited 1", log_url="https://x/log")
    assert "fetch.py exited 1" in explicit and 'href="https://x/log"' in explicit


def test_an_old_dailys_trouble_no_longer_reaches_the_banner() -> None:
    digests = [
        digest("2026-09-28", [item("a1", "A", 90)]),
        digest("2026-09-28", [], mode="daily", status={"error": "arXiv 503 on pool A"}),
    ]
    assert 'class="banner"' not in render_page(digests, page="A", today=date(2026, 9, 28))


def test_before_the_first_weekly_the_body_explains_and_old_dailies_stay_listed() -> None:
    html = render_page([digest("2026-09-10", [item("a1", "A", 90)], mode="daily")], page="A", today=TODAY)
    assert "No weekly digest yet" in html
    assert 'class="banner"' not in html  # no "No digest has been generated yet" on top of it
    assert "Thursday 10 September 2026 (daily)" in html and "Title a1" in html


def test_archive_page_carries_its_own_runs_failure() -> None:
    d = digest("2026-09-19", [item("a1", "computing", 90)], status={"error": "journal search failed: 429"})
    html = render_archive(d)
    assert 'class="banner"' in html and "journal search failed: 429" in html
    assert 'class="banner"' not in render_archive(digest("2026-09-18", [item("a1", "A", 90)], mode="daily"))


def test_unranked_digest_lists_candidates_without_scores() -> None:
    html = render_page([digest("2026-09-10", [item("a1", "A", None, None, None)], ranked=False)], page="A", today=TODAY)
    assert "Title a1" in html and "unranked" in html


def test_computing_page_shows_ranked_weeks_not_the_held_daily_lists() -> None:
    digests = [
        digest("2026-09-28", [item("k1", "computing", 88), item("a2", "A", 90)]),
        digest("2026-09-25", [item("c1", "computing", 30), item("a1", "A", 90)], mode="daily"),
        digest("2026-09-19", [item("k0", "computing", 70)]),
    ]
    html = render_page(digests, page="computing", today=date(2026, 9, 28))
    assert "Title k1" in html and "Title k0" in html
    assert "Title c1" not in html  # held for the weekly that ranked it
    assert "Title a1" not in html and "Title a2" not in html
    assert html.index("Title k1") < html.index("Week to Saturday 19 September 2026") < html.index("Title k0")


def test_foundations_page_shows_section_c() -> None:
    digests = [digest("2026-09-28", [item("f1", "C", 84, kind="T"), item("a1", "A", 90)])]
    html = render_page(digests, page="C", today=date(2026, 9, 28))
    assert "Foundations of quantum mechanics" in html
    assert "Title f1" in html and "Title a1" not in html
    assert 'href="c.html" class="current"' in html


def test_previous_days_archive_and_site_files(tmp_path: Path) -> None:
    digests = [digest("2026-09-12", [item("w1", "computing", 88)])]
    for day in range(1, 20):
        run = date(2026, 9, 12) - timedelta(days=day)
        digests.append(digest(run.isoformat(), [item(f"p{day}", "A", 50), item(f"q{day}", "B", 40)], mode="daily"))
    html = render_page(digests, page="A", today=date(2026, 9, 12))
    assert "No new papers" in html  # this week had no A papers; older digests still listed
    assert "Title p1" in html
    assert "Title p14" in html and "Title p15" not in html
    assert "Title q1" not in html
    assert 'href="archive/2026-08-27.html"' in html

    archive = render_archive(digests[-1])
    assert "Title p19" in archive and "Title q19" in archive

    docs = tmp_path / "docs"
    render_site(digests, docs, today=date(2026, 9, 12))
    for name in ("index.html", "b.html", "c.html", "weekly.html", "style.css", "archive/2026-09-12-weekly.html", "archive/2026-08-24.html"):
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
    weekly = [item("k1", "computing", 85), item("f1", "C", 60, kind="T")]
    digests = [digest("2026-09-10", items, mode="daily"), digest("2026-09-12", weekly)]
    feed = render_feed(digests, site=SITE)
    assert feed.startswith('<?xml version="1.0"')
    assert '<link rel="self" href="https://focix.github.io/quantum-optics-digest/feed.xml"/>' in feed
    assert feed.count("<entry>") == 2
    assert "1 to read, 1 worth the title" in feed
    assert "Title a1" in feed and "Title a2" in feed and "Title b1" in feed
    assert "Title a3" not in feed and "Title c1" not in feed  # a daily's computing list was held
    assert "Title k1" in feed and "Title f1" in feed
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
    digests = [
        digest("2026-09-28", [item("a1", "A", 90), item("k1", "computing", 30)]),
        digest("2026-09-25", [item("d1", "A", 85)], mode="daily"),
    ]
    html = render_page(digests, page="A", today=date(2026, 9, 28), site=SITE)
    assert '<button type="button" class="zot" data-id="a1" data-src="2026-09-28-weekly"' in html
    assert 'data-id="d1" data-src="2026-09-25"' in html  # an old daily points at its own file
    assert 'class="zot-setup"' in html and '<dialog id="zot-dialog">' in html
    assert '<body data-root="">' in html and '<script src="zotero.js" defer>' in html

    docs = tmp_path / "docs"
    render_site(digests, docs, today=date(2026, 9, 28), site=SITE)
    assert (docs / "zotero.js").exists()
    import json
    data = json.loads((docs / "data" / "2026-09-28-weekly.json").read_text())
    assert data["items"]["a1"]["abstract"] == "abs" and data["items"]["a1"]["authors"][0] == "A One"
    assert set(data["items"]) == {"a1", "k1"}
    assert (docs / "data" / "2026-09-25.json").exists()
    archive = (docs / "archive" / "2026-09-28-weekly.html").read_text()
    assert '<body data-root="../">' in archive and '<script src="../zotero.js" defer>' in archive


def test_latest_json_is_the_newest_run(tmp_path: Path) -> None:
    digests = [
        digest("2026-09-28", [item("a1", "A", 90)]),
        digest("2026-09-28", [item("a0", "A", 70)], mode="daily"),
        digest("2026-09-25", [item("a9", "A", 70)], mode="daily"),
    ]
    docs = tmp_path / "docs"
    render_site(digests, docs, today=date(2026, 9, 28), site=SITE)
    import json
    latest = json.loads((docs / "data" / "latest.json").read_text())
    assert latest["run"] == "2026-09-28" and latest["mode"] == "weekly"
    assert set(latest["items"]) == {"a1"}


def test_latest_json_absent_without_a_digest(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    render_site([], docs, today=date(2026, 9, 28), site=SITE)
    assert not (docs / "data" / "latest.json").exists()


def test_banner_trims_a_long_error_but_keeps_the_gist() -> None:
    long_url = "https://api.openalex.org/works?filter=doi:" + "%7C".join(f"10.48550/arXiv.2609.{i:05}" for i in range(40))
    d = [digest("2026-09-10", [], status={"error": f"citation lookup failed: 429 Too Many Requests for url '{long_url}'"})]

    html = render_page(d, page="A", today=TODAY)

    assert "citation lookup failed: 429 Too Many Requests" in html
    assert long_url not in html and "…" in html


ELI5 = {"plain": "They cooled it down", "how": "With a fridge", "matters": "Colder is quieter", "caveat": "One device only"}


def test_explain_panel_appears_only_for_papers_that_have_one() -> None:
    digests = [digest("2026-09-10", [item("a1", "A", 90, eli5=ELI5), item("a2", "A", 70)])]

    page = render_page(digests, page="A", today=TODAY)
    assert page.count('<details class="explain"><summary>Explain</summary>') == 1
    assert "They cooled it down" in page
    assert "Be skeptical of" in page
    assert "One device only" in page


def test_explain_text_is_escaped() -> None:
    nasty = {**ELI5, "plain": '<script>alert("x")</script>'}
    page = render_page([digest("2026-09-10", [item("a1", "A", 90, eli5=nasty)])], page="A", today=TODAY)
    assert "<script>alert" not in page
    assert "&lt;script&gt;" in page


def test_only_held_computing_lists_go_without_an_explain_panel() -> None:
    """An old daily listed computing papers as titles; the weekly ranks them in full."""
    held = digest("2026-09-10", [item("c1", "computing", 90, eli5=ELI5)], mode="daily")
    assert 'class="explain"' not in render_archive(held)
    assert "held for the weekly" in render_archive(held)

    weekly = digest("2026-09-28", [item("k1", "computing", 90, eli5=ELI5)])
    assert 'class="explain"' in render_archive(weekly)
    assert 'class="explain"' in render_page([weekly], page="computing", today=date(2026, 9, 28))
