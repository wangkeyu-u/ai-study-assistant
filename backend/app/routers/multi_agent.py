"""Multi-Agent API router — SSE streaming endpoint with Supervisor routing."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db.database import get_db
from app.db.session_utils import (
    delete_empty_session,
    fetch_history,
    get_or_create_session,
    save_assistant_response,
    save_user_message,
)
from app.dependencies import get_rag_pipeline
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


# ── Request schema ───────────────────────────────────────────────


class MultiAgentChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    collection_id: str | None = None


# ── SSE Streaming Endpoint ───────────────────────────────────────


@router.post("/chat")
async def multi_agent_chat(request: MultiAgentChatRequest):
    """Process a message through the Multi-Agent Supervisor system with SSE streaming.

    The Supervisor classifies intent and routes to the best specialist agent.
    Response is streamed as Server-Sent Events with: session, token, citations, done.
    """
    pipeline = get_rag_pipeline()
    if pipeline is None:
        raise HTTPException(status_code=503, detail="RAG pipeline not initialized")

    supervisor = _get_supervisor()
    is_new_session = request.session_id is None
    with get_db() as conn:
        session_id = get_or_create_session(conn, request.session_id, request.message)
        history = fetch_history(conn, session_id) if request.session_id else []

    # ── SSE Stream generator ───────────────────────────────────
    async def event_stream():
        full_content = ""
        citations_data = []
        agent_name = ""
        response_saved = False

        try:
            yield f"event: session\ndata: {json.dumps({'session_id': session_id})}\n\n"

            async for event in supervisor.route_stream(
                query=request.message,
                pipeline=pipeline,
                history=history,
                collection_id=request.collection_id,
            ):
                event_type = event.get("type")

                if event_type == "token":
                    full_content += event.get("text", "")
                    yield f"event: token\ndata: {json.dumps({'text': event['text']}, ensure_ascii=False)}\n\n"

                elif event_type == "citations":
                    citations_data = event.get("citations", [])
                    yield f"event: citations\ndata: {json.dumps(citations_data, ensure_ascii=False)}\n\n"

                elif event_type == "done":
                    agent_name = event.get("agent_name", "")

            # Persist the complete turn only after the agent finishes successfully.
            with get_db() as conn:
                save_user_message(conn, session_id, request.message)
                assistant_msg_id = save_assistant_response(
                    conn, session_id, full_content, citations_data
                )
                response_saved = True

            # Final done event
            yield f"event: done\ndata: {json.dumps({'message_id': assistant_msg_id, 'agent_name': agent_name, 'citations_count': len(citations_data)}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.exception("Multi-agent streaming failed")
            error_message = f"处理请求时出错: {e}"
            yield f"event: error\ndata: {json.dumps({'error': error_message}, ensure_ascii=False)}\n\n"
            yield f"event: done\ndata: {json.dumps({'error': str(e)})}\n\n"
        finally:
            if is_new_session and not response_saved:
                with get_db() as conn:
                    delete_empty_session(conn, session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
