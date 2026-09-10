from datetime import date
from pathlib import Path
from typing import Any

from digest.render import render_archive, render_index, render_site


def item(id: str, section: str, score: int | None, why: str | None = "does a thing") -> dict[str, Any]:
    return {
        "id": id, "title": f"Title {id}", "authors": ["A One", "B Two", "C Three", "D Four"],
        "abstract": "abs", "categories": ["quant-ph"], "submitted": "2026-09-09", "pool": section,
        "tags": [], "s2": {"citationCount": 2, "venue": "PRL", "tldr": ""} if id == "a1" else None,
        "section": section, "score": score, "why": why,
    }


def digest(run: str, items: list[dict[str, Any]], mode: str = "daily", status: dict[str, Any] | None = None, ranked: bool = True) -> dict[str, Any]:
    return {"run": run, "mode": mode, "generated": "x", "ranked": ranked, "status": status or {}, "items": items}


TODAY = date(2026, 9, 10)


def test_today_shows_sections_with_top_ten_and_collapsed_rest() -> None:
    a_items = [item(f"a{i}", "A", 95 - i) for i in range(12)]
    b_items = [item("b1", "B", 70)]
    html = render_index([digest("2026-09-10", a_items + b_items)], today=TODAY)

    assert "2026-09-10" in html
    assert 'href="https://arxiv.org/abs/a1"' in html
    assert "A One, B Two, C Three et al." in html
    assert "does a thing" in html
    assert "2 citations" in html and "PRL" in html
    assert html.count("<details") >= 1
    # the 11th and 12th A items are in the collapsed list after the top ten
    assert html.index("Title a10") > html.index("also matched")
    assert html.index("Title a0") < html.index("also matched")
    assert "class=\"banner\"" not in html


def test_banner_shown_for_error_and_for_stale_digest() -> None:
    html = render_index([digest("2026-09-10", [], status={"error": "arXiv 503 on pool A"})], today=TODAY)
    assert 'class="banner"' in html and "arXiv 503 on pool A" in html

    stale = render_index([digest("2026-09-07", [])], today=TODAY)  # Monday's digest on Thursday
    assert 'class="banner"' in html and "stale" in stale

    friday_ok = render_index([digest("2026-09-11", [])], today=date(2026, 9, 14))  # Friday digest on Monday
    assert 'class="banner"' not in friday_ok

    explicit = render_index([digest("2026-09-10", [])], today=TODAY, error="fetch.py exited 1")
    assert "fetch.py exited 1" in explicit


def test_unranked_digest_lists_candidates_without_scores() -> None:
    html = render_index([digest("2026-09-10", [item("a1", "A", None, None)], ranked=False)], today=TODAY)
    assert "Title a1" in html
    assert "unranked" in html


def test_weekly_block_and_previous_days_and_archive_links(tmp_path: Path) -> None:
    digests = [digest("2026-09-12", [item("w1", "weekly", 88)], mode="weekly")]
    for day in range(1, 20):
        run = date(2026, 9, 12) - __import__("datetime").timedelta(days=day)
        digests.append(digest(run.isoformat(), [item(f"p{day}", "A", 50)]))
    html = render_index(digests, today=date(2026, 9, 12))

    assert "This week" in html and "Title w1" in html
    assert "Title p1" in html            # newest daily is "today" block
    assert "Title p14" in html           # inside the previous-days block
    assert "Title p16" not in html       # older than 14 days: archive only
    assert 'href="archive/2026-08-27.html"' in html

    archive = render_archive(digests[-1])
    assert "Title p19" in archive

    docs = tmp_path / "docs"
    render_site(digests, docs, today=date(2026, 9, 12))
    assert (docs / "index.html").exists()
    assert (docs / "style.css").exists()
    assert (docs / "archive" / "2026-09-12-weekly.html").exists()
    assert (docs / "archive" / "2026-08-24.html").exists()
