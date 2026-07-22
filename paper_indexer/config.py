"""Configuration loading: config.toml for structure + .env for secrets."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Default mapping from logical fields -> Notion property names. Override any of
# these in config.toml [notion.properties] so the tool fits an existing database.
DEFAULT_NOTION_PROPERTIES: dict[str, str] = {
    "title": "Title",
    "authors": "Authors",
    "year": "Year",
    "journal": "Journal",
    "doi": "DOI",
    "url": "URL",
    "abstract": "Abstract",
    "tags": "Tags",
    "added": "Added",
}


class ConfigError(Exception):
    """Raised when configuration is missing or invalid."""


@dataclass
class ZoteroConfig:
    enabled: bool = True
    connector_url: str = "http://127.0.0.1:23119"
    collection: Optional[str] = None  # collection name to file into (optional)


@dataclass
class NotionConfig:
    enabled: bool = True
    database_id: str = ""
    token: str = ""  # loaded from env, never from config.toml
    properties: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_NOTION_PROPERTIES))


@dataclass
class Config:
    source_dir: Path
    state_db: Path
    default_tags: list[str] = field(default_factory=list)
    zotero: ZoteroConfig = field(default_factory=ZoteroConfig)
    notion: NotionConfig = field(default_factory=NotionConfig)


def _expand(p: str) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(p))).resolve()


def load_config(path: str | os.PathLike | None = None) -> Config:
    """Load configuration from a TOML file, filling secrets from the environment.

    Secrets (Notion token) come from the ``NOTION_TOKEN`` environment variable,
    which is populated from a local ``.env`` file if python-dotenv is available.
    They are deliberately never read from config.toml so the config can be
    committed safely.
    """
    # Best-effort: load .env into the environment if python-dotenv is present.
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:  # pragma: no cover - dotenv is optional at runtime
        pass

    cfg_path = Path(path) if path else _find_config()
    data: dict = {}
    if cfg_path and cfg_path.exists():
        with open(cfg_path, "rb") as fh:
            data = tomllib.load(fh)
    elif path:
        raise ConfigError(f"Config file not found: {cfg_path}")

    source_dir = _expand(data.get("source_dir", "~/Downloads"))
    state_db = _expand(data.get("state_db", "~/.paper-indexer/state.db"))
    default_tags = list(data.get("default_tags", []))

    z = data.get("zotero", {})
    zotero = ZoteroConfig(
        enabled=z.get("enabled", True),
        connector_url=z.get("connector_url", "http://127.0.0.1:23119"),
        collection=z.get("collection") or None,
    )

    n = data.get("notion", {})
    properties = dict(DEFAULT_NOTION_PROPERTIES)
    properties.update(n.get("properties", {}))
    notion = NotionConfig(
        enabled=n.get("enabled", True),
        database_id=n.get("database_id", ""),
        token=os.environ.get("NOTION_TOKEN", ""),
        properties=properties,
    )

    return Config(
        source_dir=source_dir,
        state_db=state_db,
        default_tags=default_tags,
        zotero=zotero,
        notion=notion,
    )


def _find_config() -> Optional[Path]:
    """Locate config.toml from common places, or return None to use defaults."""
    candidates = [
        Path.cwd() / "config.toml",
        _expand("~/.paper-indexer/config.toml"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None
