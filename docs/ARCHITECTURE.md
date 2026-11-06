# POC Architecture

## Current executable implementation

This repository currently contains a dependency-free Python prototype to validate the workflow and benchmark harness. It is deliberately not represented as the production Rust implementation.

- `scanner.py`: local filesystem inventory, exclusions, file fingerprints.
- `parser.py`: Python AST extraction and heuristic regex/brace extraction for other languages.
- `store.py`: SQLite snapshot, file, symbol, edge and FTS storage.
- `engine.py`: scan orchestration and candidate graph construction.
- `cli.py`: JSON CLI for humans/automation.
- `service.py`: shared read-only-source service with mandatory freshness checks.
- `mcp.py`: Claude Code STDIO MCP server fixed to one authorized local workspace.
- `context.py`: bounded context packs that reject stale source bytes.
- `offline.py`: deterministic tree, outline, hotspots, ranked repo map, no-Git snapshot diff and Markdown brief. Uses PageRank-like ranking and a diversity-first greedy selection.
- `diagnostics.py`: anonymized JSONL timings and sanitized support ZIPs (no source code or prompts).
- `engine.py`: reuse unchanged snapshots and file-level parse results; commit graph atomically.

## Planned production implementation

Replace the prototype core with Rust, Rayon, Tree-sitter and BLAKE3. Import SCIP semantic indexes for supported languages. Keep SQLite as the first persistence layer. Add contract resolvers for MethodChannel, HTTP/OpenAPI, gRPC/Protobuf, SQL and event systems.

## Trust model

Structural matches are not automatically semantic truth. Every edge records a resolution level. Regex-based call candidates are `ast_candidate`/heuristic and must not be shown as exact calls. Unsupported or dynamic relationships remain unresolved.

## Offline-first user-facing operations

The CLI and MCP both call `GuardianService`. All offline navigation queries require a fresh snapshot, access only the configured root, and bound their outputs. The new `repo-map` is a **heuristic navigation aid**; it must not be interpreted as proof of exact call/contract dependencies. See [Offline Intelligence](OFFLINE_INTELLIGENCE.md) and [Multi-agent](MULTI_AGENT.md).
