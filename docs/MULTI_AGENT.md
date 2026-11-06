# Multi-agent support and terminal-only usage

**Engineering Guardian is a deterministic local code intelligence tool, not an autonomous AI agent.** AI clients are optional. It exposes a read-only-source MCP server for compatible clients and a CLI for people and automation.

## Supported connectivity model

| Client | Integration | Status |
|---|---|---|
| No AI, Terminal / PowerShell | \`python -m ucg.cli\` | Working |
| Claude Code | Project-local stdio MCP script | Working, integration smoke-tested |
| Other MCP clients / agents (Codex, VS Code extensions, etc.) | Configure stdio executable + arguments below | Protocol-compatible path; client-specific setup not certified |
| CI / shell scripts | CLI JSON outputs | Working |
| Cloud hosted remote agents | Not exposed | No remote HTTP server in current version |

Use this command as the MCP server process (from any directory):

\`\`\`text
python /absolute/path/to/Engineering-Guardian/scripts/guardian_mcp.py --root /absolute/path/to/project
\`\`\`

On Windows use \`C:\Projects\Engineering-Guardian\.venv\Scripts\python.exe\` as executable and \`C:\Projects\Engineering-Guardian\scripts\guardian_mcp.py\` with \`--root C:\Projects\sample-app\` as distinct arguments.

Configure the AI client's MCP settings to launch the command over **stdio**; do not point it at a network URL. Restart the client and verify \`guardian_index_status\`, \`guardian_tree\` or \`guardian_parser_status\`.

## Safest multi-agent usage

1. One agent or developer performs \`guardian_scan\` first.
2. The other agents call only navigation commands (\`guardian_tree\`, \`guardian_repo_map\`, \`guardian_outline\`, \`guardian_find_symbol\`, \`guardian_get_context\`).
3. After code edits, run exactly one refresh and obtain the new snapshot ID.
4. Each analysis includes the snapshot ID, relative file paths, and what could not be resolved.
5. Treat \`tree_sitter_*\` as conservative syntax bindings and \`ast_candidate\` as heuristic; neither is compiler-certified or runtime-observed.
6. Avoid concurrent full scans; the present release does not have a distributed scan coordinator.

The index is in an external data home (\`GUARDIAN_HOME\`, default \`~/.engineering-guardian\`) so agents for the *same root* reuse it. Different roots receive separate databases. Tool results are bounded and do not execute code or write to the scanned source folder.

An MCP result containing source snippets may be transmitted to the model provider by its AI client. Non-AI commands never contact a model.

## Prompt for any MCP-capable AI client

> Use Engineering Guardian to inspect the authorized project. First check the index status, scan only if necessary, then request the folder tree and a focused repo map. Inspect outlines before reading long source files. Cite symbol and file locations. Treat candidate call edges as hypotheses requiring source verification. Do not claim full coverage when the index is incomplete. Do not edit project files.


## New v0.5.0 MCP tools

- \`guardian_parser_status\`: shows which grammar binaries are already installed; it never downloads.
- \`guardian_change_impact\`: compares two indexed snapshots and returns changed symbols, reverse dependents, suggested tests and unresolved references.

Use the grammar install CLI before scanning if Tree-sitter coverage is desired. MCP cannot install grammars or initiate network downloads. Change X-Ray is static analysis; it does not run test commands.
