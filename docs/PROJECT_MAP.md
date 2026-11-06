# Project map — fast onboarding

## Current implementation

v0.5.0 is a Python POC with optional Tree-sitter parsing and offline Change X-Ray. Scanned source remains read-only. SQLite snapshots and parser caches live outside the scanned project.

~~~text
CLI / menu / MCP
      |
  GuardianService (freshness gate)
      |
  scan_workspace
      |
  scanner.py -> parser.py fallback
            -> treesitter.py (optional local grammar)
      |
  engine.py -> resolve imports/references
      |
  store.py (SQLite snapshots)
      |-- files / symbols / edges
      |-- file_analysis / imports / symbol_references / symbol_analysis
      |
  offline.py -> tree / outline / repo-map / diff / impact
~~~

| Need | Open this file |
|---|---|
| Optional parser and binding rules | \`ucg/treesitter.py\` |
| Change X-Ray algorithm | \`ucg/offline.py\` |
| Scan/reuse/atomic snapshots | \`ucg/engine.py\` |
| SQLite migrations/queries | \`ucg/store.py\` |
| CLI grammar install and impact | \`ucg/cli.py\` |
| MCP tools | \`ucg/mcp.py\` |
| Shared freshness boundary | \`ucg/service.py\` |
| Symbol/edge records | \`ucg/models.py\` |
| Fallback parser | \`ucg/parser.py\` |
| Parser/impact integration tests | \`tests/test_treesitter.py\` |
| Cross-platform/legacy regressions | \`tests/\` |

## Commands

~~~bash
python -m ucg.cli --root /path/to/project parsers status
python -m ucg.cli --root /path/to/project parsers install --languages python,typescript
python -m ucg.cli --root /path/to/project scan
python -m ucg.cli --root /path/to/project impact
~~~

## Trust constraints

- A Tree-sitter edge is a syntactic binding with a stated resolution reason, not compiler proof.
- \`ast_candidate\` is heuristic and lower confidence; unresolved references remain visible.
- Change X-Ray suggests dependent code and tests but does not execute tests or guarantee completeness.
- Queries require a fresh source fingerprint. Concurrent scans still need external coordination.
