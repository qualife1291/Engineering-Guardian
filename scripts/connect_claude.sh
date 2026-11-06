#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT="${1:-$PWD}"
if [[ ! -d "$PROJECT" ]]; then echo "Project folder not found." >&2; exit 2; fi
PROJECT="$(cd "$PROJECT" && pwd -P)"
PYTHON=""
if [[ -x "$ROOT/.venv/bin/python" ]]; then PYTHON="$ROOT/.venv/bin/python"; fi
if [[ -z "$PYTHON" ]]; then
  for py in python3.13 python3.12 python3.11 python3; do
    if command -v "$py" >/dev/null 2>&1 && "$py" -c 'import sys; exit(sys.version_info<(3,11))' >/dev/null 2>&1; then
      PYTHON="$(command -v "$py")"; break
    fi
  done
fi
if [[ -z "$PYTHON" ]]; then echo "Python 3.11+ required." >&2; exit 2; fi
if ! command -v claude >/dev/null 2>&1; then
  echo "Claude Code CLI not found; install Claude Code first." >&2; exit 2
fi
printf '\nEngineering Guardian MCP connection (LOCAL scope)\n'
printf '  Project: %s\n  Guardian: %s\n  Python: %s\n' "$PROJECT" "$ROOT" "$PYTHON"
printf '  Access: READ source under selected project; WRITE only diagnostics/cache under ~/.engineering-guardian\n'
printf '  Note: Claude still receives selected code snippets when it calls get_context.\n'
read -r -p 'Connect this project to Claude Code? [y/N] ' ok
if [[ "$ok" != "y" && "$ok" != "Y" ]]; then echo "Cancelled."; exit 0; fi
(
  cd "$PROJECT"
  claude mcp add --scope local --transport stdio engineering-guardian -- \
    "$PYTHON" "$ROOT/scripts/guardian_mcp.py" --root "$PROJECT"
  claude mcp list
)
echo "Done. Reopen Claude Code in your project and run /mcp to verify connection."
