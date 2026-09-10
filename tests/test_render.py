from datetime import date, timedelta
from pathlib import Path
from typing import Any

from digest.render import render_archive, render_page, render_site


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
