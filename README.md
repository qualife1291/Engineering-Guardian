# Engineering Guardian

**Local-first code intelligence for developers and AI coding assistants.** Scan a folder (Git not required), find symbols and candidate call relationships, and give Claude Code small, source-backed context instead of dumping an entire codebase into an LLM.

> **Status: v0.3.0 proof of concept (Python, standard library only).** This is **not** the future Rust/Tree-sitter/SCIP engine. Python uses AST; Dart, Kotlin, TypeScript and other supported languages currently use regex/brace heuristics. All `CALLS` edges are **candidates, not compiler-verified dependencies**. Do not rely on them alone for merge/security decisions.

[Changelog](CHANGELOG.md) · [Tiếng Việt: bắt đầu nhanh](docs/EASY_START_VI.md) · [Claude Code MCP](docs/CLAUDE_CODE.md) · [Ví dụ sử dụng](docs/USAGE_EXAMPLES_VI.md) · [Đọc nhanh cho AI](AGENTS.md)

## Start in 2 minutes (macOS)

Clone the repository or extract the ZIP, then open the project:

```bash
cd /path/to/Engineering-Guardian
python3 --version             # Python 3.11+
python3 -m unittest discover -s tests -q
```

**Option A — Interactive menu:** double-click `Start Engineering Guardian.command` (or run `./"Start Engineering Guardian.command"`). Select a source folder using Finder drag-and-drop, choose scan/search/context. No Git or model API key required.

**Option B — Connect to Claude Code:** (install `claude` separately, launch Claude inside the target app)

```bash
bash scripts/connect_claude.sh '/absolute/path/to/your/app'
cd '/absolute/path/to/your/app'
claude                         # /mcp → engineering-guardian
```

The connector requests confirmation and registers a **project-local** MCP server. It never executes source code. Claude Code's other tools and permissions remain independent from Guardian's source-read-only scope.

**Option C — CLI and automation:**

```bash
python3 -m ucg.cli --root '/absolute/path/to/your/app' scan
python3 -m ucg.cli --root '/absolute/path/to/your/app' status
python3 -m ucg.cli --root '/absolute/path/to/your/app' overview
python3 -m ucg.cli --root '/absolute/path/to/your/app' search renderVideo
python3 -m ucg.cli --root '/absolute/path/to/your/app' context renderVideo --max-chars 6000
python3 -m ucg.cli --root '/absolute/path/to/your/app' log-summary
python3 -m ucg.cli --root '/absolute/path/to/your/app' support-bundle
```

All commands print JSON. For callers/callees, use `symbol_id` from `search`. Use `--help` for complete options. See [CLI examples](docs/USAGE_EXAMPLES_VI.md).

## What is implemented

| Capability | Status | Trust level |
|---|---|---|
| Scan local Git/non-Git folders, filter cache/secrets/symlinks | ✅ | Filesystem inventory |
| Parse Python functions/classes | ✅ | Python AST |
| Extract TS/JS/Dart/Kotlin/Java/SQL symbols | ⚠️ | Heuristics only |
| Build graph and query candidate callers/callees | ⚠️ | Candidate names only |
| Content-addressed snapshot + reuse unchanged parse | ✅ | Versioned SQLite |
| Detect stale files before providing source context | ✅ | File fingerprints |
| MCP stdio tools for Claude Code | ✅ | Fixed authorized root |
| JSONL diagnostics, support ZIP, performance summary | ✅ | Anonymized operational metrics |
| Full Tree-sitter, SCIP/LSP, exact cross-language impact | ⏳ | Planned, not present |
| UI, automatic README/Mermaid generation | ⏳ | Planned, not present |

## Architecture at a glance

```text
Claude Code  <-->  MCP stdio  <-->  GuardianService  <-->  UCGStore/SQLite
CLI/Menu    <--------------------------/    |
                                            +--> Scanner -> Parser -> Incremental UCG graph
                                            +--> Source-safe Context Pack
                                            +--> JSONL operational diagnostics
```

Source files are read but **not modified**. Default data home: `~/.engineering-guardian/`. Put the cache on an external SSD by setting `GUARDIAN_HOME=/Volumes/ExternalSSD/GuardianData` **before** running Guardian/Claude.

The MCP server is fixed to **one workspace path**. Scans and source queries are always initiated by a user/agent request; they are not automatic background monitors.

## Performance: understand what is measured

The repository includes reproducible 100-file × 1,000-line polyglot fixture generators plus benchmarks against baseline tools when installed. The local SQLite query speed **is not** an end-to-end ChatGPT/Claude inference speed measurement. Inspect [benchmark methodology](docs/BENCHMARK.md), [existing tool comparison](docs/EXISTING_TOOLS_COMPARISON.md), and [historical results](docs/BENCHMARK_RESULTS.md) before citing numbers.

```bash
python3 -m benchmarks.generate_fixture --output .benchmark/valid-100 --files 100 --lines 1000 --force
python3 -m benchmarks.run_benchmark --source .benchmark/valid-100 --output .benchmark/result.json --db .benchmark/index.sqlite --runs 5
```

## Report a problem or suggest an upgrade

Run `python3 -m ucg.cli --root PROJECT support-bundle` (or Claude's `guardian_support_log`). It creates an anonymized ZIP with runtime timings, cache hits, parser-warning counts and tool failure types. **No source code, prompts or project file paths are intended to be included. Inspect before sharing.** Do not upload the SQLite index. Read [diagnostics guide](docs/DIAGNOSTICS.md).

## Documentation map

- **AI agents:** [AGENTS.md](AGENTS.md) → [PROJECT_MAP.md](docs/PROJECT_MAP.md) → relevant code only. This minimizes onboarding tokens.
- **User guides:** [macOS easy start](docs/EASY_START_VI.md), [Claude Code](docs/CLAUDE_CODE.md), [use cases](docs/USAGE_EXAMPLES_VI.md).
- **Design/quality:** [architecture](docs/ARCHITECTURE.md), [test strategy](docs/TESTING.md), [acceptance](docs/ACCEPTANCE.md), [benchmarks](docs/BENCHMARK.md).
- **Operations:** [diagnostic logging](docs/DIAGNOSTICS.md), [security](SECURITY.md), [contributing](CONTRIBUTING.md), [releasing](docs/RELEASING.md), [changelog](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).