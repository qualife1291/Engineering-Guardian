# Security policy

## Trust boundary

Guardian scans code that may be untrusted. It **never** executes application source, build scripts or arbitrary commands as part of scanning. The MCP interface exposes named read/search/index/diagnostic operations only; it must never gain shell execution or source-editing tools without a separate review.

- Bind MCP to one explicit local workspace (`--root`); no MCP input may override the root.
- Project source is read-only, index/cache/logs are stored in `$GUARDIAN_HOME` (default `~/.engineering-guardian/`).
- Default exclusions cover `.env*`, private-key/certificate files, dependency/build/cache directories and symlinks; exclusion is defense-in-depth, **not** a secret scanner.
- Indexes and returned context **may contain private code**. The model service receiving an MCP response can see those selected snippets. Do not enable MCP on confidential workspaces without reviewing your model provider's data controls.
- Diagnostic logs and support bundles intentionally omit source, prompt content, file names, absolute paths and tokens. Inspect ZIP contents before sharing in case of changes or unusual environments.
- MCP remains local STDIO; do not expose to the Internet or a shared machine.

## Reporting

Report suspected vulnerabilities privately to the repository owner through GitHub private vulnerability reporting if enabled. Otherwise contact the maintainer privately; **do not open public issues with reproduction details or secrets**.

## Permissions

| Component | Reads | Writes | Executes scanned source? |
|---|---|---|---|
| Scanner | Selected source root | External SQLite cache | No |
| Context API | Selected source snippets | Diagnostics JSONL | No |
| MCP server | Selected source root | Index and diagnostics outside it | No |
| Support bundle | Sanitized logs | Support ZIP outside source | No |

Windows launcher `Start Engineering Guardian.cmd` invokes a checked-in PowerShell script with process-local ExecutionPolicy Bypass; it does not change the user's permanent policy. Inspect the scripts before execution, and follow organization policy on managed devices. Registration requests confirmation unless explicitly given `-Yes`.

GitHub Actions uses `contents: read` only. Never store credentials in this repository.
