"""Reproducible retrieval component ablation on a versioned synthetic challenge."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import random
import statistics
import subprocess
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from app.evaluation.retrieval import (
    _percentile,
    aggregate_metrics,
    build_retrievers,
    evaluate_mode,
    load_corpus,
    load_dataset,
)
from app.services.embedder import LocalEmbedder
from app.services.reranker import CrossEncoderReranker
from app.services.retriever import Retriever


class VariantOptions(TypedDict, total=False):
    hybrid_search_enabled: bool
    vector_search_enabled: bool
    fusion_method: str
    query_coverage_enabled: bool
    confidence_gate_enabled: bool
    score_penalties_enabled: bool


VARIANTS: dict[str, VariantOptions] = {
    "vector_only": dict(hybrid_search_enabled=False),
    "fts_only": dict(vector_search_enabled=False),
    "vector_fts_interleave": dict(fusion_method="interleave"),
    "vector_fts_rrf": {},
    "rrf_coverage": dict(query_coverage_enabled=True),
    "rrf_coverage_gate": dict(query_coverage_enabled=True, confidence_gate_enabled=True),
    "rrf_coverage_gate_reranker": dict(query_coverage_enabled=True, confidence_gate_enabled=True),
    # An explicit extra reference preserves all existing production heuristics.
    "production_reference": dict(
        query_coverage_enabled=True, confidence_gate_enabled=True, score_penalties_enabled=True
    ),
}


def extended_metrics(rows: list[dict], k_values: list[int]) -> dict:
    metrics = aggregate_metrics(rows, k_values)
    labeled = [r for r in rows if r["has_hard_negatives"] and not r["expect_no_results"]]
    metrics["p50_latency_ms"] = _percentile([r["latency_ms"] for r in rows], 0.5)
    metrics["hard_negative_queries"] = len(labeled)
    # Refusing every query must not receive a perfect hard-negative accuracy.
    metrics["hard_negative_accuracy"] = (
        statistics.fmean(r["hit_at_1"] * r["hard_negative_free_at_1"] for r in labeled)
        if labeled
        else None
    )
    metrics["answerable_refusal_rate"] = statistics.fmean(
        not r["retrieved"] for r in rows if not r["expect_no_results"]
    )
    for k in k_values:
        metrics[f"hard_negative_free_at_{k}"] = (
            statistics.fmean(r[f"hard_negative_free_at_{k}"] for r in labeled) if labeled else None
        )
    return metrics


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("eval/retrieval_challenge_v1.jsonl"))
    parser.add_argument(
        "--corpus", type=Path, default=Path("eval/corpora/retrieval_challenge_v1.jsonl")
    )
    parser.add_argument(
        "--labels", type=Path, default=Path("eval/retrieval_challenge_v1.labels.json")
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reranker", default="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be >= 1")
    import torch

    from app.config import get_settings

    torch.set_num_threads(1)
    settings = get_settings()
    if settings.embedding_provider != "local":
        parser.error("This experiment requires ASA_EMBEDDING_PROVIDER=local")
    examples, corpus = load_dataset(args.dataset), load_corpus(args.corpus)
    labels = json.loads(args.labels.read_text())["query_tags"]
    if any(e.query not in labels for e in examples):
        raise ValueError("Each query requires a category/language label")
    known_ids = {c.chunk_id for c in corpus}
    for e in examples:
        if not set(e.relevant_chunk_ids + e.forbidden_chunk_ids) <= known_ids:
            raise ValueError(f"Unknown chunk label: {e.query}")
        if set(e.relevant_chunk_ids) & set(e.forbidden_chunk_ids):
            raise ValueError(f"Conflicting labels: {e.query}")
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "scope": "AI-authored controlled synthetic regression, not general RAG performance",
        "dataset": str(args.dataset),
        "dataset_sha256": sha256(args.dataset),
        "corpus": str(args.corpus),
        "corpus_sha256": sha256(args.corpus),
        "labels_sha256": sha256(args.labels),
        "queries": len(examples),
        "documents": len({c.doc_id for c in corpus}),
        "chunks": len(corpus),
        "no_answer_queries": sum(e.expect_no_results for e in examples),
        "hard_negative_queries": sum(
            bool(e.forbidden_keys()) and not e.expect_no_results for e in examples
        ),
        "languages": dict(Counter(labels[e.query]["language"] for e in examples)),
        "categories": dict(Counter(labels[e.query]["category"] for e in examples)),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "device": "cpu",
        "torch_threads": 1,
        "repeats": args.repeats,
        "embedding_model": settings.embedding_model,
        "reranker_model": args.reranker,
        "packages": {
            p: importlib.metadata.version(p)
            for p in ["torch", "transformers", "sentence-transformers", "chromadb", "numpy"]
        },
        "code_base_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "source_sha256": {
            str(p): sha256(p) for p in [Path(__file__), Path("app/services/retriever.py")]
        },
        "protocol": {
            "top_k": 5,
            "candidate_multiplier": 4,
            "rrf_k": 60,
            "similarity_threshold": 0.3,
            "vector_only_min_score": 0.46,
            "penalties": "disabled except production_reference",
            "timing": "warm retrieval only; includes query embedding and reranking; excludes indexing, generation, translation and startup",
            "ordering": "seeded shuffle of modes per repeat; queries keep frozen order",
        },
        "reports": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")

    save()
    with tempfile.TemporaryDirectory(prefix="asa-ablation-") as temp:
        base = build_retrievers(
            ["vector"], 5, corpus_path=str(args.corpus), isolated_dir=temp, embedding_device="cpu"
        )["vector"]
        assert isinstance(base.embedder, LocalEmbedder)
        report["embedding_revision"] = getattr(
            base.embedder.model[0].auto_model.config, "_commit_hash", None
        )
        base.embedder.model.to("cpu")
        base.embedder.embed_query("warmup")
        retrievers = {}
        for name, overrides in VARIANTS.items():
            options: VariantOptions = dict(
                hybrid_search_enabled=True,
                vector_search_enabled=True,
                fusion_method="rrf",
                query_coverage_enabled=False,
                confidence_gate_enabled=False,
                score_penalties_enabled=False,
            )
            options.update(overrides)
            retrievers[name] = Retriever(
                base.vector_store,
                base.embedder,
                top_k=5,
                similarity_threshold=0.3,
                vector_only_min_score=0.46,
                candidate_multiplier=4,
                rrf_k=60,
                **options,
            )
        # Run available non-reranked variants even if model download is unavailable.
        try:
            reranker = CrossEncoderReranker(args.reranker)
            reranker.model.model.to("cpu")
            report["reranker_revision"] = getattr(reranker.model.model.config, "_commit_hash", None)
            reranker.warmup()
            retrievers["rrf_coverage_gate_reranker"].reranker = reranker
            report["reranker_status"] = "loaded"
        except Exception as error:
            del retrievers["rrf_coverage_gate_reranker"]
            report["reranker_status"] = f"not_run: {type(error).__name__}: {error}"
        for retriever in retrievers.values():
            retriever.retrieve(examples[0].query)
        collected: dict[str, list[dict]] = {name: [] for name in retrievers}
        rng = random.Random(20260915)
        for repetition in range(args.repeats):
            modes = list(retrievers)
            rng.shuffle(modes)
            for mode in modes:
                result = evaluate_mode(mode, examples, retrievers[mode], [1, 3, 5])
                for row in result["rows"]:
                    row["repetition"] = repetition
                    row.update(labels[row["query"]])
                collected[mode].extend(result["rows"])
                report["reports"] = [
                    {"mode": name, "metrics": extended_metrics(rows, [1, 3, 5]), "rows": rows}
                    for name, rows in collected.items()
                    if rows
                ]
                save()
                print(
                    mode,
                    repetition,
                    json.dumps(extended_metrics(result["rows"], [1, 3, 5])),
                    flush=True,
                )
        report["complete"] = len(retrievers) == len(VARIANTS)
        save()


if __name__ == "__main__":
    run()
