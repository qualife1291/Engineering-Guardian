# Public repository privacy and sanitization policy

Engineering Guardian is intended to be installed by unrelated developers in different organizations. Public files must be useful without revealing the creator's machine, customer, team, proprietary apps, identifiers or sample data.

## Public examples

Use platform-neutral examples:

- POSIX: \`/path/to/project\`, \`/path/to/guardian-data\`
- Windows: \`C:\Projects\sample-app\`, \`C:\Projects\Engineering-Guardian\`
- Workspace tree: \`Engineering-Guardian/\` and \`sample-app/\`
- Symbols: \`processOrder\`, \`parseConfig\`, \`renderFrame\`

Do not commit actual local paths, real customer/project names, private repository addresses, email or phone addresses, credentials, signing material, auth headers, access tokens, API responses or captured proprietary source code. Avoid encoding real identifiers into test fixtures.

Benchmark fixtures must be synthetic. Store benchmark **environment and parameters** needed to reproduce experiments, but replace any local absolute path with fixture-relative placeholders. Historical timing measurements should be labeled with their environment and never represented as general guarantees.

## Automated checks

The test suite scans public text files for common user-home/volume paths, temporary sandbox paths and hardcoded owner-specific repository URLs. Generic pattern detection cannot recognize every confidential client or company name. Human review is required for each public release.

## Runtime logs and support ZIPs

SQLite indexes and source snippets can contain proprietary information, and must remain local. The exporter excludes source bodies and redacts workspace identifiers in shared support bundles. Diagnostic size counts and system metadata are still potentially identifying; always inspect before sharing.

## Git history is separate from current files

**Important:** GitHub retains old commits, PR diffs, forks and caches. Removing an identifier in the latest commit does not erase copies in earlier commits. If sensitive data appeared previously, evaluate changing repository visibility, deleting/refactoring old history with explicit owner approval, and rotating any actually exposed secrets. Never force-push or rewrite published history without authorization and a communication plan.

For security reports follow [SECURITY.md](../SECURITY.md).


## Tree-sitter grammar downloads

The optional parser package is installed by the developer. Grammar binaries are downloaded into the local parser cache only after an explicit \`guardian parsers install\` command. Normal scans check the local cache and do not access the network. Guardian does not upload source code to obtain a grammar. Do not share the SQLite index; it contains project structure and symbol metadata.
