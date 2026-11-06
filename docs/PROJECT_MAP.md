# Project map — fast onboarding (~1-minute read)

## What exists today

POC v0.3, **no production Rust/Tree-sitter/SCIP**. External source is read-only; `guardian scan` creates content-addressed snapshots; unchanged files are reused. CLI and Claude Code MCP call the same service; on-disk content is checked before source context is served.

```text
scripts/connect_claude.sh  --> ucg/mcp.py --> ucg/service.py
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

## Important constraints

- Source may contain confidential code; an AI context response can transmit selected source to the calling model.
- Candidate graph edges are heuristic, **not trusted impact analysis**.
- Source file modification between scan and query yields stale error and requires a refresh.
- Source structure is computed without Git; the integration with `claude mcp` is per workspace.
