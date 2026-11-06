# Changelog

All notable **released** changes to Engineering Guardian are recorded here, following [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/). Dates use `YYYY-MM-DD` (UTC). Runtime diagnostics belong in `~/.engineering-guardian/diagnostics/`, **not** in this file.

## [Unreleased]

### Planned (not implemented)
- Tree-sitter and SCIP/LSP precise semantic indexing for multiple languages.
- Cross-language MethodChannel, HTTP, SQL and event contract resolution.
- Change X-Ray UI, source-linked diagrams and CI benchmark regression gates.

## [0.4.0] - 2026-11-06

### Added
- Zero-AI commands for compact indexed folder tree, single-file outlines, structural maintenance hotspots and ranked repository maps.
- Local source snapshot comparison without Git, and deterministic offline Markdown brief.
- File-level PageRank-style navigation ranking, lexical relevance, and diversity-aware context selection with hard output budgets.
- Shared MCP tools for multiple AI clients; Guardian remains independently usable through CLI.
- Platform-neutral public documentation, privacy review checklist, automated sensitive-example regression checks.

### Changed
- All usage examples now use neutral project names, relative roots and illustrative paths.
- Sanitize historical benchmark fixture paths before publishing reports.
- Clarify that scanner currently uses BLAKE2b, syntax heuristics outside Python, and cannot prove runtime/semantic correctness.
- Support bundles redact their workspace identifier to reduce linkability when shared.

### Limitations
- The POC still has no production Tree-sitter/SCIP or verified cross-language call graph.
- Existing Git history may retain previous public content; editing the current branch cannot erase GitHub commit history.
- Concurrent scans are not coordinated between multiple agent processes.

## [0.3.1] - 2026-11-06

### Added
- Windows 10/11 native PowerShell bootstrap and project-scoped Claude Code connector (`scripts/connect_claude.ps1`).
- One-click Windows command launcher (`Start Engineering Guardian.cmd`) and offline `.venv` setup, with no global Python package modifications.
- Windows/WSL2 installation and troubleshooting guide, documentation index and developer maintenance map.
- Windows GitHub Actions validation: Python tests, PowerShell syntax, startup smoke and mocked Claude registration, including paths with spaces.

### Fixed
- Interactive menu now preserves Windows backslashes and accepts quoted project paths; POSIX drag-and-drop escaped spaces still work.
- Corrected `Makefile smoke` CLI argument order.
- README, agent onboarding, security and diagnostic guides now distinguish Windows native, WSL2 and macOS.

### Limitations
- Native Windows test and release are validated by CI; no native Windows device was accessed by the assistant.
- Graph edges for non-Python languages remain heuristic candidates; no Tree-sitter/SCIP added in this patch.

## [0.3.0] - 2026-11-06

### Added
- Read-only-source Claude Code MCP server over stdio (`guardian-mcp`), fixed to one authorized workspace.
- Developer CLI (`guardian`) for scan, freshness status, overview, symbol search, candidate callers/callees and bounded context.
- Versioned, content-addressed SQLite snapshots and incremental reuse of unchanged file parsing.
- Diagnostic JSONL session logs, aggregate `log-summary` and sanitized support ZIP for troubleshooting and performance analysis.
- Self-checks, security regression tests, GitHub Actions CI, and macOS easy-start launcher.
- `AGENTS.md`, `CLAUDE.md`, architecture/operations guides, contribution and security policies for fast agent onboarding.

### Fixed
- Repeated scans of unchanged workspaces reuse the same snapshot rather than creating duplicates.
- Source context fails closed when on-disk content differs from the indexed snapshot.
- Partial or changed source during a scan does not commit an inconsistent snapshot.
- Sensitive files and symlink paths are excluded from normal scanner traversal.

### Known limitations
- The prototype uses Python AST for Python; other languages use heuristic extraction, not Tree-sitter or compiler-grade semantics.
- `CALLS` relationships are **candidates** and must never be treated as verified cross-language dependencies.
- Index is manually refreshed (not a filesystem watcher); fresh-check currently hashes the source inventory on queries.
- Documentation generation, deterministic impact analysis, SCIP importer and graphical UI are not implemented.

## [0.2.0] - 2026-11-06

### Added
- 100-file / 100,000-line multi-language fixture generation, validation and reproducible benchmarks.
- Comparative scripts for `ripgrep`, `git grep`, Jedi and TypeScript Language Service (only where installed).
- SQLite exact-name symbol search and synthetic cross-file call candidate smoke tests.

## [0.1.0] - 2026-11-06

### Added
- Local-folder source discovery without Git, basic parser, SQLite UCG graph and basic CLI.
- Initial architecture, acceptance criteria, benchmark documentation and tests.

---

**Release rule:** Put unshipped changes under `[Unreleased]`, then move them to a dated version entry when published; keep code version (`ucg/__init__.py` and `pyproject.toml`) aligned. Never write runtime logs into `CHANGELOG.md`.
