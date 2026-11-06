# ChatGPT vs Engineering Guardian — Evaluation Protocol (Not a Speed Claim)

> Historical planning document: initial prototype query timings do not measure model reasoning, model latency, or current v0.4.0 end-to-end CLI/MCP performance. There is no valid overall winner from these figures.

## What can be concluded now

The 100-file / 100,000-line synthetic source corpus is approximately 3.86 MB and approximately 964k tokens by a rough `characters / 4` estimate.

The early Python prototype cold-indexed its original synthetic corpus in about 1.08 seconds in the benchmark container. The initial fixture was later replaced after validity defects were found; see the validated report. After indexing, a symbol search takes about 0.29 ms median, a bounded graph query about 0.003 ms median, and a query-specific context pack about 2.63 ms median.

These are local preparation/query timings, not LLM answer timings.

## Important distinction

Raw local file reading is not the expensive part: it took about 8 ms in the benchmark container. The expensive part in a full-context ChatGPT workflow is model-side ingestion and reasoning over a very large input, plus any upload/retrieval overhead. Those values were not measured here.

Engineering Guardian is also not a replacement for ChatGPT. The intended production workflow is:

1. Guardian indexes and navigates the code locally.
2. Guardian creates a compact, evidence-backed context pack.
3. ChatGPT or another model reasons over that context.
4. The model requests additional source evidence when needed.

## Fair test design

Use the same model, task, source snapshot and expected answer in both arms.

- Arm A: ChatGPT receives the complete source or uses its best available file-search workflow.
- Arm B: ChatGPT receives a Guardian-generated context pack and can request additional evidence.

Use at least five questions covering architecture, function call path, cross-module impact, data writes and tests. Score correctness against manually verified ground truth.

Report median and p95 for:

- time to first useful answer;
- total answer latency;
- input/output tokens;
- answer correctness;
- impact precision and recall;
- evidence coverage;
- developer time to understand the change.

Do not claim Guardian is faster end-to-end until this experiment has been run.
