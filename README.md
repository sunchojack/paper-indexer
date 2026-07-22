# paper-indexer

A small, local macOS service that watches a folder (e.g. `~/Downloads`) for
research-paper PDFs, extracts their bibliographic metadata, and files each paper
into **Zotero** (your local desktop app) **and** a **Notion** database — with
deduplication so re-running is safe.

Everything runs on your machine. Zotero writes go through Zotero's local
Connector API (no cloud, no API key); only Notion (by nature a hosted service)
talks to the network.

```
~/Downloads/*.pdf ──► extract DOI + metadata ──► Zotero (local)  +  Notion (database row)
                         (pdf2doi / pdf2bib /                   dedup by file hash & DOI
                          Crossref fallback)
```

## How it works

1. **Scan** the source folder for `*.pdf`, hashing each file (`scan.py`).
2. **Skip** anything already recorded in a local SQLite index (`state.py`) — by
   file hash *and* by DOI, so the same paper isn't added twice.
3. **Extract** metadata (`metadata.py`): `pdf2doi` finds the DOI/arXiv id,
   `pdf2bib` pulls bibliographic data, and Crossref fills gaps.
4. **Push** to Zotero via `POST /connector/saveItems` (`zotero.py`) and to Notion
   via the official API (`notion.py`).
5. **Record** the result so the next run skips it.

Failures on one file never abort the sweep; that file is marked and retried next
run.

## Requirements

- macOS, Python 3.11+
- **Zotero desktop** running, with
  *Settings → Advanced → "Allow other applications on this computer to
  communicate with Zotero"* enabled.
- A **Notion** internal integration + a database to write into.

## Install

```bash
git clone https://github.com/sunchojack/paper-indexer.git
cd paper-indexer
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Configure

```bash
cp config.example.toml config.toml
cp .env.example .env
```

- Edit `config.toml`: set `source_dir`, your Notion `database_id`, and (if your
  database uses different column names) the `[notion.properties]` map.
- Edit `.env`: paste your `NOTION_TOKEN`.

### Notion setup

1. Create an internal integration at
   <https://www.notion.so/my-integrations> and copy its token into `.env`.
2. Open your target database, then **⋯ → Connections → Connect to** your
   integration.
3. Copy the database id from its URL
   (`notion.so/<workspace>/<DATABASE_ID>?v=...`) into `config.toml`.
4. The default column mapping expects properties named `Title` (a Title
   property), `Authors`, `Year` (number), `Journal`, `DOI`, `URL`, `Abstract`,
   `Tags` (multi-select), `Added` (date). Rename in `[notion.properties]` to
   match your database, or drop columns you don't want — missing ones are simply
   skipped (only `Title` is required).

## Usage

```bash
# See what it would do, without writing anything:
paper-indexer run --dry-run

# Real run over the whole source folder:
paper-indexer run

# Only recent downloads, from a specific config:
paper-indexer run -c ~/.paper-indexer/config.toml --since-days 7
```

Run it again any time — already-indexed papers are skipped.

## Run it automatically (launchd)

`scripts/com.user.paperindexer.plist` is a ready-to-edit launchd agent. It
sweeps every 15 minutes **and** whenever `~/Downloads` changes.

```bash
# Find the binary path to put in the plist:
which paper-indexer

# Edit the REPLACE placeholders in the plist, then:
cp scripts/com.user.paperindexer.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.user.paperindexer.plist

# Logs:
tail -f /tmp/paper-indexer.out.log
```

To stop: `launchctl unload ~/Library/LaunchAgents/com.user.paperindexer.plist`.

## Development

```bash
pip install -e ".[dev]"
pytest
```

Unit tests cover the pure logic (metadata mapping, Zotero payload, Notion
property mapping, dedup/state, folder scanning) and need no live services.

## Notes & limitations

- **Zotero must be open** for items to be saved; if it isn't reachable the run
  still indexes to Notion and reports the Zotero step as skipped.
- Metadata extraction is best-effort — older or scanned PDFs may lack an
  embedded DOI. Such files fall back to using the filename as the title and can
  be corrected in Zotero/Notion afterward.
- The Zotero Connector endpoints are stable but unofficial. The local
  *read* API (`/api/`) does not support writes, which is why the connector path
  is used here.

## License

MIT
