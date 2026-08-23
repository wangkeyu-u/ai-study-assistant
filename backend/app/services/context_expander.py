"""Expand high-confidence retrieval hits with nearby source chunks."""

from __future__ import annotations

from app.db.database import get_db
from app.services.retriever import RetrievedChunk


def expand_chunk_neighbors(
    chunks: list[RetrievedChunk],
    *,
    window: int = 1,
    max_neighbors: int = 2,
    max_chunks: int = 8,
    max_chars: int = 9000,
) -> list[RetrievedChunk]:
    """Add adjacent chunks to repair context split across chunk boundaries.

    Retrieved chunks remain first-class evidence. Neighbors are explicitly marked
    and receive a discounted score, so diagnostics can distinguish recall hits
    from continuity context.
    """
    if not chunks or window <= 0 or max_neighbors <= 0:
        return chunks[:max_chunks]

    selected_ids = {chunk.chunk_id for chunk in chunks}
    candidates: list[tuple[float, int, RetrievedChunk]] = []
    with get_db() as conn:
        for anchor_order, anchor in enumerate(chunks):
            start_index = max(0, anchor.chunk_index - window)
            end_index = anchor.chunk_index + window
            rows = conn.execute(
                """SELECT id, text, page_num, heading, chunk_index
                   FROM chunks
                   WHERE doc_id = ? AND is_active = 1
                         AND chunk_index BETWEEN ? AND ? AND id != ?
                   ORDER BY ABS(chunk_index - ?), chunk_index""",
                (anchor.doc_id, start_index, end_index, anchor.chunk_id, anchor.chunk_index),
            ).fetchall()
            for row in rows:
                if row["id"] in selected_ids:
                    continue
                distance = abs(row["chunk_index"] - anchor.chunk_index)
                neighbor = RetrievedChunk(
                    chunk_id=row["id"],
                    text=row["text"],
                    score=max(anchor.score * (0.86 - 0.08 * (distance - 1)), 0.0),
                    doc_id=anchor.doc_id,
                    doc_name=anchor.doc_name,
                    page_num=row["page_num"],
                    chunk_index=row["chunk_index"],
                    heading=row["heading"],
                    retrieval_sources=["neighbor"],
                )
                candidates.append((anchor.score, -anchor_order, neighbor))

    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    additions: list[RetrievedChunk] = []
    for _score, _anchor_order, neighbor in candidates:
        if neighbor.chunk_id in selected_ids:
            continue
        additions.append(neighbor)
        selected_ids.add(neighbor.chunk_id)
        if len(additions) >= max_neighbors:
            break

    combined = [*chunks, *additions]
    combined.sort(
        key=lambda chunk: (
            chunks.index(chunk) if chunk in chunks else len(chunks),
            chunk.doc_id,
            chunk.chunk_index,
        )
    )

    fitted: list[RetrievedChunk] = []
    char_count = 0
    for chunk in combined:
        if len(fitted) >= max_chunks:
            break
        if fitted and char_count + len(chunk.text) > max_chars:
            continue
        fitted.append(chunk)
        char_count += len(chunk.text)
    return fitted
