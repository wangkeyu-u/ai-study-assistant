"""Shared citation persistence helpers used by chat and multi_agent routers."""

from __future__ import annotations

import uuid


def save_citations(conn, message_id: str, citations: list) -> int:
    """Persist citations for a chat message.

    Supports both dict-based citations (from agent streaming) and
    object-based citations (from Generator CitationMark dataclass).

    Args:
        conn: An active SQLite connection (from get_db()).
        message_id: The chat_messages.id to associate citations with.
        citations: List of citations, each either a dict or an object with
                   attributes: chunk_id, doc_name, page_num, chunk_index, text_preview.

    Returns:
        Number of citations actually saved (skips orphan chunks).
    """
    saved = 0
    for citation in citations:
        # Normalize dict vs object access
        chunk_id = citation.get("chunk_id", "") if isinstance(citation, dict) else citation.chunk_id
        doc_name = citation.get("doc_name", "") if isinstance(citation, dict) else citation.doc_name
        page_num = citation.get("page_num") if isinstance(citation, dict) else citation.page_num
        chunk_index = (
            citation.get("chunk_index", 0) if isinstance(citation, dict) else citation.chunk_index
        )
        text_preview = (
            citation.get("text_preview", "")
            if isinstance(citation, dict)
            else citation.text_preview
        )

        # Lookup doc_id from chunks table
        row = conn.execute("SELECT doc_id FROM chunks WHERE id=?", (chunk_id,)).fetchone()
        if not row or not row["doc_id"]:
            continue  # skip orphan citations

        citation_id = str(uuid.uuid4())
        conn.execute(
            """INSERT INTO citations
               (id, message_id, doc_id, chunk_id, doc_name, page_num, chunk_index, text_preview)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                citation_id,
                message_id,
                row["doc_id"],
                chunk_id,
                doc_name,
                page_num,
                chunk_index,
                text_preview,
            ),
        )
        saved += 1
    return saved


def build_citations_payload(citations: list) -> list[dict]:
    """Convert citations to the SSE/JSON payload format.

    Supports both dict-based and object-based citations.
    """
    payload = []
    for c in citations:
        if isinstance(c, dict):
            payload.append(
                {
                    "doc_name": c.get("doc_name", ""),
                    "page_num": c.get("page_num"),
                    "chunk_id": c.get("chunk_id", ""),
                    "chunk_index": c.get("chunk_index", 0),
                    "text_preview": c.get("text_preview", ""),
                }
            )
        else:
            payload.append(
                {
                    "doc_name": c.doc_name,
                    "page_num": c.page_num,
                    "chunk_id": c.chunk_id,
                    "chunk_index": c.chunk_index,
                    "text_preview": c.text_preview,
                }
            )
    return payload
