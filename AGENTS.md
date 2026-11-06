# Agent instructions — read this first (under 250 tokens)

Engineering Guardian v0.3.1 is a **local, source-read-only Python POC**. It indexes arbitrary folders (Git not required) into external SQLite and serves Claude Code via MCP. **It is not Rust/Tree-sitter/SCIP yet.** Non-Python symbols and **all CALLS edges are heuristic candidates**.

- Entry points: `ucg/cli.py` (`python -m ucg.cli`) and `ucg/mcp.py` (stdio MCP).
- Flow: `scanner.py` → `parser.py` → `engine.py` → `store.py` → `service.py` → `context.py`.
- Metadata/metrics: `diagnostics.py`; no source content/paths/prompts in support logs.
- Data: `~/.engineering-guardian/` or `$GUARDIAN_HOME`, never the scanned source.
- Tests: `python -m unittest discover -s tests -v`; Windows also runs PowerShell checks in CI.
- Safety: no modifying scanned source, no publishing private code, no shell tool in MCP; freshness checking is mandatory. Never call a candidate edge a verified dependency.
- Before a change: review `docs/DEVELOPER_GUIDE.md`; after: test, update `CHANGELOG.md` and relevant docs.
- Windows entry points: `scripts/connect_claude.ps1`, `scripts/start_windows.ps1`, `Start Engineering Guardian.cmd`; WSL2 uses Bash. More: `docs/PROJECT_MAP.md`, `docs/DOCS_INDEX.md`.
