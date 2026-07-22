"""SQLite-backed index of processed PDFs, for dedup and retry tracking.

Keyed by file content hash (catches re-downloads and renames) and, secondarily,
by normalized DOI (catches the same paper arriving as a different file).
"""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    sha256      TEXT PRIMARY KEY,
    doi         TEXT,
    filename    TEXT,
    title       TEXT,
    zotero_key  TEXT,
    notion_id   TEXT,
    status      TEXT NOT NULL,
    updated_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
"""


@dataclass
class Record:
    sha256: str
    doi: Optional[str]
    filename: Optional[str]
    title: Optional[str]
    zotero_key: Optional[str]
    notion_id: Optional[str]
    status: str
    updated_at: float


def normalize_doi(doi: Optional[str]) -> Optional[str]:
    if not doi:
        return None
    d = doi.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if d.startswith(prefix):
            d = d[len(prefix):]
    return d or None


class StateStore:
    """Thin wrapper over a SQLite file. Safe to open per-run."""

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "StateStore":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def is_indexed(self, sha256: str, doi: Optional[str] = None) -> bool:
        """True if this file (by hash) or DOI has already been indexed OK."""
        cur = self.conn.execute(
            "SELECT status FROM papers WHERE sha256 = ?", (sha256,)
        )
        row = cur.fetchone()
        if row is not None:
            return row["status"] == "indexed"
        ndoi = normalize_doi(doi)
        if ndoi:
            cur = self.conn.execute(
                "SELECT status FROM papers WHERE doi = ? AND status = 'indexed'",
                (ndoi,),
            )
            if cur.fetchone() is not None:
                return True
        return False

    def get(self, sha256: str) -> Optional[Record]:
        cur = self.conn.execute("SELECT * FROM papers WHERE sha256 = ?", (sha256,))
        row = cur.fetchone()
        return _row_to_record(row) if row else None

    def upsert(
        self,
        sha256: str,
        *,
        status: str,
        doi: Optional[str] = None,
        filename: Optional[str] = None,
        title: Optional[str] = None,
        zotero_key: Optional[str] = None,
        notion_id: Optional[str] = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO papers (sha256, doi, filename, title, zotero_key, notion_id, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(sha256) DO UPDATE SET
                doi        = COALESCE(excluded.doi, papers.doi),
                filename   = COALESCE(excluded.filename, papers.filename),
                title      = COALESCE(excluded.title, papers.title),
                zotero_key = COALESCE(excluded.zotero_key, papers.zotero_key),
                notion_id  = COALESCE(excluded.notion_id, papers.notion_id),
                status     = excluded.status,
                updated_at = excluded.updated_at
            """,
            (
                sha256,
                normalize_doi(doi),
                filename,
                title,
                zotero_key,
                notion_id,
                status,
                time.time(),
            ),
        )
        self.conn.commit()


def _row_to_record(row: sqlite3.Row) -> Record:
    return Record(
        sha256=row["sha256"],
        doi=row["doi"],
        filename=row["filename"],
        title=row["title"],
        zotero_key=row["zotero_key"],
        notion_id=row["notion_id"],
        status=row["status"],
        updated_at=row["updated_at"],
    )
