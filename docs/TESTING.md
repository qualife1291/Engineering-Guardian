# Test and benchmark guide

## Dependency-free regression suite

~~~bash
python3 -m compileall -q ucg scripts benchmarks tests
python3 -m unittest discover -s tests -v
~~~

This covers fallback parsing, scanner safety, incremental reuse, stale snapshot checks, MCP allowlists, offline commands, privacy checks and cross-platform launchers. Tree-sitter tests skip when optional grammar binaries are absent.

## Tree-sitter integration suite

~~~bash
python3 -m pip install -e ".[treesitter]"
python3 -m ucg.cli --root . parsers install --languages python,typescript,javascript,dart,kotlin,java,sql,go,rust
python3 -m unittest tests.test_treesitter -v
python3 -m unittest discover -s tests -v
~~~

Grammar installation is an explicit network operation. Normal scans only use already-cached grammars and never download them. CI tests both the dependency-free fallback and installed parser path.

## Change X-Ray smoke test

~~~bash
python3 -m ucg.cli --root /path/to/project scan
# Make a source change, then:
python3 -m ucg.cli --root /path/to/project scan
python3 -m ucg.cli --root /path/to/project impact
~~~

Use \`--base\` and \`--head\` to compare explicit snapshot IDs. Impact output contains changed symbol hashes, statically resolved reverse dependents, import-linked test suggestions and unresolved references. It does not run tests.

## General smoke tests

~~~bash
python3 -m ucg.cli --root ./tests scan
python3 -m ucg.cli --root ./tests status
python3 -m ucg.cli --root ./tests overview
python3 -m ucg.cli --root ./tests parsers status
python3 -m ucg.cli --root ./tests support-bundle
~~~

Only scan a folder you have permission to access. Do not run indexing on live secrets. Performance figures must identify parser backend, cold/warm cache, host, corpus hash and end-to-end time.
