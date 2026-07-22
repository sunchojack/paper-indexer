"""Find new PDFs in the source folder that have not been indexed yet."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from .state import StateStore

_CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(_CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Candidate:
    path: Path
    sha256: str


def iter_new_pdfs(
    source_dir: str | Path,
    state: StateStore,
    since: Optional[float] = None,
    recursive: bool = False,
) -> Iterator[Candidate]:
    """Yield PDFs in ``source_dir`` that are not already indexed.

    ``since`` is an optional POSIX mtime floor: only files modified at or after
    it are considered (handy for scheduled sweeps of recent downloads).
    """
    source = Path(source_dir)
    if not source.exists():
        return
    pattern = "**/*.pdf" if recursive else "*.pdf"
    for path in sorted(source.glob(pattern)):
        if not path.is_file():
            continue
        try:
            if since is not None and path.stat().st_mtime < since:
                continue
        except OSError:
            continue
        digest = sha256_file(path)
        # Fast skip on exact-file match; DOI-level dedup happens after extraction.
        rec = state.get(digest)
        if rec is not None and rec.status == "indexed":
            continue
        yield Candidate(path=path, sha256=digest)
