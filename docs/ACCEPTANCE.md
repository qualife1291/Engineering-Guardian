# Acceptance matrix — Engineering Guardian v0.5.0

This is an offline-first Python proof of concept (POC), not a compiler-grade semantic analyzer.

## Accepted in the current POC (covered by CI)

- Scan local folders with or without Git; exclude common secret names, generated folders and symlinks.
- Python AST and regex fallback when optional Tree-sitter grammars are not installed.
- Optional Tree-sitter parsing for supported languages after explicit grammar installation.
- Syntax-based extraction of declarations, import statements, call sites, parse errors and declaration/body fingerprints.
- Conservative resolution of explicit local import aliases, \`self\`/\`this\` methods and unique same-file declarations.
- Persist parser backend, import bindings, references and symbol hashes in versioned SQLite snapshots.
- Reuse unchanged files only when the parser backend is unchanged; source freshness is checked before queries.
- Offline Change X-Ray: symbol changes, direct/transitive static dependents, test-like files imported from changed modules and unresolved matching references.
- CLI and MCP status/navigation/impact tools; Windows and Linux CI; privacy regression checks.

## Not accepted / not implemented

- Compiler/type-checker proof, full semantic call graph or complete cross-language dependency resolution.
- Dynamic dispatch, reflection, dependency injection, runtime plugin registration and generated-code relationships.
- Complete Python package resolution, TypeScript path aliases/tsconfig project references, Java/Kotlin build graph, Go module workspaces or Rust macro expansion.
- MethodChannel, HTTP/OpenAPI, gRPC, SQL schema/dataflow and event-bus contract linking.
- Running test suites, coverage-based test selection, semantic diff or guaranteed impact completeness.
- SCIP/LSP import, native Rust scanner, GUI, file watcher or distributed scan coordinator.

## Release gates

Run all GitHub Actions jobs, including Tree-sitter integration on Linux and Windows. Keep \`CHANGELOG.md\`, \`ucg.__version__\` and \`pyproject.toml\` aligned. Audit public files for private identifiers and review [privacy notes](PRIVACY.md).

Passing tests means the implemented POC contracts work; it does NOT guarantee full codebase comprehension, correct runtime dependencies or safe changes.
