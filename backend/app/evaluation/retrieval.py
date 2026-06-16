"""Offline retrieval evaluation for vector and hybrid search modes."""

from __future__ import annotations

import argparse
import json
import math
import statistics
import tempfile
import time
from collections.abc import Iterable
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import get_settings
from app.db.database import init_db
from app.services.embedder import create_embedder
from app.services.query_planner import retrieve_with_query_plan
from app.services.reranker import CrossEncoderReranker
from app.services.retriever import RetrievedChunk, Retriever
from app.services.vectorstore import VectorStore


@dataclass
class EvaluationExample:
    query: str
    relevant_chunk_ids: list[str] = field(default_factory=list)
    relevant_doc_ids: list[str] = field(default_factory=list)
    relevant_doc_names: list[str] = field(default_factory=list)
    relevant_texts: list[str] = field(default_factory=list)
    forbidden_chunk_ids: list[str] = field(default_factory=list)
    forbidden_doc_ids: list[str] = field(default_factory=list)
    forbidden_doc_names: list[str] = field(default_factory=list)
    forbidden_texts: list[str] = field(default_factory=list)
    collection_id: str | None = None
    expect_no_results: bool = False

    def relevant_keys(self) -> set[str]:
        return {
            *(f"chunk:{value}" for value in self.relevant_chunk_ids),
            *(f"doc:{value}" for value in self.relevant_doc_ids),
            *(f"name:{value}" for value in self.relevant_doc_names),
            *(f"text:{value}" for value in self.relevant_texts),
        }

    def forbidden_keys(self) -> set[str]:
        return {
            *(f"chunk:{value}" for value in self.forbidden_chunk_ids),
            *(f"doc:{value}" for value in self.forbidden_doc_ids),
            *(f"name:{value}" for value in self.forbidden_doc_names),
            *(f"text:{value}" for value in self.forbidden_texts),
        }


@dataclass
class EvaluationCorpusChunk:
    chunk_id: str
    doc_id: str
    doc_name: str
    chunk_index: int
    text: str
    page_num: int | None = None
    heading: str | None = None
    collection_id: str | None = None


