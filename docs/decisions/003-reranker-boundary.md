# Keep the reranker optional

This document retrospectively records the rationale behind the current implementation.

## Context

Cross-encoder reranking may improve candidate order but adds local CPU work and model dependencies. It must not be enabled because a single score looks better.

## Options Considered

### Option A — enable the reranker by default

Pros: higher ranking scores on favorable queries. Cons: slower cold and warm requests, extra model distribution, and no guarantee of better refusal behavior.

### Option B — keep it behind a configuration flag

Pros: the baseline stays lightweight and the trade-off remains measurable. Cons: users who need reranking must install and cache the model.

## Decision

Keep the reranker optional and reject it as a default based on the current local evidence.

## Why

On 111 controlled queries the reranker raised MRR from 0.853 to 0.878, but P95 latency rose from 5.8 ms to 417.1 ms and no-answer accuracy remained only 0.333. This is insufficient for the current default budget.

## Validation

See the `rrf_coverage_gate` and `rrf_coverage_gate_reranker` rows in [`retrieval-ablation-results.json`](../experiments/retrieval-ablation-results.json).

## Trade-offs

The measured model and CPU are local choices. A different multilingual cross-encoder or hardware could change the result; no production latency claim is made.

## What Would Change My Mind

A reproducible, independently labeled evaluation showing a meaningful hard-negative/no-answer improvement within an agreed latency budget.
