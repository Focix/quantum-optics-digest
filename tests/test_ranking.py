from datetime import date

from digest.models import Candidate
from digest.ranking import validate_ranking


def cand(id: str, pool: str = "A") -> Candidate:
    return Candidate(id=id, title="t", authors=[], abstract="a", categories=[], submitted=date(2026, 9, 9), pool=pool)


CANDIDATES = [cand("1"), cand("2", "B")]


def test_valid_ranking_has_no_errors() -> None:
    ranking = {
        "run": "2026-09-10",
        "mode": "daily",
        "items": [
            {"id": "1", "section": "A", "score": 82, "why": "Measures g2 of a shaped photon."},
            {"id": "2", "section": "B", "score": 40, "why": "Standard Mollow triplet."},
        ],
    }
    assert validate_ranking(ranking, CANDIDATES, mode="daily") == []


def test_reports_unknown_ids_bad_sections_scores_and_missing_items() -> None:
    ranking = {
        "run": "2026-09-10",
        "mode": "daily",
        "items": [
            {"id": "1", "section": "D", "score": 182, "why": "x"},
            {"id": "9", "section": "A", "score": 10, "why": "x"},
        ],
    }
    errors = validate_ranking(ranking, CANDIDATES, mode="daily")
    joined = "\n".join(errors)
    assert "unknown id 9" in joined
    assert "section D" in joined
    assert "score 182" in joined
    assert "missing 1 candidate(s): 2" in joined


def test_weekly_mode_requires_weekly_section_and_mode() -> None:
    ranking = {"run": "2026-09-12", "mode": "daily", "items": [{"id": "1", "section": "A", "score": 90, "why": "x"}]}
    errors = validate_ranking(ranking, [cand("1", "weekly")], mode="weekly")
    joined = "\n".join(errors)
    assert "mode 'daily' does not match" in joined
    assert "section A" in joined


def test_non_dict_or_missing_items_is_one_error() -> None:
    assert validate_ranking([], CANDIDATES, mode="daily") == ["ranking is not an object"]
    assert validate_ranking({"run": "x"}, CANDIDATES, mode="daily") == ["ranking has no items list"]
