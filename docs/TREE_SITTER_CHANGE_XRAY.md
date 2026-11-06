# Tree-sitter and Change X-Ray

## Why Tree-sitter is optional

Tree-sitter parses syntax structure across languages without executing the application. The core scanner remains dependency-light and continues to use Python AST / regex fallbacks when a grammar is absent.

~~~bash
python -m pip install -e ".[treesitter]"
python -m ucg.cli --root /path/to/project parsers status
python -m ucg.cli --root /path/to/project parsers install --languages python,typescript,javascript,dart,kotlin,java,sql,go,rust
python -m ucg.cli --root /path/to/project scan
~~~

The grammar install command is an explicit network operation. The scan process checks only the local registry/cache; it never downloads grammars or a remote manifest. Parser binaries remain in the user's local cache, not in the project folder.

## Resolution levels

| Resolution | Meaning | Trust |
|---|---|---|
| \`tree_sitter_import_binding\` | An explicit import alias resolves to one declaration in a local file | Stronger syntax evidence; no type checking |
| \`tree_sitter_same_class\` | \`self\`/\`this\`/\`cls\` plus one matching method in the enclosing type | Stronger syntax evidence; dynamic overrides may differ |
| \`tree_sitter_same_file_unique\` | Exactly one same-file callable declaration matches an unqualified call name | Syntax-only; local variable shadowing is not fully analyzed |
| \`ast_candidate\` | A unique global name or fallback parser candidate | Heuristic; verify in source |
| \`unresolved\` | Ambiguous, dynamic, external or unsupported reference | No graph edge; retained as an unknown |

Tree-sitter does not know the runtime type of an object. Calls such as \`client.send()\` remain unresolved unless the receiver can be safely mapped through a supported explicit import. Dynamic dispatch, reflection, DI containers, decorators/macros and generated code can create relationships not visible to this POC.

## What Change X-Ray does

1. Compare two immutable source snapshots by file fingerprint.
2. Match declarations by relative path, qualified name and kind.
3. Compare signature and body fingerprints to distinguish added, deleted, signature-changed and body-changed symbols.
4. Walk reverse call edges in the corresponding snapshot to identify direct and transitive dependents.
5. Find test-like files whose imports resolve to changed modules and callers that are themselves test files.
6. Surface unresolved references whose target name matches a changed declaration.

Run it after two scans:

~~~bash
python -m ucg.cli --root /path/to/project scan
# Make source changes.
python -m ucg.cli --root /path/to/project scan
python -m ucg.cli --root /path/to/project impact
~~~

Use \`--base SNAPSHOT\` and \`--head SNAPSHOT\` for explicit comparisons. The output includes parser coverage and a static confidence label.

## What it does not do

- It does not execute the test suite, build system or application.
- It does not claim every affected test was found.
- It does not infer all cross-language API, HTTP, database, event or platform-channel dependencies.
- It does not prove behavioral equivalence or safe-to-merge status.
- It does not edit the scanned source tree.

Treat it as a review checklist generator. A developer must verify the cited paths, run the suggested tests and inspect unresolved references.
