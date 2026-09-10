"""Data records shared across the digest pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any


@dataclass
class Paper:
    """One arXiv paper as parsed from the API feed."""

    id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    submitted: date


@dataclass
class Candidate:
    """A paper that survived selection and is handed to the ranking model."""

    id: str
    title: str
    authors: list[str]
    abstract: str
    categories: list[str]
    submitted: date
    pool: str
    tags: list[str] = field(default_factory=list)
    s2: dict[str, Any] | None = None
    url: str | None = None  # only for non-arXiv papers (weekly S2 search)

    @classmethod
    def from_paper(cls, paper: Paper, pool: str, tags: list[str]) -> Candidate:
        return cls(
            id=paper.id,
            title=paper.title,
            authors=list(paper.authors),
            abstract=paper.abstract,
            categories=list(paper.categories),
            submitted=paper.submitted,
            pool=pool,
            tags=list(tags),
        )

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["submitted"] = self.submitted.isoformat()
        return data

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Candidate:
        return cls(
            id=data["id"],
            title=data["title"],
            authors=list(data["authors"]),
            abstract=data["abstract"],
            categories=list(data["categories"]),
            submitted=date.fromisoformat(data["submitted"]),
            pool=data["pool"],
            tags=list(data.get("tags", [])),
            s2=data.get("s2"),
            url=data.get("url"),
        )
