# Agent instructions — read this first (under 250 tokens)

Engineering Guardian v0.5.0 is a **local, source-read-only Python POC**. Optional Tree-sitter grammars add syntax extraction and conservative import/local bindings; Python AST/regex fallback remains. No SCIP/type-checker/runtime proof.

- Entry points: `ucg/cli.py` (`python -m ucg.cli`, no AI) and `ucg/mcp.py` (stdio MCP for AI clients).
- Flow: `scanner.py` → `parser.py` → `engine.py` → `store.py` → `service.py`; `offline.py` supplies maps/outlines/diffs; `context.py` serves snippets.
- Metadata/metrics: `diagnostics.py`; no source content/paths/prompts in support logs.
- Data: `~/.engineering-guardian/` or `$GUARDIAN_HOME`, never the scanned source.
- Tests: `python -m unittest discover -s tests -v`; Windows also runs PowerShell checks in CI.
- Safety: no modifying scanned source, no publishing private code, no shell tool in MCP; freshness checking is mandatory. Never call a candidate edge a verified dependency.
- Before a change: review `docs/DEVELOPER_GUIDE.md`; after: test, update `CHANGELOG.md` and relevant docs.
- Windows entry points: `scripts/connect_claude.ps1`, `scripts/start_windows.ps1`, `Start Engineering Guardian.cmd`; WSL2 uses Bash. More: `docs/PROJECT_MAP.md`, `docs/DOCS_INDEX.md`.

- Public repository: NEVER commit personal paths, named private apps, customer data or real benchmark environment paths. Privacy regression test is mandatory.

- Tree-sitter is optional. Never download grammars during scan; only explicit \`guardian parsers install\` may access the network. Read \`docs/TREE_SITTER_CHANGE_XRAY.md\` before modifying resolution.
- Change X-Ray is static impact guidance, not a complete dependency proof and does not run tests.