def load_dataset(path: str | Path) -> list[EvaluationExample]:
    """Load and validate a JSONL retrieval evaluation dataset."""
    examples: list[EvaluationExample] = []
    with Path(path).open(encoding="utf-8") as dataset_file:
        for line_number, raw_line in enumerate(dataset_file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                example = EvaluationExample(**payload)
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(f"Invalid dataset row {line_number}: {error}") from error
            if not example.query.strip():
                raise ValueError(f"Dataset row {line_number} has an empty query")
            if not example.relevant_keys() and not example.expect_no_results:
                raise ValueError(f"Dataset row {line_number} has no relevant target")
            examples.append(example)

    if not examples:
        raise ValueError("Evaluation dataset is empty")
    return examples


def load_corpus(path: str | Path) -> list[EvaluationCorpusChunk]:
    """Load a versioned JSONL corpus used to build an isolated evaluation index."""
    chunks: list[EvaluationCorpusChunk] = []
    seen_chunk_ids: set[str] = set()
    with Path(path).open(encoding="utf-8") as corpus_file:
        for line_number, raw_line in enumerate(corpus_file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                chunk = EvaluationCorpusChunk(**json.loads(line))
            except (json.JSONDecodeError, TypeError) as error:
                raise ValueError(f"Invalid corpus row {line_number}: {error}") from error
            if not chunk.text.strip():
                raise ValueError(f"Corpus row {line_number} has empty text")
            if chunk.chunk_id in seen_chunk_ids:
                raise ValueError(f"Corpus row {line_number} repeats chunk_id '{chunk.chunk_id}'")
            seen_chunk_ids.add(chunk.chunk_id)
            chunks.append(chunk)
    if not chunks:
        raise ValueError("Evaluation corpus is empty")
    return chunks


def seed_evaluation_corpus(
    chunks: list[EvaluationCorpusChunk],
    embedder,
    vector_store: VectorStore,
) -> None:
    """Populate the active temporary SQLite and Chroma stores from a corpus."""
    documents: dict[str, EvaluationCorpusChunk] = {}
    for chunk in chunks:
        existing = documents.get(chunk.doc_id)
        if existing and existing.doc_name != chunk.doc_name:
            raise ValueError(f"Document '{chunk.doc_id}' has inconsistent names")
        documents[chunk.doc_id] = chunk

    from app.db.database import get_db

    with get_db() as conn:
        for doc_id, chunk in documents.items():
            chunk_count = sum(item.doc_id == doc_id for item in chunks)
            conn.execute(
                """INSERT INTO documents
                   (id, filename, file_type, file_path, file_size, chunk_count, status,
                    collection_id)
                   VALUES (?, ?, 'eval', ?, ?, ?, 'ready', ?)""",
                (
                    doc_id,
                    chunk.doc_name,
                    f"eval://{doc_id}",
                    sum(len(item.text.encode("utf-8")) for item in chunks if item.doc_id == doc_id),
                    chunk_count,
                    chunk.collection_id,
                ),
            )
        conn.executemany(
            """INSERT INTO chunks
               (id, doc_id, chunk_index, text, page_num, heading, token_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    chunk.chunk_id,
                    chunk.doc_id,
                    chunk.chunk_index,
                    chunk.text,
                    chunk.page_num,
                    chunk.heading,
                    len(chunk.text),
                )
                for chunk in chunks
            ],
        )
        conn.commit()

    texts = [chunk.text for chunk in chunks]
    vector_store.add_chunks(
        chunk_ids=[chunk.chunk_id for chunk in chunks],
        embeddings=embedder.embed(texts),
        texts=texts,
        metadatas=[
            {
                "doc_id": chunk.doc_id,
                "doc_name": chunk.doc_name,
                "chunk_index": chunk.chunk_index,
                "page_num": chunk.page_num or 0,
                "heading": chunk.heading or "",
                "collection_id": chunk.collection_id or "",
            }
            for chunk in chunks
        ],
    )


def chunk_keys(chunk: RetrievedChunk) -> set[str]:
    return {
        f"chunk:{chunk.chunk_id}",
        f"doc:{chunk.doc_id}",
        f"name:{chunk.doc_name}",
    }


def matched_relevance_keys(
    example: EvaluationExample,
    chunk: RetrievedChunk,
) -> set[str]:
    """Return the labels satisfied by one retrieved chunk."""
    matched = chunk_keys(chunk) & example.relevant_keys()
    matched.update(f"text:{snippet}" for snippet in example.relevant_texts if snippet in chunk.text)
    return matched


def matched_forbidden_keys(
    example: EvaluationExample,
    chunk: RetrievedChunk,
) -> set[str]:
    """Return hard-negative labels matched by one retrieved chunk."""
    matched = chunk_keys(chunk) & example.forbidden_keys()
    matched.update(
        f"text:{snippet}" for snippet in example.forbidden_texts if snippet in chunk.text
    )
    return matched


def score_ranking(
    example: EvaluationExample,
    chunks: list[RetrievedChunk],
    k_values: Iterable[int],
) -> dict:
    """Score one ranked result list against its relevance labels."""
    relevant = example.relevant_keys()
    forbidden = example.forbidden_keys()
    if example.expect_no_results:
        no_answer_metrics: dict[str, float] = {
            "reciprocal_rank": 1.0 if not chunks else 0.0,
            "no_answer_correct": 1.0 if not chunks else 0.0,
        }
        for k in k_values:
            correct = 1.0 if not chunks[:k] else 0.0
            no_answer_metrics[f"hit_at_{k}"] = correct
            no_answer_metrics[f"recall_at_{k}"] = correct
            no_answer_metrics[f"hard_negative_free_at_{k}"] = correct
        return no_answer_metrics

    first_relevant_rank: int | None = None
    for rank, chunk in enumerate(chunks, start=1):
        if matched_relevance_keys(example, chunk):
            first_relevant_rank = rank
            break

    metrics: dict[str, float] = {
        "reciprocal_rank": 1.0 / first_relevant_rank if first_relevant_rank else 0.0,
        "no_answer_correct": 0.0,
    }
    for k in k_values:
        retrieved_relevant: set[str] = set()
        retrieved_forbidden: set[str] = set()
        for chunk in chunks[:k]:
            retrieved_relevant.update(matched_relevance_keys(example, chunk))
            retrieved_forbidden.update(matched_forbidden_keys(example, chunk))
        metrics[f"hit_at_{k}"] = 1.0 if retrieved_relevant else 0.0
        metrics[f"recall_at_{k}"] = len(retrieved_relevant) / len(relevant)
        metrics[f"hard_negative_free_at_{k}"] = (
            1.0 if not forbidden or not retrieved_forbidden else 0.0
        )
    return metrics


def aggregate_metrics(rows: list[dict], k_values: list[int]) -> dict:
    """Aggregate per-query metrics and latency into a report."""
    latencies = [row["latency_ms"] for row in rows]
    answerable_rows = [row for row in rows if not row.get("expect_no_results")]
    aggregate: dict[str, int | float | None] = {
        "queries": len(rows),
        "answerable_queries": len(answerable_rows),
        "mrr": statistics.fmean(row["reciprocal_rank"] for row in answerable_rows),
        "avg_latency_ms": statistics.fmean(latencies),
        "p95_latency_ms": _percentile(latencies, 0.95),
    }
    no_answer_rows = [row for row in rows if row.get("expect_no_results")]
    aggregate["no_answer_accuracy"] = (
        statistics.fmean(row["no_answer_correct"] for row in no_answer_rows)
        if no_answer_rows
        else None
    )
    for k in k_values:
        aggregate[f"hit_at_{k}"] = statistics.fmean(row[f"hit_at_{k}"] for row in answerable_rows)
        aggregate[f"recall_at_{k}"] = statistics.fmean(
            row[f"recall_at_{k}"] for row in answerable_rows
        )
        hard_negative_rows = [
            row for row in rows if row.get("has_hard_negatives") or row.get("expect_no_results")
        ]
        aggregate[f"hard_negative_free_at_{k}"] = (
            statistics.fmean(row[f"hard_negative_free_at_{k}"] for row in hard_negative_rows)
            if hard_negative_rows
            else None
        )
    return aggregate


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(math.ceil(percentile * len(ordered)) - 1, 0)
    return ordered[index]


def evaluate_mode(
    mode: str,
    examples: list[EvaluationExample],
    retriever: Retriever,
    k_values: list[int],
) -> dict:
    """Evaluate one retriever mode over all examples."""
    rows = []
    for example in examples:
        start = time.perf_counter()
        if mode.startswith("multi_hop_"):
            result, retrieval_queries = retrieve_with_query_plan(
                retriever,
                example.query,
                collection_id=example.collection_id,
                max_subqueries=get_settings().query_decomposition_max_subqueries,
            )
        else:
            result = retriever.retrieve(example.query, collection_id=example.collection_id)
            retrieval_queries = [example.query]
        latency_ms = (time.perf_counter() - start) * 1000
        metrics = score_ranking(example, result.chunks, k_values)
        rows.append(
            {
                "query": example.query,
                "retrieval_queries": retrieval_queries,
                "expect_no_results": example.expect_no_results,
                "has_hard_negatives": bool(example.forbidden_keys()),
                "confidence_rejected": result.confidence_rejected,
                "confidence_score": result.confidence_score,
                "rejection_reason": result.rejection_reason,
                "latency_ms": round(latency_ms, 2),
                "retrieved": [
                    {
                        "chunk_id": chunk.chunk_id,
                        "doc_id": chunk.doc_id,
                        "doc_name": chunk.doc_name,
                        "score": round(chunk.score, 6),
                        "rerank_score": (
                            round(chunk.rerank_score, 6) if chunk.rerank_score is not None else None
                        ),
                        "sources": chunk.retrieval_sources,
                    }
                    for chunk in result.chunks
                ],
                **metrics,
            }
        )
    return {"mode": mode, "metrics": aggregate_metrics(rows, k_values), "rows": rows}


def build_retrievers(
    modes: list[str],
    top_k: int,
    *,
    corpus_path: str | None = None,
    isolated_dir: str | None = None,
) -> dict[str, Retriever]:
    """Build retrievers that share one embedding model and vector-store client."""
    settings = get_settings()
    db_path = str(Path(isolated_dir) / "evaluation.db") if isolated_dir else settings.db_path
    chroma_dir = str(Path(isolated_dir) / "chroma") if isolated_dir else settings.chroma_dir
    init_db(db_path)
    embed_kwargs = {"model": settings.embedding_model}
    if settings.embedding_provider == "openai":
        embed_kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            embed_kwargs["base_url"] = settings.openai_base_url
    embedder = create_embedder(settings.embedding_provider, **embed_kwargs)
    if settings.embedding_provider == "local":
        # Avoid charging one evaluation mode for one-time model/device warmup.
        embedder.embed_query("retrieval evaluation warmup")
    vector_store = VectorStore(
        persist_dir=chroma_dir,
        embedding_dimension=settings.embedding_dimension,
    )
    if corpus_path:
        if not isolated_dir:
            raise ValueError("An isolated directory is required when --corpus is used")
        seed_evaluation_corpus(load_corpus(corpus_path), embedder, vector_store)
    vector_store.count()  # initialize Chroma/HNSW before latency measurement
    reranker = None
    if "hybrid_rerank" in modes:
        reranker = CrossEncoderReranker(settings.reranker_model)
        reranker.warmup()
    return {
        mode: Retriever(
            vector_store=vector_store,
            embedder=embedder,
            top_k=top_k,
            similarity_threshold=settings.similarity_threshold,
            hybrid_search_enabled=mode in {"hybrid", "hybrid_rerank", "multi_hop_hybrid"},
            candidate_multiplier=settings.retrieval_candidate_multiplier,
            rrf_k=settings.rrf_k,
            confidence_gate_enabled=settings.retrieval_confidence_gate_enabled,
            vector_only_min_score=settings.vector_only_min_score,
            reranker=reranker if mode == "hybrid_rerank" else None,
            rerank_top_n=settings.reranker_top_n,
        )
        for mode in modes
    }


def print_summary(reports: list[dict], k_values: list[int]) -> None:
    headers = [
        "mode",
        "MRR",
        *(f"Hit@{k}" for k in k_values),
        *(f"Recall@{k}" for k in k_values),
        *(f"HardNeg@{k}" for k in k_values),
        "NoAnswer",
    ]
    print("\t".join(headers))
    for report in reports:
        metrics = report["metrics"]
        values = [
            report["mode"],
            f"{metrics['mrr']:.3f}",
            *(f"{metrics[f'hit_at_{k}']:.3f}" for k in k_values),
            *(f"{metrics[f'recall_at_{k}']:.3f}" for k in k_values),
            *(
                (
                    f"{metrics[f'hard_negative_free_at_{k}']:.3f}"
                    if metrics[f"hard_negative_free_at_{k}"] is not None
                    else "n/a"
                )
                for k in k_values
            ),
            (
                f"{metrics['no_answer_accuracy']:.3f}"
                if metrics["no_answer_accuracy"] is not None
                else "n/a"
            ),
        ]
        print("\t".join(values))
        print(
            f"  latency avg={metrics['avg_latency_ms']:.1f}ms p95={metrics['p95_latency_ms']:.1f}ms"
        )


def parse_hit_thresholds(values: list[str]) -> dict[int, float]:
    """Parse repeated K=VALUE quality-gate arguments."""
    thresholds: dict[int, float] = {}
    for value in values:
        try:
            raw_k, raw_threshold = value.split("=", maxsplit=1)
            k = int(raw_k)
            threshold = float(raw_threshold)
        except ValueError as error:
            raise ValueError(f"Invalid Hit@K threshold '{value}', expected K=VALUE") from error
        if k < 1 or not 0.0 <= threshold <= 1.0:
            raise ValueError(f"Invalid Hit@K threshold '{value}', K >= 1 and 0 <= VALUE <= 1")
        thresholds[k] = threshold
    return thresholds


def quality_gate_failures(
    report: dict,
    *,
    min_mrr: float | None = None,
    min_hit_at: dict[int, float] | None = None,
    min_recall_at: dict[int, float] | None = None,
    min_no_answer_accuracy: float | None = None,
    min_hard_negative_free_at: dict[int, float] | None = None,
    max_p95_latency_ms: float | None = None,
) -> list[str]:
    """Return human-readable quality-gate failures for one mode report."""
    metrics = report["metrics"]
    failures: list[str] = []
    if min_mrr is not None and metrics["mrr"] < min_mrr:
        failures.append(f"MRR {metrics['mrr']:.3f} < {min_mrr:.3f}")
    for k, threshold in (min_hit_at or {}).items():
        metric_name = f"hit_at_{k}"
        actual = metrics.get(metric_name)
        if actual is None:
            failures.append(f"Hit@{k} was not evaluated")
        elif actual < threshold:
            failures.append(f"Hit@{k} {actual:.3f} < {threshold:.3f}")
    for k, threshold in (min_recall_at or {}).items():
        metric_name = f"recall_at_{k}"
        actual = metrics.get(metric_name)
        if actual is None:
            failures.append(f"Recall@{k} was not evaluated")
        elif actual < threshold:
            failures.append(f"Recall@{k} {actual:.3f} < {threshold:.3f}")
    for k, threshold in (min_hard_negative_free_at or {}).items():
        metric_name = f"hard_negative_free_at_{k}"
        actual = metrics.get(metric_name)
        if actual is None:
            failures.append(f"HardNeg@{k} was not evaluated")
        elif actual < threshold:
            failures.append(f"HardNeg@{k} {actual:.3f} < {threshold:.3f}")
    no_answer_accuracy = metrics.get("no_answer_accuracy")
    if min_no_answer_accuracy is not None:
        if no_answer_accuracy is None:
            failures.append("No-answer accuracy was not evaluated")
        elif no_answer_accuracy < min_no_answer_accuracy:
            failures.append(
                f"No-answer accuracy {no_answer_accuracy:.3f} < {min_no_answer_accuracy:.3f}"
            )
    if max_p95_latency_ms is not None and metrics["p95_latency_ms"] > max_p95_latency_ms:
        failures.append(
            f"P95 latency {metrics['p95_latency_ms']:.1f}ms > {max_p95_latency_ms:.1f}ms"
        )
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, help="JSONL evaluation dataset")
    parser.add_argument(
        "--corpus",
        help="Versioned JSONL corpus; evaluates in temporary isolated SQLite/Chroma stores",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=("vector", "hybrid", "hybrid_rerank", "multi_hop_hybrid"),
        default=("vector", "hybrid"),
    )
    parser.add_argument("--k", nargs="+", type=int, default=(1, 3, 5))
    parser.add_argument("--output", help="Optional path for the full JSON report")
    parser.add_argument(
        "--summary-output",
        help="Optional path for aggregate metrics only (safe to commit)",
    )
    parser.add_argument(
        "--gate-mode",
        choices=("vector", "hybrid", "hybrid_rerank", "multi_hop_hybrid"),
        default="hybrid",
    )
    parser.add_argument("--min-mrr", type=float)
    parser.add_argument(
        "--min-hit-at",
        action="append",
        default=[],
        metavar="K=VALUE",
        help="Repeatable minimum Hit@K threshold, for example 3=0.95",
    )
    parser.add_argument(
        "--min-recall-at",
        action="append",
        default=[],
        metavar="K=VALUE",
        help="Repeatable minimum Recall@K threshold, for example 5=1.00",
    )
    parser.add_argument(
        "--min-hard-negative-free-at",
        action="append",
        default=[],
        metavar="K=VALUE",
        help="Repeatable minimum hard-negative-free@K threshold",
    )
    parser.add_argument("--min-no-answer-accuracy", type=float)
    parser.add_argument("--max-p95-latency-ms", type=float)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    k_values = sorted(set(args.k))
    if not k_values or k_values[0] < 1:
        raise SystemExit("--k values must be positive integers")
    try:
        hit_thresholds = parse_hit_thresholds(args.min_hit_at)
        recall_thresholds = parse_hit_thresholds(args.min_recall_at)
        hard_negative_thresholds = parse_hit_thresholds(args.min_hard_negative_free_at)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    missing_k_values = sorted(
        (set(hit_thresholds) | set(recall_thresholds) | set(hard_negative_thresholds))
        - set(k_values)
    )
    if missing_k_values:
        raise SystemExit(f"Quality gates require missing --k values: {missing_k_values}")
    for name in ("min_mrr", "min_no_answer_accuracy"):
        value = getattr(args, name)
        if value is not None and not 0.0 <= value <= 1.0:
            raise SystemExit(f"--{name.replace('_', '-')} must be between 0 and 1")
    if args.max_p95_latency_ms is not None and args.max_p95_latency_ms <= 0:
        raise SystemExit("--max-p95-latency-ms must be positive")

    examples = load_dataset(args.dataset)
    top_k = max(k_values)
    evaluation_workspace = (
        tempfile.TemporaryDirectory(prefix="rag-evaluation-") if args.corpus else nullcontext(None)
    )
    with evaluation_workspace as isolated_dir:
        retrievers = build_retrievers(
            args.modes,
            top_k,
            corpus_path=args.corpus,
            isolated_dir=isolated_dir,
        )
        settings = get_settings()
        if settings.embedding_provider == "local":
            # Compile common input shapes before timing either mode.
            shared_embedder = retrievers[args.modes[0]].embedder
            for example in examples:
                shared_embedder.embed_query(example.query)
        reports = []
        for mode in args.modes:
            reports.append(evaluate_mode(mode, examples, retrievers[mode], k_values))

    print_summary(reports, k_values)
    if args.output:
        payload = {
            "dataset": str(Path(args.dataset).resolve()),
            "examples": [asdict(example) for example in examples],
            "reports": reports,
        }
        Path(args.output).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    if args.summary_output:
        summary = {
            "dataset": str(Path(args.dataset)),
            "k_values": k_values,
            "reports": [
                {"mode": report["mode"], "metrics": report["metrics"]} for report in reports
            ],
        }
        Path(args.summary_output).write_text(
            json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    gates_enabled = any(
        value is not None
        for value in (
            args.min_mrr,
            args.min_no_answer_accuracy,
            args.max_p95_latency_ms,
        )
    ) or bool(hit_thresholds or recall_thresholds or hard_negative_thresholds)
    if gates_enabled:
        gate_report = next(
            (report for report in reports if report["mode"] == args.gate_mode),
            None,
        )
        if gate_report is None:
            raise SystemExit(f"Quality gate mode '{args.gate_mode}' was not evaluated")
        failures = quality_gate_failures(
            gate_report,
            min_mrr=args.min_mrr,
            min_hit_at=hit_thresholds,
            min_recall_at=recall_thresholds,
            min_no_answer_accuracy=args.min_no_answer_accuracy,
            min_hard_negative_free_at=hard_negative_thresholds,
            max_p95_latency_ms=args.max_p95_latency_ms,
        )
        if failures:
            print(f"Quality gate failed for {args.gate_mode}:")
            for failure in failures:
                print(f"  - {failure}")
            raise SystemExit(1)
        print(f"Quality gate passed for {args.gate_mode}")


if __name__ == "__main__":
    main()
