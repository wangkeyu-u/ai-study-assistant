"""Shared session-management helpers used by chat and multi_agent routers."""

from __future__ import annotations

import uuid

from fastapi import HTTPException

from app.db.citation_utils import save_citations


def get_or_create_session(conn, session_id: str | None, first_message: str) -> str:
    """Look up an existing session or create a new one.

    Returns the session_id.
    Raises HTTPException 404 if session_id is given but not found.
    """
    if session_id:
        session = conn.execute("SELECT * FROM chat_sessions WHERE id=?", (session_id,)).fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        return session_id

    new_id = str(uuid.uuid4())
    title = first_message[:30] + ("..." if len(first_message) > 30 else "")
    conn.execute(
        "INSERT INTO chat_sessions (id, title) VALUES (?, ?)",
        (new_id, title),
    )
    conn.commit()
    return new_id


def fetch_history(conn, session_id: str) -> list[dict]:
    """Retrieve conversation history for a session as a list of role/content dicts."""
    rows = conn.execute(
        "SELECT role, content FROM chat_messages WHERE session_id=? ORDER BY created_at",
        (session_id,),
    ).fetchall()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def save_user_message(conn, session_id: str, message: str) -> str:
    """Stage a user message and return its id.

    The caller owns the transaction so the user and assistant messages can be
    committed atomically by ``save_assistant_response``.
    """
    msg_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO chat_messages (id, session_id, role, content) VALUES (?, ?, 'user', ?)",
        (msg_id, session_id, message),
    )
    return msg_id


def delete_empty_session(conn, session_id: str) -> None:
    """Delete a session only when it still has no persisted messages."""
    conn.execute(
        """DELETE FROM chat_sessions
           WHERE id=?
             AND NOT EXISTS (
                 SELECT 1 FROM chat_messages WHERE session_id=chat_sessions.id
             )""",
        (session_id,),
    )
    conn.commit()


def save_assistant_response(
    conn,
    session_id: str,
    content: str,
    citations: list,
) -> str:
    """Save the assistant message, its citations, and update session metadata.

    Returns the new message id.
    """
    msg_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO chat_messages (id, session_id, role, content) VALUES (?, ?, 'assistant', ?)",
        (msg_id, session_id, content),
    )

    save_citations(conn, msg_id, citations)

    conn.execute(
        "UPDATE chat_sessions SET message_count = message_count + 2, updated_at = CURRENT_TIMESTAMP WHERE id=?",
        (session_id,),
    )
    conn.commit()
    return msg_id
