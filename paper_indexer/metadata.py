"""Extract bibliographic metadata from a PDF and normalize it into a Paper.

Strategy:
1. ``pdf2doi`` finds an identifier (DOI / arXiv id) in the PDF.
2. ``pdf2bib`` (which wraps pdf2doi + a metadata lookup) returns bib metadata.
3. Crossref (via ``habanero``) is used as a fallback / enrichment when a DOI is
   known but pdf2bib returned thin metadata.

Heavy third-party imports are done lazily inside functions so the rest of the
package (and its unit tests) can be imported without them installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .models import Creator, Paper


class MetadataError(Exception):
    """Raised when no usable metadata could be extracted from a PDF."""


class NotAPaperError(MetadataError):
    """Raised when a PDF yielded no bibliographic evidence at all.

    Distinct from MetadataError so the CLI can skip these quietly instead of
    reporting them as failures: a folder of downloads legitimately contains
    non-papers, and those should never reach Zotero or Notion.
    """


def _year_from(value: Any) -> Optional[str]:
    """Coerce assorted date shapes (int, '2021', '2021-05-03', crossref parts)."""
    if value is None:
        return None
    if isinstance(value, dict):  # crossref date-parts: {"date-parts": [[2021, 5]]}
        parts = value.get("date-parts")
        if parts and parts[0]:
            return str(parts[0][0])
        return None
    s = str(value).strip()
    if not s:
        return None
    # Grab the first 4-digit run.
    digits = ""
    for ch in s:
        if ch.isdigit():
            digits += ch
            if len(digits) == 4:
                return digits
        else:
            digits = ""
    return None


def _creators_from(authors: Any) -> list[Creator]:
    """Normalize author lists from pdf2bib/crossref into Creator objects."""
    creators: list[Creator] = []
    if not authors:
        return creators
    if isinstance(authors, str):
        # "Doe, Jane and Smith, John" or "Jane Doe, John Smith"
        chunks = [a for part in authors.split(" and ") for a in part.split(";")]
        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            if "," in chunk:
                last, first = chunk.split(",", 1)
                creators.append(Creator(last_name=last.strip(), first_name=first.strip()))
            else:
                bits = chunk.rsplit(" ", 1)
                if len(bits) == 2:
                    creators.append(Creator(last_name=bits[1].strip(), first_name=bits[0].strip()))
                else:
                    creators.append(Creator(last_name=chunk))
        return creators
    for a in authors:
        if isinstance(a, dict):
            last = a.get("family") or a.get("last") or a.get("lastName") or ""
            first = a.get("given") or a.get("first") or a.get("firstName") or ""
            name = a.get("name")
            if not last and name:
                last = name
            if last:
                creators.append(Creator(last_name=str(last).strip(), first_name=str(first).strip()))
        elif isinstance(a, str) and a.strip():
            creators.append(Creator(last_name=a.strip()))
    return creators


# Map common bib "entry type" / crossref "type" -> Zotero item type.
_ITEM_TYPE_MAP = {
    "article": "journalArticle",
    "journal-article": "journalArticle",
    "article-journal": "journalArticle",
    "inproceedings": "conferencePaper",
    "proceedings-article": "conferencePaper",
    "conference": "conferencePaper",
    "book": "book",
    "incollection": "bookSection",
    "book-chapter": "bookSection",
    "phdthesis": "thesis",
    "techreport": "report",
    "report": "report",
    "preprint": "preprint",
    "posted-content": "preprint",
}


def paper_from_metadata(meta: dict, pdf_path: str | Path, extra_tags: Optional[list[str]] = None) -> Paper:
    """Build a Paper from a flat-ish metadata dict (pdf2bib or crossref shape).

    Pure function (no I/O beyond reading the given dict), so it is unit-testable
    without any live services or heavy dependencies.
    """
    meta = meta or {}
    title = meta.get("title") or meta.get("Title")
    if isinstance(title, list):
        title = title[0] if title else None
    title = (title or "").strip()

    container = (
        meta.get("journal")
        or meta.get("container-title")
        or meta.get("publicationTitle")
        or meta.get("booktitle")
    )
    if isinstance(container, list):
        container = container[0] if container else None

    raw_type = str(
        meta.get("ENTRYTYPE") or meta.get("type") or meta.get("entry_type") or ""
    ).lower()
    item_type = _ITEM_TYPE_MAP.get(raw_type, "journalArticle")

    doi = meta.get("doi") or meta.get("DOI")
    url = meta.get("url") or meta.get("URL")
    if not url and doi:
        url = f"https://doi.org/{doi}"

    paper = Paper(
        title=title or Path(pdf_path).stem,
        creators=_creators_from(meta.get("author") or meta.get("authors")),
        year=_year_from(meta.get("year") or meta.get("published") or meta.get("issued")),
        container=str(container).strip() if container else None,
        doi=str(doi).strip() if doi else None,
        url=str(url).strip() if url else None,
        abstract=(meta.get("abstract") or meta.get("abstractNote") or None),
        item_type=item_type,
        tags=list(extra_tags or []),
        pdf_path=str(Path(pdf_path).resolve()),
    )
    return paper


def crossref_lookup(doi: str) -> Optional[dict]:
    """Fetch metadata for a DOI from Crossref. Returns a dict or None."""
    try:
        from habanero import Crossref
    except Exception:  # pragma: no cover - optional at runtime
        return None
    try:
        cr = Crossref()
        resp = cr.works(ids=doi)
        return resp.get("message") if isinstance(resp, dict) else None
    except Exception:
        return None


def extract_identifier(pdf_path: str | Path) -> Optional[str]:
    """Return a DOI/arXiv identifier for the PDF, or None."""
    try:
        import pdf2doi
    except Exception as exc:  # pragma: no cover
        raise MetadataError(f"pdf2doi not available: {exc}") from exc
    try:
        result = pdf2doi.pdf2doi(str(pdf_path))
    except Exception:
        return None
    if isinstance(result, dict):
        return result.get("identifier")
    return None


def has_bibliographic_evidence(meta: dict) -> bool:
    """True if a lookup actually produced bibliographic data for this PDF.

    Pure function so the "is this a paper?" decision is testable without a live
    lookup. This must be checked against the *metadata dict*, not the resulting
    Paper: paper_from_metadata falls back to the filename for a missing title,
    so a Paper always has one and checking it would let every readable PDF --
    NDAs, payslips, scanned forms -- through.
    """
    meta = meta or {}
    return bool(meta.get("doi") or meta.get("DOI") or meta.get("title") or meta.get("Title"))


def build_paper(pdf_path: str | Path, extra_tags: Optional[list[str]] = None) -> Paper:
    """Full extraction: PDF -> normalized Paper.

    Tries pdf2bib first (richest, one shot). Falls back to identifier + Crossref.
    Raises MetadataError only if nothing usable at all could be produced.
    """
    pdf_path = Path(pdf_path)
    meta: dict = {}

    # 1. pdf2bib: identifier + metadata in one call.
    try:
        import pdf2bib

        result = pdf2bib.pdf2bib(str(pdf_path))
        if isinstance(result, dict):
            meta = dict(result.get("metadata") or {})
            if not meta.get("doi") and result.get("identifier"):
                meta["doi"] = result["identifier"]
    except Exception:
        meta = {}

    # 2. Crossref enrichment if metadata is thin but we have a DOI.
    doi = meta.get("doi") or meta.get("DOI")
    if doi and (not meta.get("title") or not (meta.get("author") or meta.get("authors"))):
        cr = crossref_lookup(str(doi))
        if cr:
            merged = dict(cr)
            merged.update({k: v for k, v in meta.items() if v})
            meta = merged

    # 3. Require real evidence this is a paper (see has_bibliographic_evidence).
    if not has_bibliographic_evidence(meta):
        raise NotAPaperError(
            f"No DOI or title found in {Path(pdf_path).name}; not a research paper"
        )

    return paper_from_metadata(meta, pdf_path, extra_tags=extra_tags)
