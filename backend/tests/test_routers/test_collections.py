"""Tests for collection assignment and vector metadata synchronization."""

from app.db.database import get_connection


def _insert_document(doc_id: str, collection_id: str | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO documents
               (id, filename, file_type, file_path, file_size, status, collection_id)
               VALUES (?, 'test.txt', 'txt', '/tmp/test.txt', 10, 'ready', ?)""",
            (doc_id, collection_id),
        )
        conn.commit()


def test_assign_collection_updates_sqlite_and_chroma(test_app, mock_rag_pipeline):
    created = test_app.post("/api/collections", json={"name": "Machine Learning"}).json()
    _insert_document("doc-1")

    response = test_app.put(
        "/api/collections/documents/doc-1/collection",
        json={"collection_id": created["id"]},
    )

    assert response.status_code == 200
    with get_connection() as conn:
        doc = conn.execute("SELECT collection_id FROM documents WHERE id='doc-1'").fetchone()
        collection = conn.execute(
            "SELECT doc_count FROM collections WHERE id=?", (created["id"],)
        ).fetchone()
    assert doc["collection_id"] == created["id"]
    assert collection["doc_count"] == 1
    mock_rag_pipeline.vector_store.update_document_collection.assert_called_with(
        "doc-1", created["id"]
    )


def test_delete_collection_clears_vector_metadata(test_app, mock_rag_pipeline):
    created = test_app.post("/api/collections", json={"name": "Temporary"}).json()
    _insert_document("doc-2", created["id"])

    response = test_app.delete(f"/api/collections/{created['id']}")

    assert response.status_code == 200
    with get_connection() as conn:
        doc = conn.execute("SELECT collection_id FROM documents WHERE id='doc-2'").fetchone()
    assert doc["collection_id"] is None
    mock_rag_pipeline.vector_store.update_document_collection.assert_called_with("doc-2", None)
