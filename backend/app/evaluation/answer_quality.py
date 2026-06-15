"""Offline answer and citation quality evaluation for saved RAG outputs."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from dataclasses import asdict, dataclass, field
from pathlib import Path

_CITATION_RE = re.compile(r"\[(\d+)\]")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?])|\n+")
_REFUSAL_MARKERS = ("没有找到足够的信息", "无法根据现有资料", "资料不足")


@dataclass
class AnswerEvaluationExample:
    query: str
    answer: str
    contexts: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    expect_refusal: bool = False


def load_answer_dataset(path: str | Path) -> list[AnswerEvaluationExample]:
    """Load saved model outputs and their ordered retrieval contexts."""
    examples: list[AnswerEvaluationExample] = []
    with Path(path).open(encoding="utf-8") as dataset_file:
        for line_number, raw_line in enumerate(dataset_file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                example = AnswerEvaluationExample(**json.loads(line))
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(f"Invalid answer row {line_number}: {error}") from error
            if not example.query.strip() or not example.answer.strip():
                raise ValueError(f"Answer row {line_number} requires query and answer")
            if not example.expect_refusal and not example.contexts:
                raise ValueError(f"Answer row {line_number} requires contexts")
            examples.append(example)
    if not examples:
        raise ValueError("Answer evaluation dataset is empty")
    return examples


def is_refusal(answer: str) -> bool:
    return any(marker in answer for marker in _REFUSAL_MARKERS)


def split_factual_sentences(answer: str) -> list[str]:
    """Split answer prose while excluding headings and explicit refusals."""
    sentences = []
    for part in _SENTENCE_BOUNDARY_RE.split(answer):
        sentence = part.strip().lstrip("-•*# ")
        content = _CITATION_RE.sub("", sentence).strip()
        if len(content) < 4 or is_refusal(content):
            continue
        sentences.append(sentence)
    return sentences


def score_answer(example: AnswerEvaluationExample) -> dict[str, float | int | None]:
    """Score deterministic refusal and citation-grounding properties."""
    refs = [int(value) for value in _CITATION_RE.findall(example.answer)]
    valid_refs = [ref for ref in refs if 1 <= ref <= len(example.contexts)]
    unique_valid_refs = sorted(set(valid_refs))
    refusal_correct = float(is_refusal(example.answer) == example.expect_refusal)

    citation_validity = len(valid_refs) / len(refs) if refs else float(example.expect_refusal)
    factual_sentences = split_factual_sentences(example.answer)
    cited_sentences = sum(
        any(1 <= int(ref) <= len(example.contexts) for ref in _CITATION_RE.findall(sentence))
        for sentence in factual_sentences
    )
    citation_completeness = (
        cited_sentences / len(factual_sentences)
        if factual_sentences
        else float(example.expect_refusal)
    )

    cited_contexts = [example.contexts[ref - 1] for ref in unique_valid_refs]
    evidence_coverage = (
        sum(
            any(evidence in context for context in cited_contexts)
            for evidence in example.required_evidence
        )
        / len(example.required_evidence)
        if example.required_evidence
        else None
    )
    citation_evidence_precision = (
        sum(
            any(evidence in context for evidence in example.required_evidence)
            for context in cited_contexts
        )
        / len(cited_contexts)
        if cited_contexts and example.required_evidence
        else None
    )
    return {
        "refusal_correct": refusal_correct,
        "citation_validity": citation_validity,
        "citation_completeness": citation_completeness,
        "evidence_coverage": evidence_coverage,
        "citation_evidence_precision": citation_evidence_precision,
        "citation_count": len(refs),
        "invalid_citation_count": len(refs) - len(valid_refs),
        "factual_sentence_count": len(factual_sentences),
    }


def aggregate_answer_metrics(rows: list[dict]) -> dict[str, float | int | None]:
    metrics: dict[str, float | int | None] = {"examples": len(rows)}
    for name in (
        "refusal_correct",
        "citation_validity",
        "citation_completeness",
        "evidence_coverage",
        "citation_evidence_precision",
    ):
        values = [row[name] for row in rows if row[name] is not None]
        metrics[name] = statistics.fmean(values) if values else None
    metrics["invalid_citation_count"] = sum(row["invalid_citation_count"] for row in rows)
    return metrics


def answer_gate_failures(
    metrics: dict,
    *,
    min_refusal_accuracy: float | None = None,
    min_citation_validity: float | None = None,
    min_citation_completeness: float | None = None,
    min_evidence_coverage: float | None = None,
) -> list[str]:
    thresholds = {
        "refusal_correct": ("Refusal accuracy", min_refusal_accuracy),
        "citation_validity": ("Citation validity", min_citation_validity),
        "citation_completeness": ("Citation completeness", min_citation_completeness),
        "evidence_coverage": ("Evidence coverage", min_evidence_coverage),
    }
    failures = []
    for metric_name, (label, threshold) in thresholds.items():
        if threshold is None:
            continue
        actual = metrics.get(metric_name)
        if actual is None:
            failures.append(f"{label} was not evaluated")
        elif actual < threshold:
            failures.append(f"{label} {actual:.3f} < {threshold:.3f}")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="Saved answer JSONL dataset")
    parser.add_argument("--output", help="Optional detailed JSON report")
    parser.add_argument("--min-refusal-accuracy", type=float)
    parser.add_argument("--min-citation-validity", type=float)
    parser.add_argument("--min-citation-completeness", type=float)
    parser.add_argument("--min-evidence-coverage", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    threshold_names = (
        "min_refusal_accuracy",
        "min_citation_validity",
        "min_citation_completeness",
        "min_evidence_coverage",
    )
    for name in threshold_names:
        value = getattr(args, name)
        if value is not None and not 0.0 <= value <= 1.0:
            raise SystemExit(f"--{name.replace('_', '-')} must be between 0 and 1")

    examples = load_answer_dataset(args.dataset)
    rows = []
    for example in examples:
        rows.append({"query": example.query, **score_answer(example)})
    metrics = aggregate_answer_metrics(rows)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    if args.output:
        Path(args.output).write_text(
            json.dumps(
                {
                    "dataset": str(Path(args.dataset).resolve()),
                    "examples": [asdict(example) for example in examples],
                    "metrics": metrics,
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    failures = answer_gate_failures(
        metrics,
        min_refusal_accuracy=args.min_refusal_accuracy,
        min_citation_validity=args.min_citation_validity,
        min_citation_completeness=args.min_citation_completeness,
        min_evidence_coverage=args.min_evidence_coverage,
    )
    if failures:
        print("Answer quality gate failed:")
        for failure in failures:
            print(f"  - {failure}")
        raise SystemExit(1)
    if any(getattr(args, name) is not None for name in threshold_names):
        print("Answer quality gate passed")


if __name__ == "__main__":
    main()
