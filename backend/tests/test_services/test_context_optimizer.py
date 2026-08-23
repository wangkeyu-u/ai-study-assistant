from app.services.context_optimizer import optimize_context_chunks
from app.services.query_intelligence import analyze_query
from app.services.retriever import RetrievedChunk


def _chunk(
    chunk_id: str,
    text: str,
    *,
    doc_id: str = "doc-a",
    score: float = 0.8,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        score=score,
        doc_id=doc_id,
        doc_name=f"{doc_id}.pdf",
        page_num=1,
        chunk_index=0,
        heading=None,
        vector_score=score,
        retrieval_sources=["vector"],
    )


def test_optimize_context_keeps_document_coverage_for_comparison():
    profile = analyze_query("对比 CNN 和 RNN 的任务差异")
    chunks = [
        _chunk("a1", "CNN 用于图像识别和局部特征提取。", doc_id="doc-a", score=0.95),
        _chunk("a2", "CNN 也可以用于视觉分类任务。", doc_id="doc-a", score=0.9),
        _chunk("b1", "RNN 用于序列建模和时间序列预测。", doc_id="doc-b", score=0.7),
    ]

    selection = optimize_context_chunks(
        "对比 CNN 和 RNN 的任务差异",
        chunks,
        profile=profile,
        max_chunks=2,
        max_chars=4000,
        document_ids=["doc-a", "doc-b"],
    )

    assert {chunk.doc_id for chunk in selection.chunks} == {"doc-a", "doc-b"}
    assert selection.strategy == "intent_mmr:comparison"
    assert selection.original_count == 3
    assert selection.selected_count == 2


def test_optimize_context_respects_character_budget():
    profile = analyze_query("总结 RAG 如何减少幻觉")
    chunks = [
        _chunk("a", "RAG 通过检索外部资料减少幻觉。" * 20, score=0.9),
        _chunk("b", "引用校验会拒绝没有证据的回答。" * 20, score=0.8),
    ]

    selection = optimize_context_chunks(
        "总结 RAG 如何减少幻觉",
        chunks,
        profile=profile,
        max_chunks=4,
        max_chars=120,
    )

    assert len(selection.chunks) == 1
    assert selection.coverage_score >= 0


def test_context_coverage_is_not_diluted_by_long_relevant_context():
    profile = analyze_query("RAG 引用校验")
    chunks = [
        _chunk(
            "relevant",
            "RAG 系统通过引用校验保证回答可追溯。" + "额外背景信息。" * 80,
            score=0.9,
        )
    ]

    selection = optimize_context_chunks(
        "RAG 引用校验",
        chunks,
        profile=profile,
        max_chunks=1,
        max_chars=4000,
    )

    assert selection.coverage_score == 1.0
