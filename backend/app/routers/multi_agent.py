"""Multi-Agent API router — exposes the Supervisor-based chat endpoint."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.database import get_connection
from app.services.agents.supervisor import SupervisorAgent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/multi-agent", tags=["multi-agent"])

# Singleton supervisor instance (stateless, safe to share)
_supervisor: SupervisorAgent | None = None


def _get_supervisor() -> SupervisorAgent:
    global _supervisor
    if _supervisor is None:
        _supervisor = SupervisorAgent()
    return _supervisor


def _get_rag_pipeline():
    from app.main import rag_pipeline
    return rag_pipeline


# ── Request / Response schemas ──────────────────────────────────

class MultiAgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    collection_id: str | None = None


class MultiAgentChatResponse(BaseModel):
    content: str
    agent_name: str
    session_id: str
    metadata: dict = {}


# ── Endpoint ────────────────────────────────────────────────────

@router.post("/chat", response_model=MultiAgentChatResponse)
async def multi_agent_chat(request: MultiAgentChatRequest):
    """Process a message through the Multi-Agent Supervisor system.

    The Supervisor classifies the user's intent and routes to the best
    specialist agent (Tutor, Examiner, or Summarizer).
    """
    pipeline = _get_rag_pipeline()
    if pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    supervisor = _get_supervisor()
    conn = get_connection()

    try:
        # ── Session management ─────────────────────────────────
        if request.session_id:
            session = conn.execute(
                "SELECT * FROM chat_sessions WHERE id=?", (request.session_id,)
            ).fetchone()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
            session_id = request.session_id
        else:
            session_id = str(uuid.uuid4())
            title = request.message[:30] + ("..." if len(request.message) > 30 else "")
            conn.execute(
                "INSERT INTO chat_sessions (id, title) VALUES (?, ?)",
                (session_id, title),
            )
            conn.commit()

        # ── Fetch conversation history ─────────────────────────
        history: list[dict] = []
        if request.session_id:
            rows = conn.execute(
                "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at",
                (session_id,),
            ).fetchall()
            history = [{"role": r["role"], "content": r["content"]} for r in rows]

        # ── Save user message ──────────────────────────────────
        user_msg_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content) VALUES (?, ?, 'user', ?)",
            (user_msg_id, session_id, request.message),
        )
        conn.commit()

    finally:
        conn.close()

    # ── Route through Supervisor ────────────────────────────────
    try:
        agent_response = await supervisor.route(
            query=request.message,
            pipeline=pipeline,
            history=history,
            collection_id=request.collection_id,
        )
    except Exception as e:
        logger.exception("Multi-agent processing failed")
        raise HTTPException(status_code=500, detail=f"Multi-agent processing failed: {e}")

    # ── Save assistant message ─────────────────────────────────
    assistant_msg_id = str(uuid.uuid4())
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content) VALUES (?, ?, 'assistant', ?)",
            (assistant_msg_id, session_id, agent_response.content),
        )
        conn.execute(
            "UPDATE chat_sessions SET message_count = message_count + 2, updated_at = CURRENT_TIMESTAMP WHERE id=?",
            (session_id,),
        )
        conn.commit()
    finally:
        conn.close()

    return MultiAgentChatResponse(
        content=agent_response.content,
        agent_name=agent_response.agent_name,
        session_id=session_id,
        metadata=agent_response.metadata,
    )
