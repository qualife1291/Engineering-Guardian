# Acceptance matrix — Engineering Guardian v0.4.0

This is an offline-first Python proof of concept (POC), not a verified semantic program-analysis system.

## Accepted in the current POC (covered by CI)

- Scan local folders with or without Git; exclude common secret names, generated folders and symlinks.
- Python AST symbol extraction, heuristic structural extraction for other supported languages.
- Versioned SQLite snapshots, parsing reuse, changed-file reparse and atomic commits.
- Source fingerprint checks to refuse stale queries.
- Symbol lookup, candidate callers/callees, MCP stdio and local CLI JSON.
- Offline tree, outline, hotspots, repo-map, diff and deterministic Markdown brief.
- JSONL diagnostic metrics and sanitized support bundles.
- Windows and Ubuntu CI; public-example privacy regression tests.

## Not accepted or not implemented

- Verified cross-language call graph, MethodChannel/HTTP event resolution or dataflow.
- Compiler-grade SCIP/LSP and native Tree-sitter/Rust performance core.
- Automatic formatting, documentation coverage and semantic code-quality verdicts.
- Runtime behavior reconstruction or semantic equivalence and impact guarantees.
- File watchers, multi-process scan coordination and complete semantic invalidation.
- Interactive code-graph GUI, self-updating wiki or integrated code editor.
- End-to-end ChatGPT versus Guardian inference-latency win.
- Production privacy/data-governance certification for arbitrary private code.

## Release gates

Run all GitHub Actions test jobs on Windows and Ubuntu. Keep the changelog, ucg.__version__ and pyproject.toml aligned. Audit public source/docs/reports for private identifiers. Read [privacy notes](PRIVACY.md).

Passing tests means the POC contracts work; it does NOT guarantee full codebase comprehension or safe changes.
