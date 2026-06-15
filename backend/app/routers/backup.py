"""Data backup, import, and markdown export routes."""

import io
import logging
import os
import posixpath
import tempfile
import zipfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.config import get_settings
from app.db.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/backup", tags=["backup"])

# Max backup size: 500 MB
MAX_BACKUP_SIZE = 500 * 1024 * 1024


def _validate_zip_entry(name: str, target_dir: str) -> str:
    """Validate a zip entry name to prevent path traversal attacks.

    Returns the resolved absolute path if safe, raises ValueError otherwise.
    """
    # Reject absolute paths
    if os.path.isabs(name):
        raise ValueError(f"Zip entry has absolute path: {name}")

    # Normalize and reject .. components
    normalized = posixpath.normpath(name)
    if normalized.startswith("..") or "/.." in normalized:
        raise ValueError(f"Zip entry contains path traversal: {name}")

    resolved = os.path.realpath(os.path.join(target_dir, normalized))
    target_real = os.path.realpath(target_dir)

    if not resolved.startswith(target_real + os.sep) and resolved != target_real:
        raise ValueError(f"Zip entry escapes target directory: {name}")

    return resolved


@router.post("/export")
async def export_backup():
    """Export complete data backup as a zip file."""
    settings = get_settings()
    data_dir = os.path.join(settings.app_data_dir, "data")

    # Checkpoint WAL to ensure all data is in the main database file
    db_path = os.path.join(data_dir, "app.db")
    if os.path.exists(db_path):
        try:
            with get_db() as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                logger.info("WAL checkpoint completed before backup export")
        except Exception as e:
            logger.warning("WAL checkpoint failed (non-critical): %s", e)

    # Write zip to a temp file (avoids buffering entire backup in memory)
    tmp = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add documents directory
            docs_dir = os.path.join(data_dir, "documents")
            if os.path.exists(docs_dir):
                for root, _dirs, files in os.walk(docs_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, settings.app_data_dir)
                        zf.write(file_path, arcname)

            # Add SQLite database
            if os.path.exists(db_path):
                zf.write(db_path, "data/app.db")
                # Also include WAL and SHM if they exist
                for suffix in ["-wal", "-shm"]:
                    wal_path = db_path + suffix
                    if os.path.exists(wal_path):
                        zf.write(wal_path, f"data/app.db{suffix}")

            # Add ChromaDB directory
            chroma_dir = os.path.join(data_dir, "chroma_db")
            if os.path.exists(chroma_dir):
                for root, _dirs, files in os.walk(chroma_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, settings.app_data_dir)
                        zf.write(file_path, arcname)

            # Add config if exists
            config_path = os.path.join(settings.app_data_dir, "config.json")
            if os.path.exists(config_path):
                zf.write(config_path, "config.json")

            # Add version info
            zf.writestr("backup_version.txt", "1.0")

        tmp.close()

        # Stream the temp file to the client
        def _iter_file(path: str, chunk_size: int = 1024 * 1024):
            try:
                with open(path, "rb") as fh:
                    while chunk := fh.read(chunk_size):
                        yield chunk
            finally:
                os.unlink(path)

        return StreamingResponse(
            _iter_file(tmp.name),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=ai-study-backup.zip"},
        )
    except Exception:
        # Clean up temp file on failure
        tmp.close()
        if os.path.exists(tmp.name):
            os.unlink(tmp.name)
        raise


@router.post("/import")
async def import_backup(file: UploadFile = File(...)):
    """Import and restore from a backup zip file.

    Security: Validates all zip entries to prevent path traversal attacks.
    Note: Server restart is required after import to pick up the restored database.
    """
    settings = get_settings()

    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="请上传 .zip 格式的备份文件")

    # Read the uploaded file with size limit
    content = await file.read()
    if len(content) > MAX_BACKUP_SIZE:
        raise HTTPException(
            status_code=400, detail=f"备份文件过大（最大 {MAX_BACKUP_SIZE // 1024 // 1024}MB）"
        )

    # Verify it's a valid backup and validate all entries
    try:
        buffer = io.BytesIO(content)
        with zipfile.ZipFile(buffer, "r") as zf:
            names = zf.namelist()
            if "backup_version.txt" not in names:
                raise HTTPException(status_code=400, detail="无效的备份文件格式（缺少版本标记）")

            # Validate ALL entries before extracting (path traversal protection)
            for name in names:
                try:
                    _validate_zip_entry(name, settings.app_data_dir)
                except ValueError as e:
                    raise HTTPException(
                        status_code=400,
                        detail=f"备份文件包含不安全的路径: {name}",
                    ) from e
    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail="备份文件已损坏，无法解压") from e

    # Extract to app data dir (overwrite)
    try:
        buffer.seek(0)
        with zipfile.ZipFile(buffer, "r") as zf:
            zf.extractall(settings.app_data_dir)

        # Count restored documents
        docs_dir = os.path.join(settings.app_data_dir, "data", "documents")
        doc_count = 0
        if os.path.exists(docs_dir):
            doc_count = len(
                [d for d in os.listdir(docs_dir) if os.path.isdir(os.path.join(docs_dir, d))]
            )

        logger.info("Backup imported: %d documents restored. Server restart required.", doc_count)
        return {
            "success": True,
            "documents_restored": doc_count,
            "warning": "需要重启服务才能使用恢复的数据库。",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {e}") from e


@router.post("/export-md/{message_id}")
async def export_message_as_markdown(message_id: str):
    """Export a chat message as a Markdown file with citations."""
    with get_db() as conn:
        # Fetch the message
        msg = conn.execute("SELECT * FROM chat_messages WHERE id=?", (message_id,)).fetchone()
        if not msg:
            raise HTTPException(status_code=404, detail="消息不存在")

        # Fetch citations
        citations = conn.execute(
            "SELECT * FROM citations WHERE message_id=? ORDER BY chunk_index",
            (message_id,),
        ).fetchall()

        # Fetch session title
        session = conn.execute(
            "SELECT title FROM chat_sessions WHERE id=?", (msg["session_id"],)
        ).fetchone()

        # Build markdown
        md_lines = []
        md_lines.append(f"# {session['title'] if session else '对话记录'}")
        md_lines.append("")
        md_lines.append(f"> 导出时间: {msg['created_at']}")
        md_lines.append(f"> 角色: {'用户' if msg['role'] == 'user' else 'AI 助手'}")
        md_lines.append("")
        md_lines.append("---")
        md_lines.append("")
        md_lines.append(msg["content"])
        md_lines.append("")

        if citations:
            md_lines.append("---")
            md_lines.append("")
            md_lines.append("## 引用来源")
            md_lines.append("")
            for i, c in enumerate(citations, 1):
                page_info = f"第 {c['page_num']} 页" if c["page_num"] else "未知页"
                md_lines.append(
                    f"[{i}] **{c['doc_name']}** — {page_info} (chunk #{c['chunk_index']})"
                )
                md_lines.append("")
                md_lines.append(f"> {c['text_preview']}")
                md_lines.append("")

        md_content = "\n".join(md_lines)

        # Return as downloadable file
        buffer = io.BytesIO(md_content.encode("utf-8"))
        filename = f"answer-{message_id[:8]}.md"
        return StreamingResponse(
            buffer,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
