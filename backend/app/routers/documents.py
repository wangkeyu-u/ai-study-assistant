"""Document management API routes."""

import os
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.db.database import get_connection
from app.models.schemas import DocumentResponse, DocumentListResponse, ChunkResponse, TagAssignRequest

router = APIRouter(prefix="/api/documents", tags=["documents"])


def _get_rag_pipeline():
    """Lazy import to avoid circular dependency."""
    from app.main import rag_pipeline
    return rag_pipeline


# ── Upload ─────────────────────────────────────────────────

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(file: UploadFile = File(...), collection_id: str | None = None):
    """Upload a document file for processing."""
    settings = get_settings()

    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in settings.supported_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件格式: {ext}。仅支持: {', '.join(settings.supported_extensions)}",
        )

    # Determine file type
    type_map = {".pdf": "pdf", ".txt": "txt", ".md": "md"}
    file_type = type_map[ext]

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Check size limit
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"文件超过 {settings.max_upload_size_mb}MB 限制",
        )

    # Save file locally
    doc_id = str(uuid.uuid4())
    save_dir = os.path.join(settings.documents_dir, doc_id)
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, file.filename)

    with open(file_path, "wb") as f:
        f.write(content)

    # Run ingestion pipeline (in a thread to not block the event loop)
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _get_rag_pipeline().ingest_document(
            file_path=file_path,
            filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            collection_id=collection_id,
        ),
    )

    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result.get("error", "处理失败"))

    # Fetch the created document
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=?", (result["doc_id"],)
        ).fetchone()
        return _row_to_response(row, conn=conn)
    finally:
        conn.close()


# ── Note (manual input) ───────────────────────────────────

@router.post("/note", response_model=DocumentResponse)
async def create_note(title: str, content: str, collection_id: str | None = None):
    """Create a note from manually entered text."""
    settings = get_settings()
    doc_id = str(uuid.uuid4())

    # Save note as a text file
    save_dir = os.path.join(settings.documents_dir, doc_id)
    os.makedirs(save_dir, exist_ok=True)
    file_path = os.path.join(save_dir, f"{title}.txt")

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    file_size = os.path.getsize(file_path)

    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _get_rag_pipeline().ingest_document(
            file_path=file_path,
            filename=f"{title}.txt",
            file_type="note",
            file_size=file_size,
            collection_id=collection_id,
        ),
    )

    if result["status"] == "error":
        raise HTTPException(status_code=422, detail=result.get("error", "处理失败"))

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=?", (result["doc_id"],)
        ).fetchone()
        return _row_to_response(row, conn=conn)
    finally:
        conn.close()


# ── List ───────────────────────────────────────────────────

@router.get("", response_model=DocumentListResponse)
async def list_documents(collection_id: str | None = None):
    """List all uploaded documents, optionally filtered by collection."""
    conn = get_connection()
    try:
        if collection_id:
            rows = conn.execute(
                "SELECT * FROM documents WHERE collection_id=? ORDER BY created_at DESC",
                (collection_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents ORDER BY created_at DESC"
            ).fetchall()
        return DocumentListResponse(
            documents=[_row_to_response(r, conn=conn) for r in rows]
        )
    finally:
        conn.close()


# ── Get chunks ─────────────────────────────────────────────

@router.get("/{doc_id}/chunks", response_model=list[ChunkResponse])
async def get_document_chunks(doc_id: str):
    """List all chunks for a document."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chunks WHERE doc_id=? ORDER BY chunk_index",
            (doc_id,),
        ).fetchall()
        return [
            ChunkResponse(
                chunk_id=r["id"],
                text_preview=r["text"][:150] + ("..." if len(r["text"]) > 150 else ""),
                page_num=r["page_num"],
                heading=r["heading"],
                chunk_index=r["chunk_index"],
            )
            for r in rows
        ]
    finally:
        conn.close()


# ── Delete ─────────────────────────────────────────────────

@router.delete("/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document and all associated data."""
    import asyncio
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: _get_rag_pipeline().delete_document(doc_id),
    )

    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "删除失败"))

    return {"success": True, "chunks_deleted": result.get("chunks_deleted", 0)}


# ── Helpers ────────────────────────────────────────────────

def _row_to_response(row, conn=None) -> DocumentResponse:
    """Convert a database row to DocumentResponse, optionally fetching tags and collection."""
    tags = []
    collection_name = None
    if conn:
        tag_rows = conn.execute(
            """SELECT t.name FROM tags t
               JOIN document_tags dt ON dt.tag_id = t.id
               WHERE dt.doc_id = ?""",
            (row["id"],),
        ).fetchall()
        tags = [t["name"] for t in tag_rows]

        # Fetch collection name
        if row["collection_id"]:
            coll = conn.execute(
                "SELECT name FROM collections WHERE id=?", (row["collection_id"],)
            ).fetchone()
            if coll:
                collection_name = coll["name"]

    return DocumentResponse(
        id=row["id"],
        filename=row["filename"],
        file_type=row["file_type"],
        file_size=row["file_size"],
        chunk_count=row["chunk_count"],
        status=row["status"],
        error_message=row["error_message"],
        tags=tags,
        collection_id=row["collection_id"],
        collection_name=collection_name,
        created_at=str(row["created_at"]),
    )


