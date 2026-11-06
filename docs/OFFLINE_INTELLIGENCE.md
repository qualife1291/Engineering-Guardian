# Offline codebase intelligence (no AI, no Git required)

Engineering Guardian can be used entirely from a local terminal. **No model, network, LLM API key or token quota is needed.** Only Python 3.11+, local source files and the SQLite index are required.

## Everyday developer workflow

Run these commands from the Guardian repository root. Replace PROJECT with your folder path.

\`\`\`bash
python3 -m ucg.cli --root /path/to/project scan
python3 -m ucg.cli --root /path/to/project tree --depth 4
python3 -m ucg.cli --root /path/to/project hotspots --min-lines 300
python3 -m ucg.cli --root /path/to/project outline src/example.py
python3 -m ucg.cli --root /path/to/project repo-map --focus order --max-chars 4000 --text
python3 -m ucg.cli --root /path/to/project brief --format markdown > guardian-brief.md
# After editing the application with your own editor:
python3 -m ucg.cli --root /path/to/project scan
python3 -m ucg.cli --root /path/to/project diff
\`\`\`

The brief is written only where *you* redirect stdout; Guardian does not edit its target source tree. On Windows use \`.venv\Scripts\python.exe\` and a quoted Windows project path.

## Which algorithm solves which problem?

| Problem | Command | Technique | Reliability |
|---|---|---|---|
| Nested directories and unknown entry points | \`tree\` | Indexed path-prefix aggregation | Exact for eligible scanned files |
| File thousands of lines long | \`outline\` | Python AST / language heuristics | Position accuracy varies by parser |
| Which symbols should be read first? | \`repo-map\` | PageRank-like *candidate* file graph, lexical relevance, greedy diversity selection | Navigation heuristic; not proven criticality |
| Large, hard-to-review code | \`hotspots\` | File/function span outlier signals | Size signals only; not a quality or formatting verdict |
| Changed files, no Git available | \`diff\` | Content-fingerprint comparison between stored snapshots | Exact file changes; heuristic symbol changes |
| No quota for the AI | \`brief --format markdown\` | Deterministic report template | Inventory and evidence, not business understanding |
| Multiple AI agents | MCP tools | Shared, versioned SQLite and bounded tool results | Snapshot-checked; no automatic agent coordination |

## Other disciplines worth borrowing from

- **Information retrieval:** BM25/lexical ranking for discovery; query-focused context instead of repository dumps.
- **Network science:** damped random walk (PageRank) for centrality. In v0.4, candidate call edges are insufficient for definitive architectural claims.
- **Information diversity:** MMR-inspired greedy per-file quota to keep giant files from monopolizing a small navigation map. This is NOT a mathematically exact MMR solver.
- **Change detection:** content hashes for snapshot comparison, independent of version control.
- **Operations research:** explicit memory/output budgets so a query can bound work and context size.
- **Testing theory (future):** set-cover on real test coverage, not available yet.
- **Information theory (future):** entropy/co-change history for suspiciously distributed responsibilities, only after verified data is available.

Useful prior art: [Aider Repo Map](https://aider.chat/docs/repomap.html), [ast-grep](https://ast-grep.github.io/), [SQLite FTS5](https://www.sqlite.org/fts5.html), and [SCIP](https://github.com/sourcegraph/scip).

## What v0.4 deliberately does not do

It does not reconstruct every business flow, build a precise Dart/Kotlin/TypeScript call graph, report undocumented functions, perform semantic diff or apply auto-formatting. It does not execute the app or run arbitrary shell commands through MCP.

**Current performance caveat:** to prevent serving stale data, the service checks source fingerprints before queries. On very large source trees this O(files + input bytes) scan can dominate latency. We therefore report complete command timings instead of relying on tiny in-database graph query timings.

For precision claims, benchmark against a manually verified set of symbols, cross-file references and expected impacts. Short response time alone does not mean accurate reasoning.
