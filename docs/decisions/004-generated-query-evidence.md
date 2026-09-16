# Generated retrieval queries cannot become answer evidence

Recorded retrospectively from the current implementation, 2026-09-16. This record does not invent a prior comparison experiment.

## Context

Translation and HyDE can change a query to recover missing source chunks. A hypothetical passage may also contain plausible but fabricated facts. Selected-document comparisons have a separate evidence-coverage requirement.

## Options Considered

### Option A

Use generated HyDE text as answer context. Pros: fills gaps quickly. Cons: generated hypotheses become self-supporting citations.

### Option B

Use generated text only to retrieve original chunks. Pros: citations retain source identity. Cons: an unsuccessful retrieval still requires refusal, and generation adds latency.

## Decision

Keep HyDE outside evidence. Preserve the original-query context coverage check. Reserve available chunks for explicitly selected documents before filling top-k.

## Why

Retrieval recall and evidential support are different properties. RRF can improve rank agreement while omitting one requested document; reserving document coverage handles this independently.

## Validation

Inspect `backend/app/services/rag.py`, `retriever.py::ensure_document_coverage`, and the HyDE/coverage cases in `backend/tests/test_services/test_rag_pipeline.py` and `test_retriever.py`. The retrieval-only ablation does not run HyDE, translation or the answer-generation path; it therefore assigns no quantitative gain to them.

## Trade-offs

Lexical query-coverage boosting can reward distractors or negated passages. Forced document coverage may select a lower-ranked chunk and cannot guarantee coverage if the budget is too small or a source has no candidates. None of these controls prove semantic entailment.

## What Would Change My Mind

Independent multi-document and unsupported-query evaluations showing a measured alternative improves answer support and source coverage without adding unsupported evidence.
