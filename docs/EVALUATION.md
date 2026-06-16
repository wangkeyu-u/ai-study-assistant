# RAG Retrieval Evaluation

## Dataset

The first golden retrieval set is stored at:

```text
backend/eval/retrieval.golden.jsonl
```

It contains 48 questions derived from the local machine-learning textbook and targeted distractor chunks:

- 43 answerable questions covering terminology, paraphrases, algorithms, applications, and definitions.
- 5 out-of-scope questions that should produce no retrieval result.
- 3 answerable questions include explicit hard-negative labels to catch keyword-only distractors.
- Relevance is labeled with stable source-text snippets instead of local UUIDs, so re-ingesting the document does not invalidate the dataset.
- Private conversation documents are intentionally excluded.

This is an initial regression set, not a representative production benchmark. It currently focuses on one compact textbook and should grow as more learning materials are added.

The versioned source chunks are stored in `backend/eval/corpora/machine_learning_basics.jsonl`. Passing `--corpus` builds temporary SQLite and Chroma stores, so unrelated documents in the user's live knowledge base cannot change the score.

## Running

```bash
cd backend
venv/bin/python -m app.evaluation.retrieval \
  --dataset eval/retrieval.golden.jsonl \
  --corpus eval/corpora/machine_learning_basics.jsonl \
  --modes vector hybrid \
  --k 1 3 5 \
  --output /tmp/retrieval-golden-report.json \
  --summary-output eval/retrieval.baseline.summary.json \
  --gate-mode hybrid \
  --min-mrr 0.98 \
  --min-hit-at 1=0.97 \
  --min-hit-at 3=1.00 \
  --min-hard-negative-free-at 1=1.00 \
  --min-no-answer-accuracy 1.00 \
  --max-p95-latency-ms 100
```

The full report may contain local document names and should stay outside the repository. The summary contains aggregate metrics only.

## Multi-Hop Retrieval

Compound questions are evaluated separately because they care about evidence coverage, not just the first relevant chunk. The multi-hop set is stored at:

```text
backend/eval/retrieval_multihop.golden.jsonl
```

It currently contains 3 two-evidence questions over the same isolated corpus. `multi_hop_hybrid` runs the original query plus deterministic subqueries, then fuses the ranked lists with RRF.

```bash
cd backend
venv/bin/python -m app.evaluation.retrieval \
  --dataset eval/retrieval_multihop.golden.jsonl \
  --corpus eval/corpora/machine_learning_basics.jsonl \
  --modes hybrid multi_hop_hybrid \
  --k 1 3 5 \
  --output /tmp/retrieval-multihop-report.json \
  --summary-output /tmp/retrieval-multihop-summary.json \
  --gate-mode multi_hop_hybrid \
  --min-hit-at 1=1.00 \
  --min-recall-at 3=1.00 \
  --min-recall-at 5=1.00 \
  --max-p95-latency-ms 150
```

Current multi-hop gate result on June 16, 2026:

| Mode | MRR | Hit@1 | Recall@1 | Recall@3 | Recall@5 | P95 latency |
|---|---:|---:|---:|---:|---:|---:|
| Hybrid | 1.000 | 1.000 | 0.500 | 1.000 | 1.000 | 7.0ms |
| Multi-hop hybrid | 1.000 | 1.000 | 0.500 | 1.000 | 1.000 | 55.0ms |

The current corpus is intentionally small, so plain hybrid also passes the three multi-hop cases. The gate still protects the query decomposition path and should become more discriminating as the corpus gains more distractor documents.

## Baseline

Baseline date: June 16, 2026.

| Mode | MRR | Hit@1 | Hit@3 | Hit@5 | HardNeg@1 | No-answer accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Vector | 0.965 | 0.953 | 0.977 | 0.977 | 0.375 | 0.000 |
| Hybrid (Vector + FTS5 + RRF + confidence gate) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

Hybrid retrieval substantially improves ranking on answerable questions. The calibrated confidence gate rejects all five out-of-scope questions, and hard-negative labels verify that obvious keyword distractors do not occupy the top answer slot.

## Next Quality Gate

The current enforced quality gate is:

- Hybrid Hit@1 >= 0.97
- Hybrid Hit@3 >= 1.00
- Hybrid MRR >= 0.98
- Hybrid HardNeg@1 >= 1.00
- No-answer accuracy >= 1.00

Before enabling a Cross-Encoder reranker, benchmark a Chinese-capable model and require a measurable MRR or Hit@1 improvement without regressing no-answer accuracy or exceeding the latency budget. A lightweight multilingual mMARCO MiniLM model was rejected because it ranked the inspected Chinese failure case worse.

## Reranker A/B

Evaluated locally on June 15, 2026 against the isolated 45-question corpus:

| Mode | MRR | Hit@1 | No-answer | Average latency | P95 latency | Decision |
|---|---:|---:|---:|---:|---:|---|
| Hybrid | 0.988 | 0.975 | 1.000 | 10.5ms | 16.8ms | Keep |
| Hybrid + `BAAI/bge-reranker-v2-m3` | 0.983 | 0.975 | 1.000 | 395.3ms | 600.5ms | Reject |

`BAAI/bge-reranker-base` was also rejected during targeted screening because it ranked the known Chinese failure case incorrectly. Reranking remains available behind `ASA_RERANKER_ENABLED=false`, but is not a production default.

## Answer And Citation Quality

Saved model outputs can be evaluated without modifying the live knowledge base:

```bash
cd backend
venv/bin/python -m app.evaluation.answer_quality \
  --dataset eval/answer_quality.example.jsonl \
  --min-refusal-accuracy 1.0 \
  --min-citation-validity 1.0 \
  --min-citation-completeness 1.0 \
  --min-evidence-coverage 1.0
```

The evaluator checks refusal decisions, citation-number validity, factual-sentence citation completeness, and whether cited contexts contain labeled evidence. It is deterministic and does not claim to replace a semantic faithfulness judge. Production answers without explicit `[N]` markers now report no citations instead of silently attaching every retrieved chunk.
