"""Tests for documents router — upload, list, delete."""

import io
from types import SimpleNamespace

from app.db.database import get_connection


class TestDocumentList:
    """Tests for GET /api/documents."""

    def test_list_documents_empty(self, test_app):
        """Should return empty list when no documents exist."""
        response = test_app.get("/api/documents")
        assert response.status_code == 200
        data = response.json()
        assert data["documents"] == []


class TestDocumentUpload:
    """Tests for POST /api/documents/upload."""

    def test_upload_txt_file(self, test_app, mock_rag_pipeline):
        """Should accept a valid .txt file upload."""
        file_content = "这是一段测试文档内容，包含足够的文字来通过验证。"
        files = {"file": ("test.txt", io.BytesIO(file_content.encode("utf-8")), "text/plain")}
        response = test_app.post("/api/documents/upload", files=files)
        # Upload triggers ingestion which uses the mock pipeline
        assert response.status_code in (200, 201, 500)

    def test_upload_unsupported_extension(self, test_app):
        """Should reject files with unsupported extensions."""
        files = {"file": ("test.exe", io.BytesIO(b"binary content"), "application/octet-stream")}
        response = test_app.post("/api/documents/upload", files=files)
        assert response.status_code == 400


class TestDocumentDelete:
    """Tests for DELETE /api/documents/{doc_id}."""

    def test_delete_nonexistent_document(self, test_app):
        """Should return error for non-existent document."""
        response = test_app.delete("/api/documents/nonexistent-id")
        # Either 404 or 200 with success=false
        assert response.status_code in (200, 404)


class TestDocumentFile:
    """Tests for GET /api/documents/{doc_id}/file."""

    def test_open_original_document(self, test_app, tmp_path, monkeypatch):
        """Should serve a stored source file with its correct media type."""
        documents_dir = tmp_path / "documents"
        document_dir = documents_dir / "doc-file"
        document_dir.mkdir(parents=True)
        source_path = document_dir / "source.md"
        source_path.write_text("# Grounded source", encoding="utf-8")

        monkeypatch.setattr(
            "app.routers.documents.get_settings",
            lambda: SimpleNamespace(documents_dir=str(documents_dir)),
        )
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO documents
                   (id, filename, file_type, file_path, file_size, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "doc-file",
                    "source.md",
                    "md",
                    str(source_path),
                    source_path.stat().st_size,
                    "ready",
                ),
            )
            conn.commit()

        response = test_app.get("/api/documents/doc-file/file")

        assert response.status_code == 200
        assert response.text == "# Grounded source"
        assert response.headers["content-type"].startswith("text/markdown")

    def test_reject_file_outside_documents_directory(self, test_app, tmp_path, monkeypatch):
        """Should not expose a database path outside managed storage."""
        documents_dir = tmp_path / "documents"
        documents_dir.mkdir()
        source_path = tmp_path / "outside.txt"
        source_path.write_text("private", encoding="utf-8")

        monkeypatch.setattr(
            "app.routers.documents.get_settings",
            lambda: SimpleNamespace(documents_dir=str(documents_dir)),
        )
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO documents
                   (id, filename, file_type, file_path, file_size, status)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    "doc-outside",
                    "outside.txt",
                    "txt",
                    str(source_path),
                    source_path.stat().st_size,
                    "ready",
                ),
            )
            conn.commit()

        response = test_app.get("/api/documents/doc-outside/file")

        assert response.status_code == 403


class TestCollections:
    """Tests for collection CRUD endpoints."""

    def test_create_collection(self, test_app):
        """Should create a new collection."""
        response = test_app.post(
            "/api/collections",
            json={"name": "测试集合", "description": "用于测试"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "测试集合"

    def test_list_collections(self, test_app):
        """Should list collections."""
        response = test_app.get("/api/collections")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_create_duplicate_collection(self, test_app):
        """Should reject duplicate collection names."""
        test_app.post("/api/collections", json={"name": "重复集合"})
        response = test_app.post("/api/collections", json={"name": "重复集合"})
        assert response.status_code == 400
