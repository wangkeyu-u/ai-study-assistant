# Keep confidence gating and document coverage explicit

This document retrospectively records the rationale behind the current implementation.

## Context

A high-ranked vector result can be semantically plausible while unsupported. Comparison questions can also return several chunks from one selected document and omit another.

## Options Considered

### Option A — always generate from top-ranked chunks

Pros: maximum answer coverage and low refusal rate. Cons: unsupported questions receive plausible context and multi-document answers can silently omit a source.

### Option B — confidence gate and coverage reservation

Pros: weak vector-only evidence can be refused before generation; comparison requests reserve a candidate from each selected document. Cons: false refusals and less globally optimal top-k ranking are possible.

## Decision

Retain a vector-only confidence gate and explicit selected-document coverage in the retriever.

## Why

On the controlled challenge, adding the gate increased no-answer accuracy from 0.000 to 0.278 without changing answerable Hit@1 (0.785). It did not solve all hard negatives; that failure remains visible in the report.

## Validation

Compare `rrf_coverage` and `rrf_coverage_gate` in the committed ablation output. Query-level rows identify every refusal and selected chunk.

## Trade-offs

The current threshold is a retrieval heuristic, not a calibrated probability. A strict gate can reject supported paraphrases, while coverage can elevate a weaker chunk from a requested document.

## What Would Change My Mind

An independently labeled, multi-document set showing a calibrated alternative reduces unsupported answers and false refusals at the same or lower latency.
