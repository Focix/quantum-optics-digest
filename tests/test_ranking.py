from datetime import date

from digest.models import Candidate
from digest.ranking import clean_eli5, validate_ranking


def cand(id: str, pool: str = "A") -> Candidate:
    return Candidate(id=id, title="t", authors=[], abstract="a", categories=[], submitted=date(2026, 9, 9), pool=pool)


CANDIDATES = [cand("1"), cand("2", "B")]


def test_valid_ranking_has_no_errors() -> None:
    ranking = {
        "run": "2026-09-10",
        "mode": "weekly",
        "items": [
            {"id": "1", "section": "A", "score": 82, "why": "Measures g2 of a shaped photon.", "kind": "E"},
            {"id": "2", "section": "B", "score": 40, "why": "Standard Mollow triplet.", "kind": "TE"},
        ],
    }
    assert validate_ranking(ranking, CANDIDATES, mode="weekly") == []


def test_reports_unknown_ids_bad_sections_scores_and_missing_items() -> None:
    ranking = {
        "run": "2026-09-10",
        "mode": "weekly",
        "items": [
            {"id": "1", "section": "D", "score": 182, "why": "x", "kind": "X"},
            {"id": "9", "section": "A", "score": 10, "why": "x"},
        ],
    }
    errors = validate_ranking(ranking, CANDIDATES, mode="weekly")
    joined = "\n".join(errors)
    assert "unknown id 9" in joined
    assert "section D" in joined
    assert "score 182" in joined
    assert "kind X" in joined
    assert "item 1: kind is missing" in joined
    assert "missing 1 candidate(s): 2" in joined


def test_mode_must_match_and_foundations_is_a_section() -> None:
    ranking = {"run": "2026-09-28", "mode": "daily", "items": [
        {"id": "1", "section": "C", "score": 90, "why": "x", "kind": "T"},
        {"id": "2", "section": "weekly", "score": 90, "why": "x", "kind": "T"},
    ]}
    errors = validate_ranking(ranking, [cand("1", "C"), cand("2", "journal")], mode="weekly")
    joined = "\n".join(errors)
    assert "mode 'daily' does not match" in joined
    assert "section C" not in joined
    assert "section weekly" in joined  # the old computing-only weekly's section is gone


def test_non_dict_or_missing_items_is_one_error() -> None:
    assert validate_ranking([], CANDIDATES, mode="weekly") == ["ranking is not an object"]
    assert validate_ranking({"run": "x"}, CANDIDATES, mode="weekly") == ["ranking has no items list"]


def test_clean_eli5_keeps_a_complete_explanation_and_drops_a_partial_one() -> None:
    full = {"plain": " p ", "how": "h", "matters": "m", "caveat": "c"}
    assert clean_eli5(full) == {"plain": "p", "how": "h", "matters": "m", "caveat": "c"}
    assert clean_eli5({**full, "caveat": "  "}) is None
    assert clean_eli5({"plain": "p"}) is None
    assert clean_eli5("just a string") is None
    assert clean_eli5(None) is None


def test_a_broken_eli5_does_not_invalidate_the_ranking() -> None:
    ranking = {"run": "2026-09-10", "mode": "weekly", "items": [
        {"id": "1", "section": "A", "score": 82, "why": "x", "kind": "E", "eli5": {"plain": "p"}},
        {"id": "2", "section": "B", "score": 40, "why": "y", "kind": "T"},
    ]}
    assert validate_ranking(ranking, CANDIDATES, mode="weekly") == []
