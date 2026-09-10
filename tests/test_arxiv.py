from pathlib import Path

from digest.arxiv import build_query_url, parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "arxiv_transmon.xml"


def test_parse_feed_yields_papers_with_bare_ids_and_dates() -> None:
    papers = parse_feed(FIXTURE.read_text())

    assert [p.id for p in papers] == ["2609.09426", "2609.08348"]
    first = papers[0]
    assert first.title.startswith("Josephson energy of superconducting junctions")
    assert first.authors[:2] == ["Wanting Zhang", "Aldilene Saraiva-Souza"]
    assert len(first.authors) == 6
    assert first.submitted.isoformat() == "2026-09-08"
    assert first.categories == ["quant-ph"]
    assert first.abstract.startswith("The Josephson energy")
    assert papers[1].categories == ["quant-ph", "cond-mat.supr-con", "physics.app-ph"]


def test_parse_feed_collapses_whitespace_in_title_and_abstract() -> None:
    xml = FIXTURE.read_text().replace(
        "Josephson energy of superconducting junctions",
        "Josephson energy of\n  superconducting junctions",
    )
    papers = parse_feed(xml)
    assert "Josephson energy of superconducting junctions" in papers[0].title


def test_build_query_url_combines_categories_and_query() -> None:
    url = build_query_url(
        categories=["quant-ph", "hep-ex"],
        query='abs:axion AND abs:qubit',
        max_results=200,
    )
    assert url.startswith("https://export.arxiv.org/api/query?")
    assert "sortBy=submittedDate" in url
    assert "sortOrder=descending" in url
    assert "max_results=200" in url
    # categories OR'ed together and AND'ed with the query
    assert "%28cat%3Aquant-ph+OR+cat%3Ahep-ex%29+AND+%28abs%3Aaxion+AND+abs%3Aqubit%29" in url
