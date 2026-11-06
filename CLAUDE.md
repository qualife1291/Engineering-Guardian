# Claude Code quick context

Read [`AGENTS.md`](AGENTS.md) first. Keep context small: inspect `docs/PROJECT_MAP.md`, then only files relevant to the task. **Do not mass-read the repository.**

This project **is the Guardian tool**, not an app to be modified by scanning. To analyze another repo, run `guardian --root /absolute/path scan` or connect Guardian MCP with `scripts/connect_claude.sh /absolute/path` on macOS/Linux, or `scripts/connect_claude.ps1 -ProjectPath 'D:\\app'` on Windows. Read `docs/DOCS_INDEX.md` for platform-specific usage.

Guardrails: source read-only; queries require fresh index; no arbitrary shell through MCP; Tree-sitter edges are syntax bindings, ast_candidate edges are heuristic, and neither is semantic proof. Run `python -m unittest discover -s tests -v` before committing. If you modify released behavior, update `CHANGELOG.md`, usage docs and tests. Do not add source code, secrets, absolute paths or prompts to diagnostic logs.

Offline-first: users can run `tree`, `outline`, `repo-map`, `hotspots`, `diff`, and `brief` without any AI account. Read `docs/OFFLINE_INTELLIGENCE.md` before changing ranking or logic. Avoid identifying examples.

Tree-sitter is optional and grammar installation must be explicit. Scans must not access the network. Change X-Ray never executes tests. See \`docs/TREE_SITTER_CHANGE_XRAY.md\`.
