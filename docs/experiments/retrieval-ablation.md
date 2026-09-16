# Retrieval ablation

## Scope

This is a controlled regression experiment, not a general RAG benchmark. The frozen set has 111 queries, 93 answerable queries, 18 no-answer queries, 21 logical documents, 25 chunks, and 29 answerable queries with hard-negative labels. It retains the original 48 cases and adds paraphrase, abbreviation, Chinese/English cross-language, numeric, near-duplicate, multi-hop, lexical-heavy, semantic-heavy, and unsupported cases.

The added labels are AI-authored synthetic fixtures. They are useful for regression and failure analysis, but are not independent human annotation.

Language labels: 69 Chinese, 42 English (mixed-script Chinese questions count as Chinese). Multi-hop labels test retrieval of multiple evidence chunks; this experiment does not run query decomposition or generate a multi-hop answer.

## Variants

1. Vector only
2. FTS5 only
3. Vector + FTS5 with rank interleaving
4. Vector + FTS5 with RRF
5. RRF + query coverage boost
6. RRF + query coverage + confidence gate
7. The same path with a local cross-encoder reranker
8. Existing production reference path, including current penalties

Generation, translation, query rewriting, and indexing are outside this retrieval table. P50/P95 include warm query embedding and reranking where enabled.

## Protocol

```bash
cd backend
ASA_EMBEDDING_PROVIDER=local \
ASA_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5 \
ASA_EMBEDDING_DIMENSION=512 \
ANONYMIZED_TELEMETRY=False \
python -m app.evaluation.ablation \
  --output ../docs/experiments/retrieval-ablation-results.json
```

The evaluator validates chunk labels, records SHA-256 hashes, package versions, environment, model revision when available, and runs three seeded repetitions. The full per-query result is [`retrieval-ablation-results.json`](retrieval-ablation-results.json).

Install Python 3.12 dependencies using `requirements.txt`, `requirements-dev.txt` and `requirements-local.txt` as shown in the README. Measured on macOS 26.6.2 arm64 with Python 3.12.13, CPU and one torch thread. Embedding revision: `7999e1d3359715c523056ef9478215996d62a620`; reranker `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` revision: `1427fd652930e4ba29e8149678df786c240d8825`. The machine-readable report identifies exact library versions. Future model downloads should resolve these revisions for a comparable rerun.

## Results

| Variant | MRR | Hit@1 | Hit@3 | Recall@5 | No-answer | Hard-negative accuracy | P50 ms | P95 ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Vector only | 0.7280 | 0.6129 | 0.8495 | 0.8763 | 0.0000 | 0.5172 | 4.33 | 4.97 |
| FTS5 + short-term exact fallback | 0.7706 | 0.6882 | 0.8495 | 0.8656 | 0.3333 | 0.3448 | 0.59 | 0.79 |
| Vector + FTS5 interleave | 0.7599 | 0.6129 | 0.9140 | 0.9301 | 0.0000 | 0.5172 | 5.21 | 5.84 |
| RRF | 0.8341 | 0.7634 | 0.9032 | 0.9194 | 0.0000 | 0.5862 | 5.15 | 5.65 |
| + coverage boost | 0.8530 | 0.7849 | 0.9247 | 0.9194 | 0.0000 | 0.5862 | 5.16 | 5.84 |
| + confidence gate | 0.8530 | 0.7849 | 0.9247 | 0.9194 | 0.2778 | 0.5862 | 5.21 | 5.77 |
| + reranker | 0.8781 | 0.8172 | 0.9462 | 0.9462 | 0.3333 | 0.6552 | 334.32 | 417.14 |
| Current path including penalties | 0.8853 | 0.8495 | 0.9247 | 0.9194 | 0.2778 | 0.6897 | 5.63 | 6.39 |

Quality values are identical across the three repeats; pooled latency covers 333 calls per variant. Repeats are not 333 independent questions. In each mode's aggregate, `queries=333`, `answerable_queries=279`, `hard_negative_queries=87` count repeated observations; top-level dataset denominators are 111/93/29.

## Reading the result

RRF improves ranking over either single path on this fixture. Coverage improves ranking but does not fix unsupported queries. The gate rejects 5/18 unsupported questions, with 0/93 answerable refusals; FTS-only falsely refuses 9/93. Hard-negative errors remain. The reranker improves MRR over the no-penalty gated path at a large latency cost, and is worse in MRR than the full current path. Enabling it by default is not justified by this experiment.

The gate examines lexical support and a vector score heuristic. A keyword hit can bypass rejection even when it does not answer the question. For example, `What is the measured peak throughput of Atlas?` retrieves `capacity`, whose text gives only a target and explicitly says no load test was done. This is an unresolved retrieval answerability failure; no generated answer was evaluated. The legacy French Revolution query also retrieves a newly added Chinese chunk. Both failures are retained in the raw output.

Query coverage boosts lexical overlap, which can reward near-duplicate or negated text. The current-path penalties partly counter this but are heuristics tied to surface wording. The expanded set is development evidence; do not tune on it and then relabel it an independent test set.

## Metric definitions

- MRR and Hit@K use answerable queries only.
- No-answer accuracy uses only the 18 queries labeled `expect_no_results`.
- Hard-negative accuracy uses only the 29 answerable queries with an explicit forbidden chunk label and requires both a relevant Hit@1 and no forbidden Hit@1.
- Recall@K counts labeled relevant chunks retrieved by K.
- Latency is measured per query after index/model warmup; startup and indexing are excluded.
