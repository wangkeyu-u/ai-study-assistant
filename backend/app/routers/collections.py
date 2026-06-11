"""Collection (knowledge base group) management API routes."""

import uuid

from fastapi import APIRouter, HTTPException

from app.db.database import get_connection
from app.models.schemas import CollectionCreate, CollectionResponse, CollectionAssignRequest

router = APIRouter(prefix="/api/collections", tags=["collections"])


@router.post("", response_model=CollectionResponse)
async def create_collection(request: CollectionCreate):
    """Create a new collection group."""
    conn = get_connection()
    try:
        coll_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO collections (id, name, description) VALUES (?, ?, ?)",
            (coll_id, request.name, request.description),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM collections WHERE id=?", (coll_id,)).fetchone()
        return CollectionResponse(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            doc_count=row["doc_count"],
            created_at=str(row["created_at"]),
        )
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=400, detail=f"创建分组失败: {e}")
    finally:
        conn.close()


@router.get("", response_model=list[CollectionResponse])
async def list_collections():
    """List all collections."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM collections ORDER BY created_at DESC").fetchall()
        return [
            CollectionResponse(
                id=r["id"],
                name=r["name"],
                description=r["description"],
                doc_count=r["doc_count"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]
    finally:
        conn.close()


@router.delete("/{collection_id}")
async def delete_collection(collection_id: str):
    """Delete a collection (documents are NOT deleted, collection_id set to NULL)."""
    conn = get_connection()
    try:
        # Unlink documents from this collection
        conn.execute(
            "UPDATE documents SET collection_id = NULL WHERE collection_id = ?",
            (collection_id,),
        )
        conn.execute("DELETE FROM collections WHERE id=?", (collection_id,))
        conn.commit()
        return {"success": True}
    finally:
        conn.close()


@router.put("/documents/{doc_id}/collection")
async def assign_document_to_collection(doc_id: str, request: CollectionAssignRequest):
    """Assign a document to a collection (or remove from collection if collection_id is null)."""
    conn = get_connection()
    try:
        doc = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        conn.execute(
            "UPDATE documents SET collection_id=? WHERE id=?",
            (request.collection_id, doc_id),
        )
        # Update doc_count
        if request.collection_id:
            conn.execute(
                "UPDATE collections SET doc_count = (SELECT COUNT(*) FROM documents WHERE collection_id = ?) WHERE id = ?",
                (request.collection_id, request.collection_id),
            )
        conn.commit()
        return {"success": True}
    finally:
        conn.close()
