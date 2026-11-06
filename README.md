# Engineering Guardian

**Local-first code intelligence for developers and AI coding assistants.** Scan a folder (Git not required), find symbols and candidate call relationships, and give Claude Code small, source-backed context instead of dumping an entire codebase into an LLM.

> **Status: v0.5.0 proof of concept.** Tree-sitter is optional; after explicitly installing local grammars, supported languages use syntax-tree extraction. If a grammar is unavailable, Python AST or regex/brace fallback is used. `tree_sitter_*` edges are conservative syntactic bindings, while `ast_candidate` edges are heuristics. Neither is compiler/type-checker proof; dynamic dispatch and reflection can remain unresolved.

[Changelog](CHANGELOG.md) · [Tiếng Việt: bắt đầu nhanh](docs/EASY_START_VI.md) · [Claude Code MCP](docs/CLAUDE_CODE.md) · [Ví dụ sử dụng](docs/USAGE_EXAMPLES_VI.md) · [Đọc nhanh cho AI](AGENTS.md)

## No AI? Use Engineering Guardian entirely from your terminal

Guardian is **offline-first**. All of these features work with Python and SQLite, even when your AI subscription hits a request/token limit, or you do not use any AI agent:

~~~bash
python3 -m ucg.cli --root /path/to/project scan
python3 -m ucg.cli --root /path/to/project tree --depth 4
python3 -m ucg.cli --root /path/to/project hotspots --min-lines 300
python3 -m ucg.cli --root /path/to/project outline src/example.py
python3 -m ucg.cli --root /path/to/project repo-map --focus processOrder --max-chars 4000 --text
python3 -m ucg.cli --root /path/to/project brief --format markdown > codebase-brief.md
# After modifying the project, run scan again, then:
python3 -m ucg.cli --root /path/to/project diff
python3 -m ucg.cli --root /path/to/project impact
~~~

**Large source files** can be navigated via function outlines rather than read in full. PageRank-style file ranking and a diversity-first symbol map prioritize what to inspect. The exact content hash diff works without Git. Optional Tree-sitter adds syntax-aware symbols/imports/call sites; [Change X-Ray](docs/TREE_SITTER_CHANGE_XRAY.md) compares indexed snapshots and traces statically resolved dependents without running tests.

**AI integrations are optional:** Claude Code has the tested project-scoped MCP workflow; other stdio MCP-capable clients can use the same server (see [Multi-agent guide](docs/MULTI_AGENT.md)). No cloud endpoint or user source is automatically uploaded by Guardian.

## Quick start by operating system

| System | One-click menu | Claude Code MCP guide |
|---|---|---|
| macOS / Apple Silicon | `Start Engineering Guardian.command` | [Claude Code](docs/CLAUDE_CODE.md) |
| **Windows 10/11 native** | **`Start Engineering Guardian.cmd`** | **[Windows / PowerShell setup](docs/WINDOWS_SETUP_VI.md)** |
| Linux / WSL2 | Python CLI or Bash launcher | [Claude Code](docs/CLAUDE_CODE.md) |

Guardian itself needs **Python 3.11+**, no Rust, Docker or model API key. Tree-sitter is optional; the core fallback scanner works without it. Git is optional when extracting a downloaded ZIP. Python environments for native Windows and WSL2 are separate.

### macOS (2-minute setup)

Clone the repository or extract the ZIP, then open the project:

```bash
cd /path/to/Engineering-Guardian
python3 --version             # Python 3.11+
python3 -m unittest discover -s tests -q
# Optional: enable syntax-tree parsing, then explicitly cache grammars.
python3 -m pip install -e ".[treesitter]"
python3 -m ucg.cli --root . parsers install --languages python,typescript,javascript,dart,kotlin,java,sql,go,rust
~~~

**Option A — Interactive menu:** double-click `Start Engineering Guardian.command` (or run `./"Start Engineering Guardian.command"`). Select a source folder using Finder drag-and-drop, choose scan/search/context. No Git or model API key required.

**Option B — Connect to Claude Code:** (install `claude` separately, launch Claude inside the target app)

```bash
bash scripts/connect_claude.sh '/absolute/path/to/your/app'
cd '/absolute/path/to/your/app'
claude                         # /mcp → engineering-guardian
```

The connector requests confirmation and registers a **project-local** MCP server. It never executes source code. Claude Code's other tools and permissions remain independent from Guardian's source-read-only scope.

### Windows 10/11 native (PowerShell)

Download/clone this repository, then **double-click `Start Engineering Guardian.cmd`** to use the Terminal menu. The launcher creates an isolated local `.venv` with no external Python dependencies.

To connect Claude Code from PowerShell (replace the sample paths):

```powershell
cd 'C:\\Projects\\Engineering-Guardian'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\connect_claude.ps1 -ProjectPath 'C:\\Projects\\sample-app'
cd 'C:\\Projects\\sample-app'
claude
# In Claude Code: /mcp
```

See the [step-by-step Windows guide](docs/WINDOWS_SETUP_VI.md) for Python, Windows native vs WSL2, paths with spaces, caching on a second disk, diagnostics and troubleshooting.

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

Source files are read but **not modified**. Default data home: `~/.engineering-guardian/`. Put the cache on an external SSD by setting `GUARDIAN_HOME=/path/to/GuardianData` **before** running Guardian/Claude.

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

- **AI agents:** [AGENTS.md](AGENTS.md) → [PROJECT_MAP.md](docs/PROJECT_MAP.md) → relevant code only.
- **Contributors:** [DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for OS-specific setup and quality gates. This minimizes onboarding tokens.
- **Documentation index:** [DOCS_INDEX.md](docs/DOCS_INDEX.md) — open only the guide you need.
- **User guides:** [Windows native / WSL2](docs/WINDOWS_SETUP_VI.md), [macOS easy start](docs/EASY_START_VI.md), [Claude Code](docs/CLAUDE_CODE.md), [use cases](docs/USAGE_EXAMPLES_VI.md).
- **Design/quality:** [architecture](docs/ARCHITECTURE.md), [test strategy](docs/TESTING.md), [acceptance](docs/ACCEPTANCE.md), [benchmarks](docs/BENCHMARK.md).
- **Operations:** [diagnostic logging](docs/DIAGNOSTICS.md), [security](SECURITY.md), [contributing](CONTRIBUTING.md), [releasing](docs/RELEASING.md), [changelog](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).

## Public repository privacy

All published usage examples must be generic. See [privacy and history policy](docs/PRIVACY.md). Runtime logs are separate from version history; see [CHANGELOG](CHANGELOG.md) and [diagnostics](docs/DIAGNOSTICS.md).


## Tree-sitter and Change X-Ray

Install the optional engine and grammar binaries only when you choose to enable them:

~~~bash
python3 -m pip install -e ".[treesitter]"
python3 -m ucg.cli --root /path/to/project parsers status
python3 -m ucg.cli --root /path/to/project parsers install --languages python,typescript,javascript,dart,kotlin,java,sql,go,rust
python3 -m ucg.cli --root /path/to/project scan
python3 -m ucg.cli --root /path/to/project impact
~~~

The install command downloads grammars into the local user cache. Scanning never downloads parsers. Change X-Ray compares two indexed snapshots and returns static dependents/test suggestions; it does not execute tests or guarantee runtime impact. See [Tree-sitter & Change X-Ray](docs/TREE_SITTER_CHANGE_XRAY.md).