# ── Tags ──────────────────────────────────────────────────

@router.post("/{doc_id}/tags")
async def add_tag(doc_id: str, request: TagAssignRequest):
    """Add a tag to a document."""
    conn = get_connection()
    try:
        # Verify document exists
        doc = conn.execute("SELECT id FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        # Get or create tag
        tag = conn.execute("SELECT id FROM tags WHERE name=?", (request.tag_name,)).fetchone()
        if not tag:
            tag_id = str(uuid.uuid4())
            conn.execute("INSERT INTO tags (id, name) VALUES (?, ?)", (tag_id, request.tag_name))
        else:
            tag_id = tag["id"]

        # Link tag to document (ignore if already linked)
        try:
            conn.execute(
                "INSERT INTO document_tags (doc_id, tag_id) VALUES (?, ?)",
                (doc_id, tag_id),
            )
            conn.commit()
        except Exception:
            pass  # Already linked

        return {"success": True, "tag": request.tag_name}
    finally:
        conn.close()


@router.delete("/{doc_id}/tags/{tag_name}")
async def remove_tag(doc_id: str, tag_name: str):
    """Remove a tag from a document."""
    conn = get_connection()
    try:
        tag = conn.execute("SELECT id FROM tags WHERE name=?", (tag_name,)).fetchone()
        if tag:
            conn.execute(
                "DELETE FROM document_tags WHERE doc_id=? AND tag_id=?",
                (doc_id, tag["id"]),
            )
            conn.commit()
        return {"success": True}
    finally:
        conn.close()


@router.get("/tags/all")
async def list_all_tags():
    """List all available tags with document counts."""
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT t.id, t.name, COUNT(dt.doc_id) as doc_count
               FROM tags t
               LEFT JOIN document_tags dt ON dt.tag_id = t.id
               GROUP BY t.id
               ORDER BY t.name"""
        ).fetchall()
        return [{"id": r["id"], "name": r["name"], "doc_count": r["doc_count"]} for r in rows]
    finally:
        conn.close()


# ── Summary ───────────────────────────────────────────────

@router.post("/{doc_id}/summary")
async def generate_summary(doc_id: str):
    """Generate a summary of a document using LLM."""
    pipeline = _get_rag_pipeline()
    conn = get_connection()

    try:
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        if doc["status"] != "ready":
            raise HTTPException(status_code=400, detail="文档尚未处理完成，无法生成摘要")

        # Get all chunks for this document
        chunks = conn.execute(
            "SELECT text FROM chunks WHERE doc_id=? ORDER BY chunk_index", (doc_id,),
        ).fetchall()
        if not chunks:
            raise HTTPException(status_code=400, detail="文档没有可总结的内容")

        # Build summary text from chunks (limit to first ~3000 chars to stay in token budget)
        full_text = "\n\n".join(c["text"] for c in chunks)[:3000]
    finally:
        conn.close()

    # Call LLM for summary
    try:
        response = await pipeline.generator.client.chat.completions.create(
            model=pipeline.generator.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一个学习助手。请为以下学习资料生成一份简洁的核心要点摘要。"
                        "要求：用中文，列出 3-7 个核心要点，每个要点 1-2 句话。"
                    ),
                },
                {"role": "user", "content": f"文档名：{doc['filename']}\n\n{full_text}"},
            ],
            temperature=0.3,
        )
        summary_text = response.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"摘要生成失败: {e}")

    from app.models.schemas import SummaryResponse
    return SummaryResponse(
        doc_id=doc_id,
        filename=doc["filename"],
        summary=summary_text,
    )


# ── Images ─────────────────────────────────────────────────

@router.get("/{doc_id}/images")
async def get_document_images(doc_id: str):
    """Get all extracted images for a document."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM chunk_images WHERE doc_id=? ORDER BY page_num",
            (doc_id,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "chunk_id": r["chunk_id"],
                "image_type": r["image_type"],
                "page_num": r["page_num"],
                "width": r["width"],
                "height": r["height"],
            }
            for r in rows
        ]
    finally:
        conn.close()


@router.get("/images/{image_id}/file")
async def get_image_file(image_id: str):
    """Serve an extracted image file."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT image_path FROM chunk_images WHERE id=?", (image_id,)
        ).fetchone()
        if not row or not os.path.exists(row["image_path"]):
            raise HTTPException(status_code=404, detail="图片不存在")
        return FileResponse(row["image_path"])
    finally:
        conn.close()
