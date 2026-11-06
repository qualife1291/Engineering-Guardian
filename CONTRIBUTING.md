# Contributing

## Local development

Requirements: Python 3.11+; no runtime Python dependencies. From repo root:

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q ucg scripts benchmarks tests
python3 -m ucg.cli --root tests scan
python3 -m ucg.cli --root tests doctor
```

On native Windows use `py -3 -m unittest discover -s tests -v`, then `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\\scripts\\start_windows.ps1 -CheckOnly`. The GitHub Windows CI job verifies PowerShell AST syntax and Claude registration with a mocked command. Windows native and WSL2 have separate virtual environments.

Keep fixture tests synthetic and secrets-free. Performance data should include machine, Python version, corpus size, cache state, repeats and known accuracy limitations.

## Design rules

1. Keep source scanning read-only. Indexes, logs and support ZIPs must live outside workspace by default.
2. Preserve immutable snapshot/source evidence. Refuse stale reads, never mix sources across revisions.
3. Label AST/regex heuristics `ast_candidate` rather than pretending they are compiler-verified.
4. Avoid external runtime dependencies unless justified, pinned, documented and covered by CI.
5. Add regression tests for correctness, performance-sensitive behavior and privacy before changing public APIs.
6. Document user-facing changes and append an entry to `CHANGELOG.md` under `[Unreleased]` until release.
7. For agents, start with `AGENTS.md`, then `docs/PROJECT_MAP.md`, and open only relevant implementation files.

## Release checklist

See `docs/RELEASING.md`; update both package version fields and changelog in the same change. Do not commit local SQLite indexes, credentials or diagnostic bundles.
