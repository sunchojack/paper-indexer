"""Core data model shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Creator:
    """An author (or other creator) of a paper."""

    last_name: str
    first_name: str = ""

    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class Paper:
    """Normalized bibliographic record extracted from a PDF.

    This is the single currency passed between metadata extraction and the
    Zotero / Notion sinks, so both sinks map from the same shape.
    """

    title: str
    creators: list[Creator] = field(default_factory=list)
    year: Optional[str] = None
    container: Optional[str] = None  # journal / conference / publication title
    doi: Optional[str] = None
    url: Optional[str] = None
    abstract: Optional[str] = None
    item_type: str = "journalArticle"  # Zotero item type
    tags: list[str] = field(default_factory=list)
    pdf_path: Optional[str] = None

    def author_string(self) -> str:
        """Human-readable author list, e.g. 'Jane Doe; John Smith'."""
        return "; ".join(c.full_name() for c in self.creators if c.last_name)

    def display(self) -> str:
        who = self.author_string() or "unknown authors"
        when = self.year or "n.d."
        return f"{self.title} — {who} ({when})"
