"""Chat API routes with SSE streaming."""

import json
import logging

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.db.citation_utils import build_citations_payload
from app.db.database import get_db
from app.db.session_utils import (
    delete_empty_session,
    fetch_history,
    get_or_create_session,
    save_assistant_response,
    save_user_message,
)
from app.dependencies import get_rag_pipeline
from app.models.schemas import (
    ChatMessageResponse,
    ChatRequest,
    ChatSessionResponse,
    CitationData,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])
logger = logging.getLogger(__name__)


# ── Chat (SSE streaming) ──────────────────────────────────


@router.post("")
async def chat(request: ChatRequest):
    """Send a message and get a streaming RAG response via SSE."""
    pipeline = get_rag_pipeline()
    is_new_session = request.session_id is None
    with get_db() as conn:
        session_id = get_or_create_session(conn, request.session_id, request.message)
        history = fetch_history(conn, session_id) if request.session_id else []
        # NOTE: user message is saved inside event_stream() AFTER LLM succeeds
        # to avoid orphaned messages when the LLM call fails

    # Stream the response
    async def event_stream():
        # Yield session ID first (before any heavy work)
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

        try:
            # Run the RAG query with conversation history
            gen_result, debug_info = await pipeline.query(
                request.message,
                history=history,
                collection_id=request.collection_id,
            )
        except Exception as e:
            logger.exception("RAG query failed for session %s", session_id)
            if is_new_session:
                with get_db() as conn:
                    delete_empty_session(conn, session_id)
            error_msg = f"回答生成失败: {e}"
            yield f"event: error\ndata: {json.dumps({'error': error_msg})}\n\n"
            yield f"event: done\ndata: {json.dumps({'error': error_msg})}\n\n"
            return

        # Save both user message and assistant response in one transaction
        # (user message was NOT saved before to avoid orphans on LLM failure)
        with get_db() as conn:
            save_user_message(conn, session_id, request.message)
            assistant_msg_id = save_assistant_response(
                conn, session_id, gen_result.content, gen_result.citations
            )

        # Yield the answer text
        yield f"event: token\ndata: {json.dumps({'text': gen_result.content})}\n\n"

        # Yield citations
        citations_payload = build_citations_payload(gen_result.citations)
        yield f"event: citations\ndata: {json.dumps(citations_payload, ensure_ascii=False)}\n\n"

        # Yield debug info
        debug_payload = {
            "query": debug_info.query,
            "embedding_model": debug_info.embedding_model,
            "top_k_chunks": [c.model_dump() for c in debug_info.top_k_chunks],
            "token_usage": debug_info.token_usage.model_dump(),
            "retrieval_time_ms": debug_info.retrieval_time_ms,
            "generation_time_ms": debug_info.generation_time_ms,
        }
        yield f"event: debug\ndata: {json.dumps(debug_payload, ensure_ascii=False)}\n\n"

        # Done
        yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg_id, 'citations_count': len(gen_result.citations)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── History Search ──────────────────────────────────────────


def _escape_like(s: str) -> str:
    """Escape special characters in LIKE patterns (% and _)."""
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/search")
async def search_history(q: str, mode: str = "fulltext", limit: int = 20):
    """Search chat message history by full-text or semantic search."""
    limit = min(limit, 100)  # Cap to prevent abuse
    with get_db() as conn:
        try:
            # Try FTS5 search first
            rows = conn.execute(
                """SELECT cm.id, cm.session_id, cm.role, cm.content, cm.created_at,
                          cs.title as session_title,
                          bm25(chat_messages_fts) as score
                   FROM chat_messages_fts fts
                   JOIN chat_messages cm ON cm.rowid = fts.rowid
                   JOIN chat_sessions cs ON cs.id = cm.session_id
                   WHERE chat_messages_fts MATCH ?
                   ORDER BY score
                   LIMIT ?""",
                (q, limit),
            ).fetchall()

            # Fallback to LIKE search if FTS5 returns no results (common for Chinese)
            if not rows:
                rows = conn.execute(
                    """SELECT cm.id, cm.session_id, cm.role, cm.content, cm.created_at,
                              cs.title as session_title,
                              1.0 as score
                       FROM chat_messages cm
                       JOIN chat_sessions cs ON cs.id = cm.session_id
                       WHERE cm.content LIKE ?
                       ORDER BY cm.created_at DESC
                       LIMIT ?""",
                    (f"%{_escape_like(q)}%", limit),
                ).fetchall()

            return [
                {
                    "message_id": r["id"],
                    "session_id": r["session_id"],
                    "session_title": r["session_title"],
                    "role": r["role"],
                    "content_preview": r["content"][:200],
                    "score": round(abs(r["score"]), 4) if r["score"] else 0,
                    "created_at": str(r["created_at"]),
                }
                for r in rows
            ]
        except Exception as e:
            # FTS might fail for very short queries or special chars, fallback to LIKE
            logger.warning("FTS search failed, falling back to LIKE: %s", e)
            try:
                rows = conn.execute(
                    """SELECT cm.id, cm.session_id, cm.role, cm.content, cm.created_at,
                              cs.title as session_title,
                              1.0 as score
                       FROM chat_messages cm
                       JOIN chat_sessions cs ON cs.id = cm.session_id
                       WHERE cm.content LIKE ?
                       ORDER BY cm.created_at DESC
                       LIMIT ?""",
                    (f"%{_escape_like(q)}%", limit),
                ).fetchall()
                return [
                    {
                        "message_id": r["id"],
                        "session_id": r["session_id"],
                        "session_title": r["session_title"],
                        "role": r["role"],
                        "content_preview": r["content"][:200],
                        "score": 1.0,
                        "created_at": str(r["created_at"]),
                    }
                    for r in rows
                ]
            except Exception as e:
                logger.error("LIKE search fallback also failed: %s", e)
                return []


# ── Sessions ───────────────────────────────────────────────


@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions():
    """List all chat sessions."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT 500"
        ).fetchall()
        return [
            ChatSessionResponse(
                id=r["id"],
                title=r["title"],
                message_count=r["message_count"],
                created_at=str(r["created_at"]),
                updated_at=str(r["updated_at"]),
            )
            for r in rows
        ]


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(session_id: str):
    """Get all messages in a session, with citations."""
    with get_db() as conn:
        messages = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()

        if not messages:
            return []

        # Batch-fetch all citations for this session's messages (fixes N+1)
        msg_ids = [msg["id"] for msg in messages]
        placeholders = ",".join("?" for _ in msg_ids)
        citations_rows = conn.execute(
            f"""SELECT * FROM citations WHERE message_id IN ({placeholders})
                ORDER BY message_id, chunk_index""",
            msg_ids,
        ).fetchall()

        # Group citations by message_id
        citations_by_msg: dict[str, list[CitationData]] = {}
        for c in citations_rows:
            mid = c["message_id"]
            if mid not in citations_by_msg:
                citations_by_msg[mid] = []
            citations_by_msg[mid].append(
                CitationData(
                    doc_name=c["doc_name"],
                    page_num=c["page_num"],
                    chunk_id=c["chunk_id"],
                    chunk_index=c["chunk_index"],
                    text_preview=c["text_preview"],
                )
            )

        return [
            ChatMessageResponse(
                id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                citations=citations_by_msg.get(msg["id"], []),
                created_at=str(msg["created_at"]),
            )
            for msg in messages
        ]


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and all its messages."""
    with get_db() as conn:
        conn.execute(
            "DELETE FROM citations WHERE message_id IN "
            "(SELECT id FROM chat_messages WHERE session_id=?)",
            (session_id,),
        )
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
        conn.commit()
        return {"success": True}
