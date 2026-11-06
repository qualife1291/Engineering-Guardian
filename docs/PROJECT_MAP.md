# Project map — fast onboarding (~1-minute read)

## What exists today

POC v0.4.0, **no production Rust/Tree-sitter/SCIP**. External source is read-only; `guardian scan` creates content-addressed snapshots; unchanged files are reused. CLI and Claude Code MCP call the same service; on-disk content is checked before source context is served.

```text
scripts/connect_claude.sh / connect_claude.ps1 --> ucg/mcp.py --> ucg/service.py
python -m ucg.cli ---------/                    |
                                                 v
ucg/scanner.py --> ucg/parser.py --> ucg/engine.py --> ucg/store.py (SQLite)
                                                 |
                                        ucg/context.py
                                                 |
                                        ucg/diagnostics.py (JSONL)
```

| Need | Open only this file |
|---|---|
| Windows installers/launchers | `scripts/windows_common.ps1`, `scripts/start_windows.ps1`, `scripts/connect_claude.ps1`, `Start Engineering Guardian.cmd` |
| Offline tree/outline/map/hotspots/diff | `ucg/offline.py`, `ucg/service.py`, `ucg/cli.py`, `ucg/mcp.py` |
| Add CLI command | `ucg/cli.py` |
| Add MCP tool | `ucg/mcp.py`, `ucg/service.py` |
| Change scan/cache | `ucg/scanner.py`, `ucg/engine.py` |
| Parse language | `ucg/languages.py`, `ucg/parser.py` |
| Symbol IDs/graph | `ucg/models.py`, `ucg/store.py` |
| Context token budget | `ucg/context.py` |
| Logging/privacy | `ucg/diagnostics.py` |
| Integration tests | `tests/test_mcp_incremental.py` |
| Baselines | `benchmarks/` and `docs/BENCHMARK.md` |

## Commands

```bash
python3 -m ucg.cli --root /path/to/app scan
python3 -m ucg.cli --root /path/to/app status
python3 -m ucg.cli --root /path/to/app search render
python3 -m ucg.cli --root /path/to/app support-bundle
```

## Platform and documentation navigation

- Windows native: [WINDOWS_SETUP_VI.md](WINDOWS_SETUP_VI.md), `Start Engineering Guardian.cmd`.
- macOS/Linux/WSL2: [EASY_START_VI.md](EASY_START_VI.md), `scripts/connect_claude.sh`.
- Full map: [DOCS_INDEX.md](DOCS_INDEX.md); coding rules: [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md).

## Important constraints

- Source may contain confidential code; an AI context response can transmit selected source to the calling model.
- Candidate graph edges are heuristic, **not trusted impact analysis**.
- Source file modification between scan and query yields stale error and requires a refresh.
- Source structure is computed without Git; the integration with `claude mcp` is per workspace.

## Offline v0.4 navigation path

`ucg/offline.py` supplies deterministic tree/outline/hotspots/PageRank-style repo-map/diff/brief. Exposed through GuardianService, CLI and MCP, these work without AI. CLI and MCP machine output use UTF-8 on Windows and Unix. See [OFFLINE_INTELLIGENCE.md](OFFLINE_INTELLIGENCE.md).
