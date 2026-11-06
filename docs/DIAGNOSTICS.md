# Runtime diagnostics, quality and performance

`CHANGELOG.md` records **version history**. Runtime diagnostics are machine-readable **per-session JSONL** to help improve the engine after users run it on real projects.

## Where logs live

`$GUARDIAN_HOME/diagnostics/YYYY-MM-DD/<session-id>.jsonl` (default `~/.engineering-guardian`).

Each line is a self-contained JSON record with version, UTC timestamp, anonymized workspace hash, event, status and an allowlist of metrics. Examples of logged metrics:

- Scan: `files`, `lines`, `symbols`, `edges`, `parsed_files`, `reused_files`, `cache_hit`, `skipped_files`, `diagnostic_count`.
- Speed: `scan_ms`, `parse_ms`, `graph_ms`, `persist_ms`, `duration_ms`.
- AI context: `context_characters`, `context_tokens_estimate`, `truncated`.
- Tools: permitted MCP tool name, duration, success/failure and exception **type**, not exception text.

**Limitations:** counts and response times are operational quality indicators. They do not establish symbol precision, call-graph recall, correctness of reasoning, or safety of changes. For those, compare findings to manually labeled test fixtures.

For Windows native, `$GUARDIAN_HOME` is a PowerShell environment variable (`$env:GUARDIAN_HOME = 'C:\\GuardianData'`) and defaults to `%USERPROFILE%\\.engineering-guardian`. WSL2 paths and Windows paths must not be mixed. See [Windows setup](WINDOWS_SETUP_VI.md).

## View metrics summary without sharing source

```bash
python3 -m ucg.cli --root /path/to/project log-summary
```

This reports scan cache-hit ratio, parsed/reused file counts, parser warning counts, tool errors, and median/p95 durations. It does not measure semantic precision or recall.

## Export a support ZIP (recommended for sending feedback)

```bash
cd /path/to/Engineering-Guardian
python3 -m ucg.cli --root '/path/to/your/project' support-bundle
```

Or ask Claude to call `guardian_support_log`. The output path is printed, e.g. `~/.engineering-guardian/guardian-support-YYYYMMDD-HHMMSS.zip`.

The exporter re-sanitizes event fields and includes `environment.json` (OS, Python version, architecture, log count), plus matching anonymized JSONL events. **It does not include source files, snippets, prompts, file paths, API keys or SQLite databases by design.** Review the ZIP before sharing.

## Diagnosing common problems

| Symptom | Command | Interpretation |
|---|---|---|
| New changes not visible | `guardian --root PROJECT status` | Stale index → scan again |
| Scan slow | `guardian --root PROJECT scan` | Compare `scan_ms`, `parse_ms`, `persist_ms`; check cache hit |
| Missing function | `guardian --root PROJECT search NAME` | Unsupported extension/parser, nested scope or heuristic miss |
| Unexpected call edges | `guardian --root PROJECT callers ID` | Candidate relation; independently verify |
| MCP failure | `claude mcp list`, `/mcp` | Check scope, Python 3.11+ and path |
| Need upgrade | `guardian --root PROJECT support-bundle` | Share sanitized ZIP and describe expected behavior |

### Privacy caveats

Absolute source paths, function names and source content are omitted from logs. However, file/line counts, OS type and anonymized workspace hash can reveal coarse project characteristics. If that matters, inspect locally and do not share the ZIP. Support bundles are not automatically uploaded to any service.
