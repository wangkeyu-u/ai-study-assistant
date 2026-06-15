"""Tests for chat router — SSE streaming and session management."""

from app.db.database import get_connection


class TestChatEndpoint:
    """Tests for POST /api/chat — SSE streaming endpoint."""

    def test_chat_returns_sse_stream(self, test_app, mock_rag_pipeline):
        """Chat should return Server-Sent Events stream."""
        response = test_app.post(
            "/api/chat",
            json={"message": "测试问题", "session_id": None},
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_chat_creates_session(self, test_app, tmp_db):
        """First message should create a new session."""
        response = test_app.post(
            "/api/chat",
            json={"message": "你好", "session_id": None},
        )
        assert response.status_code == 200

    def test_chat_with_session_id(self, test_app, tmp_db):
        """Should accept existing session_id."""
        # First create a session
        response1 = test_app.post(
            "/api/chat",
            json={"message": "你好"},
        )
        assert response1.status_code == 200

    def test_chat_empty_message(self, test_app):
        """Empty message should be handled gracefully."""
        response = test_app.post(
            "/api/chat",
            json={"message": ""},
        )
        # Should still return 200 (the generator handles empty input)
        assert response.status_code == 200

    def test_failed_new_chat_does_not_leave_empty_session(self, test_app, mock_rag_pipeline):
        """A failed first turn should not leave an unusable empty session."""
        mock_rag_pipeline.query.side_effect = RuntimeError("model unavailable")

        response = test_app.post("/api/chat", json={"message": "测试问题"})

        assert response.status_code == 200
        assert "event: error" in response.text
        with get_connection() as conn:
            session_count = conn.execute("SELECT COUNT(*) FROM chat_sessions").fetchone()[0]
            message_count = conn.execute("SELECT COUNT(*) FROM chat_messages").fetchone()[0]
        assert session_count == 0
        assert message_count == 0


class TestChatSessions:
    """Tests for GET /api/chat/sessions."""

    def test_list_sessions_empty(self, test_app):
        """Should return empty list when no sessions exist."""
        response = test_app.get("/api/chat/sessions")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestHealthCheck:
    """Tests for GET /api/health."""

    def test_health_endpoint(self, test_app):
        """Health check should return status ok."""
        response = test_app.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "embedding_provider" in data
        assert "llm_model" in data
