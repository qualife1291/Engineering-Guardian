# Benchmark Protocol

The supplied fixture generator creates a nested source tree with exactly N source files and L lines per source file. The default target is 100 files × 1,000 lines = 100,000 lines.

Run:

```bash
python3 -m benchmarks.generate_fixture --output ./.benchmark/complex-100 --files 100 --lines 1000 --force
python3 -m benchmarks.run_benchmark --source ./.benchmark/complex-100 --output benchmark-results.json --runs 5
```

The harness measures local scanner/indexer cold time, warm time, peak Python allocation and the size of the full-source payload. The full-context baseline is only a payload-size estimate (`characters / 4`), not a measured ChatGPT model latency or exact token count.

A fair ChatGPT vs Engineering Guardian comparison must use the same tasks, the same source snapshot, the same expected answers, and the same correctness rubric. Record wall-clock latency, time-to-first-useful-answer, total completion time, input tokens reported by the model, output tokens, and correctness. Run each task at least five times and report median and p95. Do not compare a local index-only operation against full LLM inference as if they were equivalent tasks.

The prototype's warm run still reparses the corpus. Incremental cache is a future implementation task; the benchmark intentionally reports this limitation.
