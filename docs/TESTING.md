# Test and benchmark guide

## Correctness & security (required before release)

```bash
python3 -m compileall -q ucg scripts benchmarks tests
python3 -m unittest discover -s tests -v
```

Core regressions cover: non-Git scan, mixed-language symbols, cache reuse, edited-file incremental parsing, snapshot isolation, rejecting stale snippets, source modification during scan, symlink/secret exclusion, MCP JSON-RPC and tool argument allowlists, privacy-filtered support logs.

## Smoke tests against a local folder

```bash
python3 -m ucg.cli --root ./tests scan
python3 -m ucg.cli --root ./tests status
python3 -m ucg.cli --root ./tests overview
python3 -m ucg.cli --root ./tests search test
python3 -m ucg.cli --root ./tests doctor
python3 -m ucg.cli --root ./tests support-bundle
```

Only scan a folder you have permission to access. Do not run indexing on live secrets.

## Synthetic benchmark

```bash
python3 -m benchmarks.generate_fixture --output ./.benchmark/valid-100 --files 100 --lines 1000 --force
python3 -m benchmarks.run_benchmark --source ./.benchmark/valid-100 --output ./reports/local-benchmark.json --db ./.benchmark/local-benchmark.sqlite --runs 5
```

Include host CPU/RAM/storage, Python version, fixture hash, parser mode, warm/cold cache, medians and p95, precision/recall against ground truth. See `docs/BENCHMARK.md`.

**Do not conflate** local UCG query timings with ChatGPT inference. UCG source coverage is currently heuristic outside Python. Benchmark targets are not guarantees.

## v0.4 offline and privacy tests

Run `python -m unittest discover -s tests -v` from the repository root on Python 3.11+. Tests now include tree/outline/hotspots/repo-map, no-Git snapshot diffs, bounded MCP output, stale-index handling and an automated public-example privacy audit. CI runs on Windows and Ubuntu. Performance measurements of SQLite-only graph queries are *not* end-to-end latency benchmarks, because index freshness checks rehash source files.
