"""Command-line entry point: `paper-indexer run`."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import typer

from .config import Config, load_config
from .metadata import NotAPaperError
from .scan import iter_new_pdfs
from .state import StateStore

app = typer.Typer(
    add_completion=False,
    help="Index research-paper PDFs from a folder into Zotero (local) and Notion.",
)


@app.callback()
def _main() -> None:
    """paper-indexer — index PDFs into Zotero and Notion."""


def _echo(msg: str) -> None:
    typer.echo(msg)


@app.command()
def run(
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Path to config.toml."),
    source: Optional[Path] = typer.Option(None, "--source", "-s", help="Override source folder."),
    since_days: Optional[float] = typer.Option(
        None, "--since-days", help="Only consider PDFs modified in the last N days."
    ),
    recursive: bool = typer.Option(False, "--recursive", help="Scan subfolders too."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Extract and report, but do not write to Zotero/Notion."
    ),
) -> None:
    """Scan the source folder for new PDFs and index them."""
    cfg = load_config(str(config) if config else None)
    if source:
        cfg.source_dir = source.expanduser().resolve()
    since = time.time() - since_days * 86400 if since_days else None

    _echo(f"Scanning {cfg.source_dir} ...")
    processed = indexed = skipped = failed = 0

    with StateStore(cfg.state_db) as state:
        zotero = _make_zotero(cfg, dry_run)
        notion = _make_notion(cfg, dry_run)
        # A target the user *wants* but that failed to initialize (Zotero closed,
        # Notion token missing) must not count as success, or the run would be
        # recorded "indexed" and never retried once the target comes back.
        zotero_wanted = cfg.zotero.enabled and not dry_run
        notion_wanted = cfg.notion.enabled and not dry_run

        for cand in iter_new_pdfs(cfg.source_dir, state, since=since, recursive=recursive):
            processed += 1
            name = cand.path.name
            try:
                paper = _extract(cfg, cand.path)
            except NotAPaperError:
                skipped += 1
                _echo(f"  ↷ {name}: no bibliographic metadata, not a paper — skipping")
                state.upsert(cand.sha256, status="not_a_paper", filename=name)
                continue
            except Exception as exc:
                failed += 1
                _echo(f"  ✗ {name}: metadata failed: {exc}")
                state.upsert(cand.sha256, status="error", filename=name)
                continue

            # DOI-level dedup (a different file of an already-indexed paper).
            if state.is_indexed(cand.sha256, paper.doi):
                skipped += 1
                _echo(f"  ↷ {name}: already indexed (DOI match), skipping")
                state.upsert(
                    cand.sha256, status="indexed", doi=paper.doi, filename=name, title=paper.title
                )
                continue

            _echo(f"  • {name}: {paper.display()}")

            if dry_run:
                indexed += 1
                continue

            zotero_key = _push_zotero(zotero, paper)
            notion_id = _push_notion(notion, paper)

            status = (
                "indexed"
                if (zotero_key or not zotero_wanted) and (notion_id or not notion_wanted)
                else "partial"
            )
            state.upsert(
                cand.sha256,
                status=status,
                doi=paper.doi,
                filename=name,
                title=paper.title,
                zotero_key=zotero_key,
                notion_id=notion_id,
            )
            indexed += 1

    _echo("")
    _echo(
        f"Done. processed={processed} indexed={indexed} "
        f"skipped={skipped} failed={failed}"
        + (" (dry-run: nothing written)" if dry_run else "")
    )


def _extract(cfg: Config, path: Path):
    from .metadata import build_paper

    return build_paper(path, extra_tags=cfg.default_tags)


def _make_zotero(cfg: Config, dry_run: bool):
    if dry_run or not cfg.zotero.enabled:
        return None
    from .zotero import ZoteroConnector

    conn = ZoteroConnector(cfg.zotero.connector_url)
    if not conn.is_available():
        _echo(
            "  ! Zotero connector not reachable — is the desktop app open with "
            "the connector enabled? Zotero writes will be skipped."
        )
        return None
    return conn


def _make_notion(cfg: Config, dry_run: bool):
    if dry_run or not cfg.notion.enabled:
        return None
    from .notion import NotionError, NotionSync

    try:
        return NotionSync(cfg.notion.token, cfg.notion.database_id, cfg.notion.properties)
    except NotionError as exc:
        _echo(f"  ! Notion disabled: {exc}")
        return None


def _push_zotero(zotero, paper) -> Optional[str]:
    if zotero is None:
        return None
    from .zotero import ZoteroError

    try:
        key = zotero.save_paper(paper)
        _echo(f"      → Zotero: saved{f' ({key})' if key else ''}")
        return key or "saved"
    except ZoteroError as exc:
        _echo(f"      → Zotero: FAILED ({exc})")
        return None


def _push_notion(notion, paper) -> Optional[str]:
    if notion is None:
        return None
    from .notion import NotionError

    try:
        page_id, created = notion.upsert_paper(paper)
        _echo(f"      → Notion: {'created' if created else 'exists'} ({page_id})")
        return page_id
    except NotionError as exc:
        _echo(f"      → Notion: FAILED ({exc})")
        return None


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
