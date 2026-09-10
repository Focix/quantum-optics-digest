"""arXiv API: query construction and Atom feed parsing."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urlencode

from digest.models import Paper

API = "https://export.arxiv.org/api/query"
NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_ID_RE = re.compile(r"/abs/([^v]+)(?:v\d+)?$")


def build_query_url(categories: list[str], query: str, max_results: int) -> str:
    cats = " OR ".join(f"cat:{c}" for c in categories)
    search = f"({cats}) AND ({query})"
    params = {
        "search_query": search,
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    return f"{API}?{urlencode(params)}"


def _text(el: ET.Element | None) -> str:
    return " ".join((el.text or "").split()) if el is not None else ""


def parse_feed(xml: str) -> list[Paper]:
    root = ET.fromstring(xml)
    papers: list[Paper] = []
    for entry in root.findall("atom:entry", NS):
        raw_id = _text(entry.find("atom:id", NS))
        match = _ID_RE.search(raw_id)
        if not match:
            continue
        published = _text(entry.find("atom:published", NS))
        papers.append(
            Paper(
                id=match.group(1),
                title=_text(entry.find("atom:title", NS)),
                authors=[_text(a.find("atom:name", NS)) for a in entry.findall("atom:author", NS)],
                abstract=_text(entry.find("atom:summary", NS)),
                categories=[c.get("term", "") for c in entry.findall("atom:category", NS)],
                submitted=datetime.fromisoformat(published.replace("Z", "+00:00")).date(),
            )
        )
    return papers
