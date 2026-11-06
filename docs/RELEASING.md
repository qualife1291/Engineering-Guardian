# Releasing Engineering Guardian

1. Verify `AGENTS.md`, README and CLI/MCP docs match actual code.
2. Run `python3 -m unittest discover -s tests -v`, compileall, CLI/MCP smoke, and diagnostics privacy test.
3. Record benchmark environment and findings; do not claim model-level wins without identical model inference.
4. Update `CHANGELOG.md`: move entries from `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD`.
5. Keep `ucg/__init__.py` `__version__` and `pyproject.toml` `project.version` identical.
6. Check `git status`; never publish `.env`, source indexes, SQLite, logs, support ZIPs or private application code.
7. Commit, push, wait for GitHub Actions checks and review logs. Tag only when CI passes and intended commit is verified.
8. Release notes must distinguish implemented features from future roadmap.

SemVer guideline: patch for compatible fixes, minor for new compatible features, major for breaking tool/API/schema changes. POC releases are `0.x` and can still evolve rapidly.
