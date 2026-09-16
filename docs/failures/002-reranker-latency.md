# Reranker ranking gain exceeded the local latency budget

## Symptom

The local reranker improved controlled MRR but retrieval became much slower.

## Reproduction

Run the ablation command in [`docs/experiments/retrieval-ablation.md`](../experiments/retrieval-ablation.md). Compare `rrf_coverage_gate` with `rrf_coverage_gate_reranker`.

## Root Cause

Cross-encoder inference scores each candidate pair on CPU. The model adds substantial per-query work; ranking improvement does not imply an acceptable service budget.

## Attempts

The reranker was measured after warmup and with one torch thread. It was not silently removed from the experiment when it underperformed.

## Final Fix

Keep reranking optional and record the result as an explicit trade-off. The default path remains hybrid retrieval with gate/coverage controls.

## Remaining Risk

Different hardware, batching, model size, or candidate counts may change the balance. The current result is not a deployment benchmark.
