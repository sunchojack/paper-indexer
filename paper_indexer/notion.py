"""Append papers as rows to a Notion database via the official API.

The Notion client is imported lazily so building/testing the property mapping
does not require the dependency.
"""

from __future__ import annotations

import datetime as _dt
from typing import Optional

from .models import Paper
from .state import normalize_doi

# Notion caps rich_text / title content at 2000 chars per text object.
_MAX = 2000


class NotionError(Exception):
    pass


def _rich_text(value: str) -> dict:
    return {"rich_text": [{"text": {"content": value[:_MAX]}}]}


def build_properties(paper: Paper, property_map: dict[str, str]) -> dict:
    """Map a Paper to Notion property values using the configured names.

    Pure function — unit-tested without a live Notion. Property *types* are
    fixed (title/rich_text/number/url/multi_select/date); property *names* are
    taken from ``property_map`` so it fits an existing database.
    """
    p = property_map
    props: dict = {}

    props[p["title"]] = {"title": [{"text": {"content": (paper.title or "Untitled")[:_MAX]}}]}

    authors = paper.author_string()
    if authors:
        props[p["authors"]] = _rich_text(authors)

    if paper.year:
        try:
            props[p["year"]] = {"number": int(paper.year)}
        except (TypeError, ValueError):
            props[p["year"]] = _rich_text(str(paper.year))

    if paper.container:
        props[p["journal"]] = _rich_text(paper.container)

    if paper.doi:
        props[p["doi"]] = _rich_text(paper.doi)

    if paper.url:
        props[p["url"]] = {"url": paper.url}

    if paper.abstract:
        props[p["abstract"]] = _rich_text(paper.abstract)

    if paper.tags:
        props[p["tags"]] = {"multi_select": [{"name": t} for t in paper.tags]}

    props[p["added"]] = {"date": {"start": _dt.date.today().isoformat()}}

    return props


class NotionSync:
    def __init__(self, token: str, database_id: str, property_map: dict[str, str]):
        if not token:
            raise NotionError("Notion token is empty (set NOTION_TOKEN in .env).")
        if not database_id:
            raise NotionError("Notion database_id is empty (set it in config.toml).")
        self.database_id = database_id
        self.property_map = property_map
        try:
            from notion_client import Client
        except Exception as exc:  # pragma: no cover
            raise NotionError(f"notion-client not installed: {exc}") from exc
        self._client = Client(auth=token)

    def find_by_doi(self, doi: str) -> Optional[str]:
        """Return an existing page id whose DOI matches, or None."""
        ndoi = normalize_doi(doi)
        if not ndoi:
            return None
        doi_prop = self.property_map.get("doi", "DOI")
        try:
            resp = self._client.databases.query(
                database_id=self.database_id,
                filter={"property": doi_prop, "rich_text": {"contains": ndoi}},
                page_size=1,
            )
        except Exception:
            return None
        results = resp.get("results") if isinstance(resp, dict) else None
        return results[0]["id"] if results else None

    def create_page(self, paper: Paper) -> str:
        """Create a database row for the paper. Returns the new page id."""
        properties = build_properties(paper, self.property_map)
        try:
            page = self._client.pages.create(
                parent={"database_id": self.database_id},
                properties=properties,
            )
        except Exception as exc:
            raise NotionError(f"Failed to create Notion page: {exc}") from exc
        return page["id"]

    def upsert_paper(self, paper: Paper) -> tuple[str, bool]:
        """Create the row unless one with the same DOI exists.

        Returns (page_id, created) where created is False if a duplicate was found.
        """
        if paper.doi:
            existing = self.find_by_doi(paper.doi)
            if existing:
                return existing, False
        return self.create_page(paper), True
