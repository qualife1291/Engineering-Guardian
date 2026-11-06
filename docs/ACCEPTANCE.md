# POC Acceptance Criteria

## Current prototype checks

- Local non-Git folder scanning.
- File inventory and language detection for supported extensions.
- Python AST symbol extraction.
- Heuristic structural symbol extraction for TypeScript, JavaScript, Dart, Kotlin, Java and SQL.
- SQLite persistence and symbol search.
- Basic graph traversal API in the Python store.
- Reproducible synthetic fixture generation.
- Benchmark output with explicit limitations.

## Not yet accepted / not implemented

- Production Rust scanner.
- Tree-sitter parser integration.
- SCIP import and compiler-grade references.
- Correct cross-language contract resolution.
- True incremental parsing/index invalidation.
- Exact semantic call graph for dynamic languages.
- Production API/MCP/UI.
- End-to-end ChatGPT vs Guardian inference latency comparison.

## Release gate

Do not call this production-ready until the unimplemented items are completed, security tests pass, and accuracy/performance targets are measured on real projects.
