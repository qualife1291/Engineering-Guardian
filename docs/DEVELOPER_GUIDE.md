# Developer guide — maintain Engineering Guardian safely

## First 60 seconds

Read [AGENTS.md](../AGENTS.md) (rules) then [PROJECT_MAP.md](PROJECT_MAP.md) (file ownership). Only open implementation files relevant to the task. Run [TESTING.md](TESTING.md) checks before committing.

**Architecture:** `ucg/scanner.py` inventories source → `parser.py` extracts symbols → `engine.py` computes candidate edges and versioned snapshots → `store.py` persists SQLite → `service.py` enforces freshness → `cli.py` / `mcp.py` expose data. `context.py` verifies source fingerprint and bounds source snippets; `diagnostics.py` records allowlisted metrics.

## Changes by category

| Change | Files to inspect first | Required verification |
|---|---|---|
| Windows installation / launcher | `scripts/windows_common.ps1`, `scripts/start_windows.ps1`, `Start Engineering Guardian.cmd` | Windows runner bootstrap + PowerShell AST parse |
| Claude Code registration | `scripts/connect_claude.sh`, `scripts/connect_claude.ps1`, `docs/CLAUDE_CODE.md` | Verify per-project registration, root quoting, no source writes |
| CLI tool | `ucg/cli.py`, `ucg/service.py` | CLI JSON on success/error; tests |
| MCP tool | `ucg/mcp.py`, `ucg/service.py` | JSON-RPC stdio, no arbitrary root or shell |
| Index correctness | `ucg/engine.py`, `ucg/store.py`, `ucg/context.py` | Same snapshot on no changes, changed-file reparse, stale fail-closed |
| Parser logic | `ucg/parser.py`, `ucg/languages.py` | Supported fixture tests, report ambiguity |
| Operational logging | `ucg/diagnostics.py` | ZIP never contains source snippets or paths |
| Documentation | `README.md`, `docs/DOCS_INDEX.md`, platform guide | Valid relative links, version and command alignment |

## Local commands

macOS/Linux/WSL2:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q ucg scripts benchmarks tests
python3 -m ucg.cli --root ./tests scan
python3 -m ucg.cli --root ./tests status
```

Windows native PowerShell:

```powershell
py -3 -m unittest discover -s tests -v
py -3 -m compileall -q ucg scripts benchmarks tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1 -CheckOnly
```

Run commands from the **Guardian repository root**. The scanner must never execute application source, build hooks or arbitrary shell scripts.

## Guidelines for agent contributions

1. Keep edits narrowly scoped; no speculative refactor.
2. Every graph edge that is not compiler-verified stays labeled `ast_candidate`.
3. Keep source root explicit. No tool may override authorized root via untrusted arguments.
4. Do not store or upload source/paths/prompts in diagnostic logs.
5. Add one regression test for each fixed bug and each new OS-specific path.
6. Update the nearest relevant guide and `CHANGELOG.md`, keeping the package version aligned.
7. Only call a release complete after all relevant GitHub CI operating-system jobs pass.
