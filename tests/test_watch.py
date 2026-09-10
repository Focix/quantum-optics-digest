from pathlib import Path

from digest.watch import load_watchlist, watch_tags, watched_names


def test_name_matching_initials_surnames_and_accents() -> None:
    authors = ["Andreas Wallraff", "J.-C. Besse", "Göran Johansson", "Y. Nakamura"]
    assert watch_tags(authors, ["A. Wallraff"]) == ["watch:A. Wallraff"]
    assert watch_tags(authors, ["Jean-Claude Besse"]) == ["watch:Jean-Claude Besse"]
    assert watch_tags(authors, ["Goran Johansson"]) == ["watch:Goran Johansson"]
    assert watch_tags(authors, ["Nakamura"]) == ["watch:Nakamura"]          # bare surname matches any first name
    assert watch_tags(authors, ["B. Wallraff"]) == []                        # wrong initial does not
    assert watch_tags(authors, ["Andreas Wall"]) == []
    assert watch_tags(["Y. Nakamura"], ["Yasunobu Nakamura"]) == ["watch:Yasunobu Nakamura"]


def test_tags_follow_watchlist_order_and_round_trip() -> None:
    tags = watch_tags(["B. Two", "A. One"], ["A. One", "B. Two"])
    assert tags == ["watch:A. One", "watch:B. Two"]
    assert watched_names(["platform:sc", *tags]) == ["A. One", "B. Two"]


def test_load_watchlist_missing_file_and_toml(tmp_path: Path) -> None:
    assert load_watchlist(tmp_path / "none.toml") == []
    f = tmp_path / "w.toml"
    f.write_text('authors = ["A. One", "  ", "B. Two"]\n')
    assert load_watchlist(f) == ["A. One", "B. Two"]
