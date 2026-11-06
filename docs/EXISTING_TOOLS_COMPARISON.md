# Existing Tool Comparison — Historical POC Baselines

> These results predate the v0.4.0 offline navigation layer. They mix different tool startup and index states and do NOT prove a universal speed advantage. Rebenchmark on identical real repositories for developer-level metrics.

## Executive result

Engineering Guardian should **not** replace ripgrep, Git grep, Tree-sitter, language servers, or SCIP. The best design is to orchestrate them and persist their outputs in one searchable graph/context layer.

The current POC is competitive on warm, indexed symbol/reference traversal in a small synthetic same-file test. It is not yet a compiler-accurate code intelligence engine. The strongest established competitors are Tree-sitter for syntax structure and SCIP/LSP-based indexers for precise references.

## Reproducible fixture

- 100 source files × 1,000 lines = 100,000 source lines.
- 20 files each: Python, TypeScript, Kotlin, Dart, SQL.
- Nested `domain / layer / module` folders.
- Approximately 4.03 MB of source text.
- Unlike the first fixture generator, the valid generator pads source with comments rather than truncating code at line 1,000.
- Validation: Python AST 20/20, TypeScript `tsc` 20/20, Kotlin compiler 20/20, SQLite SQL execution 20/20. Dart SDK was unavailable, so Dart syntax was not compiler-validated.

The initial `generate_fixture.py` implementation truncated files at the line limit and produced invalid Python/TypeScript files. Its results are superseded by `generate_valid_fixture.py` and the reports below.

## Local command-line comparison

25 runs per CLI command. Times include process startup for external commands. Guardian is measured inside an already-running Python process with its SQLite database open, so these numbers are not strictly apples-to-apples.

### File inventory

| Tool | Median | P95 | Notes |
|---|---:|---:|---|
| `git ls-files` | 1.41 ms | 2.00 ms | Fast for tracked files only |
| `rg --files` | 4.02 ms | 5.38 ms | Filesystem discovery; honors ignore rules |
| `find` | 7.16 ms | 14.09 ms | General filesystem traversal |

### Exact symbol search

| Tool | Median | P95 | Notes |
|---|---:|---:|---|
| `git grep` (working tree) | 2.93 ms | 8.56 ms | Tracked worktree |
| `git grep --no-index` | 2.90 ms | 3.80 ms | Tested against a folder outside any Git repository |
| GNU `grep -R` | 3.44 ms | 4.04 ms | Recursive text search |
| `rg` | 6.69 ms | 9.45 ms | Recursive text search |
| Guardian exact symbol lookup | 0.0049 ms | 0.0069 ms | Warm in-process SQLite indexed lookup |

The Guardian exact lookup is much faster once its index is open, but it must pay the initial indexing cost (about 1.14 seconds for this 100k-line fixture). The CLI timings include process startup; do not turn these into a universal speed multiplier.

### Reference search vs graph traversal

| Operation | Median | P95 | Output |
|---|---:|---:|---|
| `git grep` call-text search | 3.11 ms | 6.15 ms | 6 matching lines |
| `rg` call-text search | 5.88 ms | 7.74 ms | 6 matching lines |
| Guardian forward graph traversal | 0.0156 ms | 0.0223 ms | 3 candidate call edges |

Text search finds matching lines. Guardian returns structured source-to-target edges with evidence file and line, but those edges are currently heuristic candidates.

## Language-native references comparison

The tools below only analyze their own language subset; they do not scan the entire five-language corpus as one engine. Warm reference lookup is measured after each tool's initial setup.

| Language | Existing tool | Warm median | Warm P95 | Guardian reverse graph median | Reference count |
|---|---|---:|---:|---:|---:|
| Python | Jedi 0.20.0 | 13.30 ms | 17.98 ms | 0.0092 ms | 5 calls (Jedi returns 5 + definition) |
| TypeScript | TypeScript Language Service 5.8.3 | 0.427 ms | 1.169 ms | 0.0115 ms | 7 calls (TS LS returns 7 + definition) |

In this simple same-file fixture, Guardian found the same call sites as Jedi and TypeScript Language Service. This is a useful performance signal, **not proof of equal semantic correctness**: Guardian edges are name-based candidates, while language-native tools use language-aware analysis. First-query setup took roughly 0.69 s for Jedi and 0.58 s for TypeScript LS; those figures are not directly comparable with Guardian's all-language cold index.

