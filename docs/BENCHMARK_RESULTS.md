# Historical Benchmark Results — Valid 100 × 1,000-Line Fixture

> **Historical baseline from the initial Python prototype.** These timings were measured before v0.4.0 offline tools and do not include current index freshness checks or LLM inference. Run fresh benchmarks before making performance claims.

> This report supersedes the first POC benchmark. The original fixture generator truncated files at line 1,000 and could produce syntactically invalid source. The valid fixture pads files with comments instead.

## Dataset and validation

- 100 source files, exactly 1,000 lines each; 100,000 total lines.
- 20 files each: Python, TypeScript, Kotlin, Dart, SQL.
- Nested `domain / layer / module` tree; approximately 4.03 MB source.
- Python AST: 20/20 pass.
- TypeScript 5.8.3 `tsc`: 20/20 pass.
- Kotlin 1.9.0 compiler: 20/20 pass.
- SQLite execution: 20/20 pass.
- Dart: SDK unavailable; not compiler-validated.

## Environment

Linux x86_64 container, AMD EPYC 9V74 virtual CPU allocation (5 vCPUs), Python 3.13.5, 5.8 GiB memory visible. These are container measurements, not a guarantee for any particular developer machine.

## Guardian cold-index benchmark (5 runs)

| Measurement | Result |
|---|---:|
| Full-source read + concatenation | 9.63 ms median |
| Full-source payload | 4,027,959 bytes |
| Approximate tokens (`characters / 4`) | 1,006,990 (rough estimate only) |
| Guardian cold index | 1.100 s median |
| Indexed files / lines | 100 / 100,000 |
| Extracted symbols | 9,140 |
| Candidate edges | 17,000 |
| Warm substring symbol search (`operation_1`) | 2.67 ms median / 3.29 ms p95 |
| Warm bounded graph traversal | 0.016 ms median / 0.031 ms p95 |
| Warm context pack (`operation_1`) | 5.40 ms median / 9.33 ms p95 |
| Context pack size estimate | 7,779 tokens |
| Python process peak RSS | approximately 121,088 KB |

The exact-name lookup path is separately indexed and measures about 0.0049 ms median / 0.0069 ms p95 when the SQLite connection is already open. Broad substring search uses a fallback scan and is slower.

## Key interpretation

- Raw file reading is cheap; it is not the main bottleneck.
- The cold index takes about 1.1 seconds for the entire 100k-line fixture.
- Once indexed, exact symbol lookup and bounded graph traversal are very fast.
- Guardian should not replace ripgrep or Git grep for text search.
- Guardian's value is the persistent structure/relationship layer and compact, evidence-backed context selection.
- The current call graph is heuristic and is not compiler-verified.

## Existing-tool comparison

See `docs/EXISTING_TOOLS_COMPARISON.md` and the raw JSON reports. In summary, `git grep` was faster than `rg` for the tested literal search, including `git grep --no-index` on a static folder outside any Git repository. Guardian's warm graph traversal was faster than warm Jedi/TypeScript Language Service references in the small same-file fixture, but the semantic correctness of those results is not yet equivalent or proven.

## ChatGPT comparison limitation

No live ChatGPT full-source inference run was performed. The token count is only a `characters / 4` estimate, not a tokenizer result. Do not claim end-to-end Guardian superiority until identical tasks are run against (A) full-source ChatGPT and (B) the same model with Guardian context packs, measuring correctness, evidence coverage, input tokens, time-to-first-useful-answer, and total latency.

## Remaining gaps

- Tree-sitter not integrated; current non-Python extraction still uses regex/brace heuristics.
- SCIP/LSP and compiler-verified references not integrated.
- Universal Ctags not benchmarked because it is not installed.
- Cross-file smoke test only covers one unique-name call; imports, overloads, duplicate symbols, dynamic dispatch, and cross-language contracts are not solved.
- Incremental re-indexing is not implemented.
- Dart syntax validation unavailable in this environment.
- The POC is Python, not the planned Rust production core.
