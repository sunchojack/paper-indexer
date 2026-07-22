"""Write items to a locally-running Zotero desktop via its Connector API.

This is the fully-local, no-cloud, no-API-key path: it targets the same HTTP
server the "Save to Zotero" browser button uses
(http://127.0.0.1:23119/connector/...). Zotero must be running with
Settings -> Advanced -> "Allow other applications on this computer to
communicate with Zotero" enabled.

Note: Zotero's *local API* (/api/) is read-only; the *connector* endpoints below
are the supported local write path.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Optional

import requests

from .models import Paper

CONNECTOR_API_VERSION = "3"


class ZoteroError(Exception):
    pass


def build_zotero_item(paper: Paper) -> dict:
    """Translate a Paper into a Zotero connector item dict.

    Pure function — unit-tested without a live Zotero.
    """
    item: dict = {
        "itemType": paper.item_type,
        "title": paper.title,
        "creators": [
            {"creatorType": "author", "firstName": c.first_name, "lastName": c.last_name}
            for c in paper.creators
            if c.last_name
        ],
        "tags": [{"tag": t} for t in paper.tags],
    }
    if paper.year:
        item["date"] = paper.year
    if paper.container:
        item["publicationTitle"] = paper.container
    if paper.doi:
        item["DOI"] = paper.doi
    if paper.url:
        item["url"] = paper.url
    if paper.abstract:
        item["abstractNote"] = paper.abstract
    if paper.pdf_path:
        item["attachments"] = [
            {
                "title": "Full Text PDF",
                "mimeType": "application/pdf",
                "url": Path(paper.pdf_path).resolve().as_uri(),
                "linkMode": "imported_file",
            }
        ]
    return item


def build_save_payload(paper: Paper, session_id: str) -> dict:
    """Build the POST body for /connector/saveItems."""
    return {
        "items": [build_zotero_item(paper)],
        "sessionID": session_id,
        "uri": paper.url or "",
    }


class ZoteroConnector:
    def __init__(self, base_url: str = "http://127.0.0.1:23119", timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "X-Zotero-Connector-API-Version": CONNECTOR_API_VERSION,
            # Some Zotero versions gate the connector on a non-browser UA check.
            "User-Agent": "paper-indexer/0.1",
        }

    def is_available(self) -> bool:
        """True if a Zotero connector server answers on the endpoint."""
        try:
            resp = requests.post(
                f"{self.base_url}/connector/ping",
                json={},
                headers=self._headers(),
                timeout=self.timeout,
            )
            return resp.status_code < 500
        except requests.RequestException:
            return False

    def save_paper(self, paper: Paper) -> Optional[str]:
        """Save a Paper (with its PDF) to Zotero. Returns an item key if reported.

        Raises ZoteroError on transport/HTTP failure so the caller can mark the
        record 'zotero_pending' and retry on a later run.
        """
        session_id = uuid.uuid4().hex
        payload = build_save_payload(paper, session_id)
        try:
            resp = requests.post(
                f"{self.base_url}/connector/saveItems",
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise ZoteroError(f"Could not reach Zotero connector: {exc}") from exc

        if resp.status_code not in (200, 201):
            raise ZoteroError(
                f"Zotero saveItems failed: HTTP {resp.status_code}: {resp.text[:300]}"
            )

        return _extract_item_key(resp)


def _extract_item_key(resp: "requests.Response") -> Optional[str]:
    try:
        data = resp.json()
    except ValueError:
        return None
    items = data.get("items") if isinstance(data, dict) else None
    if items:
        first = items[0]
        return first.get("key") or first.get("id")
    return None
