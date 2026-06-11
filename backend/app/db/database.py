"""SQLite database initialization and connection management."""

import sqlite3
from pathlib import Path


_db_path: str | None = None


def init_db(db_path: str) -> None:
    """Create all tables if they don't exist."""
    global _db_path
    _db_path = db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA_SQL)
    conn.commit()

    # Migration: add collection_id to documents if not exists
    try:
        conn.execute("ALTER TABLE documents ADD COLUMN collection_id TEXT REFERENCES collections(id)")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    # Migration: populate FTS from existing messages
    try:
        conn.execute("INSERT INTO chat_messages_fts(chat_messages_fts) VALUES('rebuild')")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # FTS already populated or table just created

    conn.close()


def get_connection() -> sqlite3.Connection:
    """Return a new connection (caller must close / use as context manager)."""
    if _db_path is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ── Schema ─────────────────────────────────────────────────

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS collections (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    description   TEXT,
    doc_count     INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,
    filename      TEXT NOT NULL,
    file_type     TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    file_size     INTEGER NOT NULL,
    chunk_count   INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'processing',
    error_message TEXT,
    collection_id TEXT REFERENCES collections(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chunks (
    id            TEXT PRIMARY KEY,
    doc_id        TEXT NOT NULL REFERENCES documents(id),
    chunk_index   INTEGER NOT NULL,
    text          TEXT NOT NULL,
    page_num      INTEGER,
    heading       TEXT,
    token_count   INTEGER NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id);

-- 标签表
CREATE TABLE IF NOT EXISTS tags (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL UNIQUE,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 文档-标签关联表
CREATE TABLE IF NOT EXISTS document_tags (
    doc_id        TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    tag_id        TEXT NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (doc_id, tag_id)
);

CREATE TABLE IF NOT EXISTS chat_sessions (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES chat_sessions(id),
    role          TEXT NOT NULL,
    content       TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id);

CREATE TABLE IF NOT EXISTS citations (
    id            TEXT PRIMARY KEY,
    message_id    TEXT NOT NULL REFERENCES chat_messages(id),
    doc_id        TEXT NOT NULL REFERENCES documents(id),
    chunk_id      TEXT NOT NULL REFERENCES chunks(id),
    doc_name      TEXT NOT NULL,
    page_num      INTEGER,
    chunk_index   INTEGER NOT NULL,
    text_preview  TEXT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_citations_message ON citations(message_id);

-- 测验表（Phase 3）
CREATE TABLE IF NOT EXISTS quizzes (
    id            TEXT PRIMARY KEY,
    topic         TEXT,
    doc_ids       TEXT,                        -- JSON: list of doc IDs used
    tag           TEXT,
    total_count   INTEGER NOT NULL,
    correct_count INTEGER DEFAULT 0,
    status        TEXT DEFAULT 'active',       -- 'active' | 'completed'
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 测验题目表（Phase 3）
CREATE TABLE IF NOT EXISTS quiz_questions (
    id             TEXT PRIMARY KEY,
    quiz_id        TEXT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_type  TEXT NOT NULL,              -- 'choice' | 'true_false'
    question_text  TEXT NOT NULL,
    options        TEXT,                       -- JSON: option list (for choice)
    correct_answer TEXT NOT NULL,
    explanation    TEXT,
    source_chunk_id TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_quiz_questions_quiz ON quiz_questions(quiz_id);

-- 用户答题记录（Phase 3）
CREATE TABLE IF NOT EXISTS quiz_answers (
    id             TEXT PRIMARY KEY,
    quiz_id        TEXT NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    question_id    TEXT NOT NULL REFERENCES quiz_questions(id) ON DELETE CASCADE,
    user_answer    TEXT NOT NULL,
    is_correct     INTEGER NOT NULL,           -- 0 or 1
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 错题表（Phase 3）
CREATE TABLE IF NOT EXISTS wrong_answers (
    id             TEXT PRIMARY KEY,
    question_id    TEXT NOT NULL REFERENCES quiz_questions(id),
    quiz_id        TEXT NOT NULL REFERENCES quizzes(id),
    question_text  TEXT NOT NULL,
    question_type  TEXT NOT NULL,
    options        TEXT,
    correct_answer TEXT NOT NULL,
    explanation    TEXT,
    user_answer    TEXT NOT NULL,
    review_count   INTEGER DEFAULT 0,
    mastery_level  INTEGER DEFAULT 0,          -- 0-5
    last_reviewed  TIMESTAMP,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 知识点表（Phase 3）
CREATE TABLE IF NOT EXISTS knowledge_points (
    id             TEXT PRIMARY KEY,
    doc_id         TEXT,
    tag            TEXT,
    name           TEXT NOT NULL,
    description    TEXT,
    mastery_score  REAL DEFAULT 0.0,           -- 0.0-1.0
    quiz_count     INTEGER DEFAULT 0,
    correct_count  INTEGER DEFAULT 0,
    next_review    TIMESTAMP,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chunk 质量评分（Phase 4）
CREATE TABLE IF NOT EXISTS chunk_quality (
    chunk_id      TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    info_density  REAL DEFAULT 0.5,
    is_low_quality INTEGER DEFAULT 0,
    reason        TEXT,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PDF 提取的图片/表格（Phase 4）
CREATE TABLE IF NOT EXISTS chunk_images (
    id            TEXT PRIMARY KEY,
    chunk_id      TEXT NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    doc_id        TEXT NOT NULL,
    image_path    TEXT NOT NULL,
    image_type    TEXT DEFAULT 'image',
    page_num      INTEGER,
    width         INTEGER,
    height        INTEGER,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_chunk_images_chunk ON chunk_images(chunk_id);

-- FTS5 全文搜索索引（Phase 4）
CREATE VIRTUAL TABLE IF NOT EXISTS chat_messages_fts USING fts5(
    content,
    content='chat_messages',
    content_rowid='rowid'
);

-- Trigger to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS chat_messages_ai AFTER INSERT ON chat_messages BEGIN
    INSERT INTO chat_messages_fts(rowid, content) VALUES (new.rowid, new.content);
END;

-- 概念表（Phase 5 知识图谱）
CREATE TABLE IF NOT EXISTS concepts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    description TEXT,
    doc_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 概念关系表（Phase 5 知识图谱）
CREATE TABLE IF NOT EXISTS concept_relations (
    id TEXT PRIMARY KEY,
    source_concept_id TEXT NOT NULL REFERENCES concepts(id),
    target_concept_id TEXT NOT NULL REFERENCES concepts(id),
    relation_type TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    doc_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_concept_id, target_concept_id, relation_type)
);
CREATE INDEX IF NOT EXISTS idx_relations_source ON concept_relations(source_concept_id);
CREATE INDEX IF NOT EXISTS idx_relations_target ON concept_relations(target_concept_id);
"""
