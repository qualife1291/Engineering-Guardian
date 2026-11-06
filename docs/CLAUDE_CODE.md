# Claude Code + Engineering Guardian (macOS / Linux)

## One-time setup

1. Install Python 3.11+ and Claude Code CLI (`claude`).
2. Clone or extract Engineering Guardian **beside** your application folder:

```text
/Volumes/ExternalSSD/development/HTH/
├── Engineering-Guardian/
└── airvoice-wireless-app/
```

3. In a Terminal:

```bash
cd '/Volumes/ExternalSSD/development/HTH/Engineering-Guardian'
python3 -m unittest discover -s tests -q
bash scripts/connect_claude.sh '/Volumes/ExternalSSD/development/HTH/airvoice-wireless-app'
```

The script displays the target workspace and permissions and **asks for confirmation** before registering a project-local MCP server. It does not modify the target source. If a previous `engineering-guardian` MCP registration exists, remove/reconfigure it using `claude mcp remove` as appropriate before retrying.

4. Start Claude Code in the target app directory, run `/mcp`, and verify `engineering-guardian` is connected.

## Suggested prompts

**Architecture:** “Use `guardian_scan` if needed, then `guardian_overview` and `guardian_find_symbol` to map the eSIM entry points. Only read source snippets relevant to the call path. Mark unverified edges explicitly.”

**Callers:** “Use `guardian_find_symbol` for `downloadProfile`, then `guardian_get_callers` using the returned `symbol_id`. Verify important candidates against source before recommending a change.”

**Debugging:** “Check `guardian_index_status`, refresh stale index, then request `guardian_get_context` for the failing symbol. Include source evidence and coverage gaps in your answer.”

**Performance/support:** “Use `guardian_support_log` to export the sanitized ZIP; inspect it before sharing. Never send the SQLite database.”

## Permission & scope

- MCP is registered in Claude's `local` scope for the selected project.
- Guardian itself writes only external index/cache/diagnostics; Claude Code may have other capabilities based on your Claude Code permission settings. Guardian does **not** restrict Claude's other tools.
- Configure `$GUARDIAN_HOME` before starting Claude Code if you want the index/logs on an external SSD.
- To register Guardian for a **second** project, rerun `connect_claude.sh` with that project's absolute path.

## Limitations

- The current graph is heuristic, particularly for Dart/Kotlin/TypeScript: do not trust `CALLS` alone to assess change safety.
- Project file watchers are not implemented: run `guardian_scan` again after edits.
- MCP does not write README/diagrams; those remain manual AI tasks until documentation generation is implemented.
