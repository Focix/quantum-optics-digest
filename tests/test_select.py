from datetime import date

from digest.models import Paper
from digest.select import mark_seen, select_candidates


def paper(id: str, submitted: str, abstract: str = "Photon.", cats: list[str] | None = None) -> Paper:
    return Paper(
        id=id,
        title=f"Paper {id}",
        authors=["A. Author"],
        abstract=abstract,
        categories=cats or ["quant-ph"],
        submitted=date.fromisoformat(submitted),
    )


TODAY = date(2026, 9, 10)


def test_keeps_only_papers_within_window_and_not_seen() -> None:
    pools = {
        "A": [paper("1", "2026-09-09"), paper("2", "2026-09-02"), paper("3", "2026-09-08")],
    }
    seen = {"3": "2026-09-09"}
    result = select_candidates(pools, seen=seen, today=TODAY, window_days=7, cap=120)

    assert [c.id for c in result.candidates] == ["1"]
    assert result.dropped_seen == 1
    assert result.dropped_old == 1


def test_b_paper_also_in_a_pool_is_kept_once_in_a() -> None:
    pools = {
        "A": [paper("1", "2026-09-09")],
        "B": [paper("1", "2026-09-09"), paper("2", "2026-09-09")],
    }
    result = select_candidates(pools, seen={}, today=TODAY, window_days=7, cap=120)

    assert [(c.id, c.pool) for c in result.candidates] == [("1", "A"), ("2", "B")]


def test_a_pool_gets_platform_tag_and_computing_heuristic() -> None:
    pools = {
        "A": [
            paper("1", "2026-09-09", abstract="We measure g2 of a shaped microwave photon."),
            paper("2", "2026-09-09", abstract="We demonstrate a surface code below threshold."),
        ],
        "C": [paper("3", "2026-09-09", abstract="Axion search with a qubit.")],
    }
    result = select_candidates(pools, seen={}, today=TODAY, window_days=7, cap=120)
    by_id = {c.id: c for c in result.candidates}

    assert by_id["1"].tags == ["platform:sc"]
    assert by_id["2"].tags == ["platform:sc", "computing"]
    assert by_id["3"].tags == []


def test_cap_keeps_newest_and_reports_overflow() -> None:
    pools = {"B": [paper(str(i), f"2026-09-0{1 + i % 9}") for i in range(10)]}
    result = select_candidates(pools, seen={}, today=TODAY, window_days=30, cap=3)

    assert len(result.candidates) == 3
    assert sorted(c.submitted.isoformat() for c in result.candidates) == ["2026-09-07", "2026-09-08", "2026-09-09"]
    assert result.overflow == 7


def test_mark_seen_adds_ids_with_today_and_prunes_old_entries() -> None:
    pools = {"A": [paper("1", "2026-09-09")]}
    result = select_candidates(pools, seen={}, today=TODAY, window_days=7, cap=120)
    seen = {"old": "2026-01-01", "recent": "2026-09-01"}

    updated = mark_seen(seen, result.candidates, today=TODAY, keep_days=60)

    assert updated == {"recent": "2026-09-01", "1": "2026-09-10"}
