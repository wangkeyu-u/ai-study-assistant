"""Tests for multilingual RAG language routing."""

from app.db.database import get_connection
from app.services.language import (
    answer_language_instruction,
    detect_corpus_languages,
    detect_text_language,
    resolve_answer_language,
    translation_targets,
)


def test_detect_text_language_handles_chinese_english_and_mixed():
    assert detect_text_language("检索增强生成可以减少幻觉。") == "zh"
    assert detect_text_language("Retrieval augmented generation grounds model answers.") == "en"
    assert detect_text_language("RAG 使用 vector search 进行检索") == "mixed"


def test_translation_targets_follow_active_corpus_language():
    assert translation_targets("zh", ["en"]) == ["en"]
    assert translation_targets("en", ["zh", "en"]) == ["zh"]
    assert translation_targets("zh", ["zh"]) == []


def test_detect_corpus_languages_respects_indexed_chunks(tmp_db):
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO documents
               (id, filename, file_type, file_path, file_size, status)
               VALUES ('doc-en', 'guide.md', 'md', '/tmp/guide.md', 100, 'ready')"""
        )
        conn.execute(
            """INSERT INTO chunks
               (id, doc_id, chunk_index, text, token_count)
               VALUES ('chunk-en', 'doc-en', 0, 'Vector search retrieves semantic evidence.', 8)"""
        )
        conn.commit()

    assert detect_corpus_languages(document_ids=["doc-en"]) == ["en"]


def test_answer_language_can_differ_from_question_language():
    assert resolve_answer_language("en", "这个概念是什么？") == "en"
    assert resolve_answer_language("zh", "What is this concept?") == "zh"
    assert "entirely in English" in answer_language_instruction("en", "中文问题")
