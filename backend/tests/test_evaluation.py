"""Tests for offline retrieval evaluation metrics and datasets."""

import json

import pytest

from app.evaluation.retrieval import (
    EvaluationExample,
    aggregate_metrics,
    load_corpus,
    load_dataset,
    parse_hit_thresholds,
    quality_gate_failures,
    score_ranking,
)
from app.services.retriever import RetrievedChunk


def _chunk(chunk_id: str, doc_id: str, doc_name: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="text",
        score=0.5,
        doc_id=doc_id,
        doc_name=doc_name,
        page_num=1,
        chunk_index=0,
        heading=None,
    )


def test_score_ranking_calculates_hit_recall_and_reciprocal_rank():
    example = EvaluationExample(query="q", relevant_doc_ids=["doc-2"])
    chunks = [_chunk("c1", "doc-1", "a.pdf"), _chunk("c2", "doc-2", "b.pdf")]

    metrics = score_ranking(example, chunks, [1, 2])

    assert metrics["reciprocal_rank"] == 0.5
    assert metrics["hit_at_1"] == 0.0
    assert metrics["hit_at_2"] == 1.0
    assert metrics["recall_at_2"] == 1.0


def test_score_ranking_supports_portable_text_snippet_labels():
    example = EvaluationExample(query="q", relevant_texts=["支持向量机"])
    chunks = [_chunk("c1", "doc-1", "a.pdf")]
    chunks[0].text = "典型算法包括决策树和支持向量机。"

    metrics = score_ranking(example, chunks, [1])

    assert metrics["hit_at_1"] == 1.0
    assert metrics["reciprocal_rank"] == 1.0


def test_score_ranking_handles_expected_no_results():
    example = EvaluationExample(query="q", expect_no_results=True)

    correct = score_ranking(example, [], [1])
    incorrect = score_ranking(example, [_chunk("c1", "doc-1", "a.pdf")], [1])

    assert correct["no_answer_correct"] == 1.0
    assert incorrect["no_answer_correct"] == 0.0


def test_aggregate_metrics_reports_macro_averages():
    rows = [
        {
            "reciprocal_rank": 1.0,
            "hit_at_1": 1.0,
            "recall_at_1": 1.0,
            "latency_ms": 10.0,
            "expect_no_results": False,
        },
        {
            "reciprocal_rank": 0.0,
            "hit_at_1": 0.0,
            "recall_at_1": 0.0,
            "latency_ms": 30.0,
            "expect_no_results": False,
        },
    ]

    metrics = aggregate_metrics(rows, [1])

    assert metrics["mrr"] == 0.5
    assert metrics["hit_at_1"] == 0.5
    assert metrics["avg_latency_ms"] == 20.0
    assert metrics["p95_latency_ms"] == 30.0


def test_load_dataset_validates_relevance_targets(tmp_path):
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(json.dumps({"query": "missing labels"}), encoding="utf-8")

    with pytest.raises(ValueError, match="no relevant target"):
        load_dataset(dataset)


def test_load_corpus_validates_duplicate_chunk_ids(tmp_path):
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "chunk_id": "same",
                        "doc_id": "doc",
                        "doc_name": "doc.txt",
                        "chunk_index": 0,
                        "text": "first",
                    }
                ),
                json.dumps(
                    {
                        "chunk_id": "same",
                        "doc_id": "doc",
                        "doc_name": "doc.txt",
                        "chunk_index": 1,
                        "text": "second",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="repeats chunk_id"):
        load_corpus(corpus)


def test_parse_hit_thresholds_validates_repeated_values():
    assert parse_hit_thresholds(["1=0.9", "3=0.95"]) == {1: 0.9, 3: 0.95}

    with pytest.raises(ValueError, match="expected K=VALUE"):
        parse_hit_thresholds(["invalid"])


def test_quality_gate_failures_reports_metric_regressions():
    report = {
        "mode": "hybrid",
        "metrics": {
            "mrr": 0.89,
            "hit_at_3": 0.94,
            "no_answer_accuracy": 0.75,
            "p95_latency_ms": 120.0,
        },
    }

    failures = quality_gate_failures(
        report,
        min_mrr=0.9,
        min_hit_at={3: 0.95},
        min_no_answer_accuracy=0.8,
        max_p95_latency_ms=100.0,
    )

    assert failures == [
        "MRR 0.890 < 0.900",
        "Hit@3 0.940 < 0.950",
        "No-answer accuracy 0.750 < 0.800",
        "P95 latency 120.0ms > 100.0ms",
    ]
