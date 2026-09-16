# Small benchmark produced a misleading perfect score

## Symptom

The original README showed MRR, Hit@1, Hit@3, no-answer accuracy, and HardNeg@1 as 1.000.

## Reproduction

Inspect `backend/eval/retrieval.baseline.summary.json` and `docs/EVALUATION.md`. The fixture has 48 queries over one compact textbook and seven chunks; five queries are no-answer cases.

## Root Cause

The benchmark was a controlled regression set rather than a representative corpus. Its small size made a perfect hybrid score easy to overread. The documentation also reported vector Hit@1 as 0.953 while the committed JSON computes 0.9302. Hard-negative aggregation included no-answer rows in its denominator.

## Attempts

The original score was retained as historical evidence. A new challenge set and denominator-aware reporting were added instead of deleting the old result.

## Final Fix

README now names every denominator and calls the benchmark synthetic/controlled. The ablation reports separate no-answer and explicitly labeled hard-negative queries and stores raw per-query rows.

## Remaining Risk

The expanded labels are AI-authored and still not independent human annotation. Generalization, generation faithfulness, and user-document distribution remain unmeasured.
