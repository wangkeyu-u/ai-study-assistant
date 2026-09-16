# Use hybrid retrieval with RRF

This document retrospectively records the rationale behind the current implementation.

## Context

The corpus contains both exact identifiers and natural-language paraphrases. Dense and FTS5 retrieval expose different failure modes, and their scores do not share a calibrated scale.

## Options Considered

### Option A — dense retrieval only

Pros: one index and a simple query path. Cons: weak on exact terms, unsupported-query rejection, and lexical distractors in the controlled regression set.

### Option B — vector + FTS5 with score normalization

Pros: combines both signals. Cons: cosine and BM25 distributions vary by corpus and query; normalization would add calibration assumptions that are not measured here.

### Option C — vector + FTS5 with Reciprocal Rank Fusion

Pros: uses rank agreement without pretending scores are comparable; each path remains inspectable. Cons: RRF discards score gaps and cannot create evidence that either path missed.

## Decision

Use vector and FTS5 candidate paths and fuse their ranks with RRF (`rrf_k=60`).

## Why

The expanded controlled ablation improved MRR from 0.728 (vector only) and 0.771 (FTS5 only) to 0.834 for RRF. This is a fixture result, not a general benchmark claim.

## Validation

Run `python -m app.evaluation.ablation --output ../docs/experiments/retrieval-ablation-results.json` with the pinned local embedding configuration. The output records corpus/code hashes and per-query results.

## Trade-offs

RRF adds candidate retrieval and latency. It does not calibrate confidence, prove semantic faithfulness, or guarantee hard-negative accuracy.

## What Would Change My Mind

A larger independently labeled corpus showing a simpler ranker matches RRF while improving hard-negative and no-answer accuracy within the same latency budget.
