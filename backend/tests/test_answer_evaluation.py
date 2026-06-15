"""Tests for deterministic answer and citation quality evaluation."""

from app.evaluation.answer_quality import (
    AnswerEvaluationExample,
    aggregate_answer_metrics,
    answer_gate_failures,
    score_answer,
    split_factual_sentences,
)


def test_score_answer_checks_citations_evidence_and_refusal():
    answerable = AnswerEvaluationExample(
        query="q",
        answer="机器学习可以从数据中自动学习[1]。它不需要显式编程[1]。",
        contexts=["机器学习可以从数据中自动学习和改进，而不需要显式编程。"],
        required_evidence=["从数据中自动学习", "不需要显式编程"],
    )
    refusal = AnswerEvaluationExample(
        query="missing",
        answer="根据现有资料，没有找到足够的信息来回答这个问题。",
        expect_refusal=True,
    )

    answerable_score = score_answer(answerable)
    refusal_score = score_answer(refusal)

    assert answerable_score["citation_validity"] == 1.0
    assert answerable_score["citation_completeness"] == 1.0
    assert answerable_score["evidence_coverage"] == 1.0
    assert refusal_score["refusal_correct"] == 1.0


def test_score_answer_exposes_invalid_and_missing_citations():
    example = AnswerEvaluationExample(
        query="q",
        answer="第一条事实没有引用。第二条事实引用越界[9]。",
        contexts=["context"],
        required_evidence=["expected evidence"],
    )

    score = score_answer(example)

    assert score["citation_validity"] == 0.0
    assert score["citation_completeness"] == 0.0
    assert score["invalid_citation_count"] == 1
    assert score["evidence_coverage"] == 0.0


def test_split_factual_sentences_ignores_headings_and_refusal():
    sentences = split_factual_sentences("# 回答\n根据现有资料，没有找到足够的信息。\n有效事实[1]。")

    assert sentences == ["有效事实[1]。"]


def test_answer_quality_gate_reports_regressions():
    rows = [
        {
            "refusal_correct": 1.0,
            "citation_validity": 0.5,
            "citation_completeness": 0.75,
            "evidence_coverage": 0.5,
            "citation_evidence_precision": 1.0,
            "invalid_citation_count": 1,
        }
    ]
    metrics = aggregate_answer_metrics(rows)

    assert answer_gate_failures(
        metrics,
        min_citation_validity=0.9,
        min_citation_completeness=0.8,
        min_evidence_coverage=0.8,
    ) == [
        "Citation validity 0.500 < 0.900",
        "Citation completeness 0.750 < 0.800",
        "Evidence coverage 0.500 < 0.800",
    ]
