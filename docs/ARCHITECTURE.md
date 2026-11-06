# Architecture — Engineering Guardian v0.5.0

## Executable implementation

The current product is an offline-first Python POC. It is not a Rust/SCIP compiler index.

- \`scanner.py\`: local filesystem inventory, exclusions and BLAKE2b fingerprints.
- \`parser.py\`: dependency-free Python AST and heuristic fallback parser.
- \`treesitter.py\`: optional Tree-sitter grammar availability, syntax extraction, imports, call references, local binding resolution and body fingerprints. It never downloads a grammar during scan.
- \`engine.py\`: snapshot orchestration, unchanged-file reuse, reference resolution, candidate/structural graph creation and atomic commit.
- \`store.py\`: SQLite snapshots plus files, symbols, edges, parser metadata, imports, references and per-symbol fingerprints.
- \`offline.py\`: tree, outline, hotspots, repo map, snapshot diff, Markdown brief and Change X-Ray.
- \`service.py\`: common freshness-checked boundary for CLI and MCP.
- \`cli.py\`: offline CLI, explicit grammar installation and impact analysis.
- \`mcp.py\`: stdio MCP tools for status, scan, navigation, parser status and Change X-Ray.
- \`context.py\`: bounded source-backed context that refuses stale snapshots.
- \`diagnostics.py\`: allowlisted operational telemetry and sanitized support bundles.

## Parser lifecycle and offline guarantee

1. Install the optional \`treesitter\` Python extra if syntax-tree support is wanted.
2. Run \`guardian parsers install --languages ...\` explicitly to download chosen grammar binaries to the user cache.
3. Scan checks only whether the requested grammar is already available locally. It does not fetch a manifest, binary, model or source.
4. If no grammar is installed, Python AST / regex fallback remains available.
5. File reuse requires the same parser backend; installing a grammar after a previous scan causes affected files to be parsed again.

## Resolution levels

- \`tree_sitter_import_binding\`: explicit local import alias resolves to one local declaration.
- \`tree_sitter_same_class\`: \`self\`/\`this\`/\`cls\` receiver and one matching method in the enclosing type.
- \`tree_sitter_same_file_unique\`: one same-file declaration matches an unqualified call.
- \`ast_candidate\`: globally unique unresolved name or dependency-free heuristic candidate; not a verified binding.
- \`unresolved\`: dynamic, ambiguous or unsupported references are retained without an edge.

Tree-sitter gives syntactic structure. It does not perform compiler type checking, runtime dispatch, reflection analysis or dependency-injection resolution.

## Change X-Ray

Compare two immutable snapshots, identify changed declarations using signature/body hashes, then walk reverse edges for dependents. Resolved imports from test-like files provide test suggestions. Unresolved references to changed names are shown as unknowns. No tests are executed and no source file is modified.

## Future work

SCIP/LSP compiler indexes, cross-language event/HTTP/SQL contracts, dependency-injection maps, dataflow/slicing, test coverage set-cover and a visual graph UI remain future work.