A separate two-file Python smoke test verifies one uniquely named cross-file call candidate. This does not yet validate imports, overloads, namespaces, dynamic dispatch, reflection, generated code, or ambiguous duplicate symbols across a large repository.

## Tool availability in the benchmark environment

| Tool | Installed? | Intended role |
|---|---|---|
| ripgrep 14.1.1 | Yes | Fast text search and discovery |
| Git 2.47.3 / `git grep` | Yes | Tracked-tree search; `--no-index` also works on static folders |
| TypeScript 5.8.3 | Yes | Compiler and language-service references for TS |
| Kotlin compiler 1.9.0 | Yes | Syntax/type validation for Kotlin |
| Python AST / Jedi 0.20.0 | Yes | Python structure and references |
| Tree-sitter | No | Multi-language concrete syntax trees and incremental parsing |
| Universal Ctags | No | Broad symbol/tag inventory, including JSON output |
| SCIP indexers | No | Compiler/language-tooling-derived symbol/reference indexes |
| Semgrep / ast-grep | No | Structural pattern search and code queries |
| Dart SDK | No | Dart compile/analyzer validation |

## What the established tools already do well

- **ripgrep** is the baseline for fast recursive text search and should remain the text-search backend.
- **Git grep** is fast on tracked worktrees. `git grep --no-index` also supports non-Git folders, so static source directories are not a reason to reimplement text search.
- **Tree-sitter** produces concrete syntax trees, supports incremental updates, and is designed to remain useful with syntax errors. It is the preferred structural parsing layer, not a semantic type resolver.
- **Universal Ctags** can emit JSON Lines tags with symbol name, path, language, kind, and scope. It is a useful broad fallback for symbol inventory, but tags alone do not provide a trustworthy call graph.
- **SCIP / language servers** provide the strongest path to precise definition/reference relationships when a language indexer and build context are available. Sourcegraph's precise navigation uses SCIP and requires uploading language-specific indexes; its documented precise-navigation product is Enterprise-gated.

## Recommended Engineering Guardian architecture

1. **Discovery:** filesystem walker + ignore rules; use `rg --files`/`git ls-files` adapters where useful. Never require `.git`.
2. **Syntax:** Tree-sitter parsers for language-neutral structural extraction and incremental updates.
3. **Semantic adapters:** SCIP or LSP/language-service adapters for precise definitions, references, implementations, types, and import resolution.
4. **Fallback:** Universal Ctags for symbol inventory where no semantic adapter exists; regex only as a last-resort low-confidence fallback.
5. **Unified graph:** normalize symbol IDs and relationships into Guardian's graph, preserving provenance and confidence (`compiler_verified`, `lsp_resolved`, `tree_sitter_structural`, `heuristic`).
6. **Impact/context:** graph traversal, change impact, source evidence, and bounded context packs for the LLM.
7. **Incremental updates:** file fingerprint + changed-file parse + affected-edge invalidation; do not rescan all files after every edit.

## Next benchmark gates

Before claiming production readiness, add:

- Tree-sitter benchmark for parse throughput, error recovery, and incremental reparse after one-file edits.
- Universal Ctags symbol count/accuracy and JSON indexing benchmark.
- SCIP/LSP definition/reference accuracy for TypeScript, Python, Kotlin, and additional available indexers.
- Cross-file fixture with imports, duplicate symbol names, overloads, interfaces/implementations, and dependency injection.
- Real repository benchmark (not only generated fixtures), including non-Git static folder mode.
- Precision/recall against manually curated ground truth; latency alone is insufficient.
- End-to-end same-model comparison: full source vs Guardian context pack, measuring answer correctness, evidence coverage, input tokens, and time-to-first-useful-answer.

## Reproduce

```bash
python3 -m benchmarks.generate_fixture --output ./.benchmark/valid-100 --files 100 --lines 1000 --force
python3 -m unittest discover -s tests -v
python3 -m benchmarks.compare_existing_tools --source ./.benchmark/valid-100 --output ./reports/tool-comparison-valid-100.json --runs 25
python3 -m benchmarks.language_service_comparison ./.benchmark/valid-100
python3 -m benchmarks.run_benchmark --source ./.benchmark/valid-100 --output ./reports/benchmark-valid-100.json --db ./.benchmark/benchmark-valid.sqlite --runs 5
```

Machine details, raw run samples, and exact result records are in `reports/tool-comparison-valid-100.json`, `reports/language-service-comparison-valid-100.json`, and `reports/benchmark-valid-100.json`.
