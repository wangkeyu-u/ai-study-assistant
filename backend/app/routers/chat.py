"""Chat API routes with SSE streaming."""

import json
import uuid
import time

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.db.database import get_connection
from app.models.schemas import (
    ChatRequest,
    ChatSessionResponse,
    ChatMessageResponse,
    CitationData,
)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _get_rag_pipeline():
    from app.main import rag_pipeline
    return rag_pipeline


# ── Chat (SSE streaming) ──────────────────────────────────

@router.post("")
async def chat(request: ChatRequest):
    """Send a message and get a streaming RAG response via SSE."""
    pipeline = _get_rag_pipeline()
    conn = get_connection()

    try:
        # Create or get session
        if request.session_id:
            session = conn.execute(
                "SELECT * FROM chat_sessions WHERE id=?", (request.session_id,)
            ).fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="会话不存在")
            session_id = request.session_id
        else:
            session_id = str(uuid.uuid4())
            title = request.message[:30] + ("..." if len(request.message) > 30 else "")
            conn.execute(
                "INSERT INTO chat_sessions (id, title) VALUES (?, ?)",
                (session_id, title),
            )
            conn.commit()

        # Fetch conversation history for multi-turn context
        history = []
        if request.session_id:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at",
                (session_id,),
            ).fetchall()
            history = [{"role": r["role"], "content": r["content"]} for r in rows]

        # Save user message
        user_msg_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content) VALUES (?, ?, 'user', ?)",
            (user_msg_id, session_id, request.message),
        )
        conn.commit()

    finally:
        conn.close()

    # Stream the response
    async def event_stream():
        full_text = ""
        citations_data = []
        start_time = time.time()

        # Run the RAG query with conversation history
        gen_result, debug_info = await pipeline.query(
            request.message,
            history=history,
            collection_id=request.collection_id,
        )

        # Save assistant message
        assistant_msg_id = str(uuid.uuid4())
        conn = get_connection()
        try:
            conn.execute(
                "INSERT INTO chat_messages (id, session_id, role, content) VALUES (?, ?, 'assistant', ?)",
                (assistant_msg_id, session_id, gen_result.content),
            )

            # Save citations
            for citation in gen_result.citations:
                citation_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO citations
                       (id, message_id, doc_id, chunk_id, doc_name, page_num, chunk_index, text_preview)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        citation_id,
                        assistant_msg_id,
                        "",   # doc_id from metadata if available
                        citation.chunk_id,
                        citation.doc_name,
                        citation.page_num,
                        citation.chunk_index,
                        citation.text_preview,
                    ),
                )

            # Update session metadata
            conn.execute(
                "UPDATE chat_sessions SET message_count = message_count + 2, updated_at = CURRENT_TIMESTAMP WHERE id=?",
                (session_id,),
            )
            conn.commit()
        finally:
            conn.close()

        # Yield session ID first
        yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

        # Yield the answer text
        yield f"event: token\ndata: {json.dumps({'text': gen_result.content})}\n\n"

        # Yield citations
        citations_payload = [
            {
                "doc_name": c.doc_name,
                "page_num": c.page_num,
                "chunk_id": c.chunk_id,
                "chunk_index": c.chunk_index,
                "text_preview": c.text_preview,
            }
            for c in gen_result.citations
        ]
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

@router.get("/search")
async def search_history(q: str, mode: str = "fulltext", limit: int = 20):
    """Search chat message history by full-text or semantic search."""
    conn = get_connection()
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
                (f"%{q}%", limit),
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
                (f"%{q}%", limit),
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
        except:
            return []
    finally:
        conn.close()


# ── Sessions ───────────────────────────────────────────────

@router.get("/sessions", response_model=list[ChatSessionResponse])
async def list_sessions():
    """List all chat sessions."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chat_sessions ORDER BY updated_at DESC"
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
    finally:
        conn.close()


@router.get("/sessions/{session_id}/messages", response_model=list[ChatMessageResponse])
async def get_session_messages(session_id: str):
    """Get all messages in a session, with citations."""
    conn = get_connection()
    try:
        messages = conn.execute(
            "SELECT * FROM chat_messages WHERE session_id=? ORDER BY created_at",
            (session_id,),
        ).fetchall()

        result = []
        for msg in messages:
            # Fetch citations for this message
            citations_rows = conn.execute(
                "SELECT * FROM citations WHERE message_id=?", (msg["id"],)
            ).fetchall()

            citations = [
                CitationData(
                    doc_name=c["doc_name"],
                    page_num=c["page_num"],
                    chunk_id=c["chunk_id"],
                    chunk_index=c["chunk_index"],
                    text_preview=c["text_preview"],
                )
                for c in citations_rows
            ]

            result.append(ChatMessageResponse(
                id=msg["id"],
                role=msg["role"],
                content=msg["content"],
                citations=citations,
                created_at=str(msg["created_at"]),
            ))

        return result
    finally:
        conn.close()


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a chat session and all its messages."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM citations WHERE message_id IN "
                     "(SELECT id FROM chat_messages WHERE session_id=?)",
                     (session_id,))
        conn.execute("DELETE FROM chat_messages WHERE session_id=?", (session_id,))
        conn.execute("DELETE FROM chat_sessions WHERE id=?", (session_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()
