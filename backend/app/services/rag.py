"""RAG pipeline orchestrator — ties together parse → chunk → embed → store and query → retrieve → generate.

This module is the central coordination point for all RAG operations. It composes
the individual service modules (parser, chunker, embedder, vectorstore, retriever,
generator) into two main pipelines:

1. **Ingest Pipeline** (document upload):
   parse → chunk → embed → store (ChromaDB + SQLite)

2. **Query Pipeline** (user question):
   rewrite (optional) → embed → retrieve → generate → cite

The orchestrator also handles:
- Error recovery at each pipeline stage
- Debug info collection for the Debug Panel
- Document deletion with transactional consistency

Data Flow:
    User uploads file → Router calls ingest_document()
        → Parser extracts text (PDF/TXT/MD)
        → Chunker splits into ~512 token chunks with overlap
        → Embedder generates vectors for each chunk
        → VectorStore saves to ChromaDB (ANN index)
        → SQLite saves metadata (doc info, chunk text, relationships)

    User asks question → Router calls query()
        → Generator.rewrite_query() if multi-turn context exists
        → Embedder embeds the (rewritten) query
        → Retriever finds top-K similar chunks, filters by threshold
        → Generator builds prompt with context + history → LLM generates answer
        → Citation marks [N] are extracted and mapped back to chunks
        → DebugInfo is collected (scores, tokens, timing)
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from app.config import get_settings
from app.db.database import get_db
from app.models.schemas import DebugInfo, RetrievedChunkInfo, TokenUsage
from app.services.chunker import TextChunker
from app.services.context_expander import expand_chunk_neighbors
from app.services.context_optimizer import optimize_context_chunks
from app.services.embedder import BaseEmbedder
from app.services.generator import GenerationResult, Generator
from app.services.image_extractor import extract_pdf_images
from app.services.language import (
    AnswerLanguage,
    detect_corpus_languages,
    detect_text_language,
    resolve_answer_language,
    translation_targets,
)
from app.services.parser import DocumentParser
from app.services.quality import batch_score_chunks
from app.services.query_intelligence import analyze_query, build_response_instructions
from app.services.query_planner import retrieve_with_query_plan
from app.services.reranker import CrossEncoderReranker
from app.services.retriever import Retriever
from app.services.vectorstore import VectorStore

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Central orchestrator for all RAG operations.

    Composes individual services into two pipelines:
    - ingest_document(): parse → chunk → embed → store
    - query(): rewrite → embed → retrieve → generate
    - delete_document(): chroma → sqlite → file (transactional)

    Dependencies are injected via constructor (embedder, vector_store, generator)
    to support different providers (OpenAI vs local, Ollama vs OpenAI API).
    """

    def __init__(self, embedder: BaseEmbedder, vector_store: VectorStore, generator: Generator):
        self.embedder = embedder
        self.vector_store = vector_store
        self.generator = generator
        self.parser = DocumentParser()
        self.settings = get_settings()
        self.reranker = (
            CrossEncoderReranker(self.settings.reranker_model)
            if self.settings.reranker_enabled
            else None
        )
        self.chunker = TextChunker(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        # Store last debug info for the /debug endpoint
        self.last_debug_info: DebugInfo | None = None

    # ── Document Ingestion ─────────────────────────────────

    def ingest_document(
        self,
        file_path: str,
        filename: str,
        file_type: str,
        file_size: int,
        collection_id: str | None = None,
    ) -> dict:
        """Full ingestion pipeline: parse → chunk → embed → store.

        Returns dict with doc_id, chunk_count, status.
        """
        doc_id = str(uuid.uuid4())
        settings = self.settings

        # Record document in SQLite
        try:
            with get_db() as conn:
                conn.execute(
                    """INSERT INTO documents (id, filename, file_type, file_path, file_size, status, collection_id)
                       VALUES (?, ?, ?, ?, ?, 'processing', ?)""",
                    (doc_id, filename, file_type, file_path, file_size, collection_id),
                )
                conn.commit()

                # Step 1: Parse
                logger.info("Parsing document: %s", filename)
                parse_result = self.parser.parse(file_path, file_type)
                if parse_result.error:
                    conn.execute(
                        "UPDATE documents SET status='error', error_message=? WHERE id=?",
                        (parse_result.error, doc_id),
                    )
                    conn.commit()
                    return {"doc_id": doc_id, "status": "error", "error": parse_result.error}

                # Step 2: Chunk
                logger.info("Chunking document: %s", filename)
                chunks = self.chunker.chunk_segments(parse_result.segments)
                if not chunks:
                    conn.execute(
                        "UPDATE documents SET status='error', error_message='文档内容无法分块' WHERE id=?",
                        (doc_id,),
                    )
                    conn.commit()
                    return {"doc_id": doc_id, "status": "error", "error": "文档内容无法分块"}

                # Step 3: Embed
                logger.info("Generating embeddings for %d chunks", len(chunks))
                chunk_texts = [c.text for c in chunks]
                embeddings = self.embedder.embed([c.embedding_text for c in chunks])

                # Step 4: Store in ChromaDB
                chunk_ids = [str(uuid.uuid4()) for _ in chunks]
                metadatas = [
                    {
                        "doc_id": doc_id,
                        "doc_name": filename,
                        "chunk_index": c.chunk_index,
                        "page_num": c.page_num if c.page_num is not None else 0,
                        "heading": c.heading or "",
                        "collection_id": collection_id or "",
                    }
                    for c in chunks
                ]

                self.vector_store.add_chunks(
                    chunk_ids=chunk_ids,
                    embeddings=embeddings,
                    texts=chunk_texts,
                    metadatas=metadatas,
                )

                # Step 5: Store chunk metadata in SQLite
                for i, chunk in enumerate(chunks):
                    conn.execute(
                        """INSERT INTO chunks (id, doc_id, chunk_index, text, page_num, heading, token_count)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            chunk_ids[i],
                            doc_id,
                            chunk.chunk_index,
                            chunk.text,
                            chunk.page_num,
                            chunk.heading,
                            chunk.token_count,
                        ),
                    )

                # Step 6: Score chunk quality
                logger.info("Scoring quality for %d chunks", len(chunks))
                quality_scores = batch_score_chunks([c.text for c in chunks])
                for i, (_chunk, score) in enumerate(zip(chunks, quality_scores, strict=True)):
                    conn.execute(
                        """INSERT OR REPLACE INTO chunk_quality (chunk_id, info_density, is_low_quality, reason)
                           VALUES (?, ?, ?, ?)""",
                        (
                            chunk_ids[i],
                            score["info_density"],
                            1 if score["is_low_quality"] else 0,
                            score["reason"],
                        ),
                    )
                low_quality_count = sum(1 for s in quality_scores if s["is_low_quality"])
                if low_quality_count > 0:
                    logger.info(
                        "Found %d low-quality chunks (will be deprioritized in search)",
                        low_quality_count,
                    )

                # Step 7: Extract PDF images (Phase 4)
                if file_type == "pdf":
                    try:
                        images_dir = os.path.join(settings.app_data_dir, "data", "chunk_images")
                        extracted_images = extract_pdf_images(file_path, images_dir, doc_id)
                        for img in extracted_images:
                            # Link image to the closest chunk by page number
                            matching_chunk_idx = None
                            for i, c in enumerate(chunks):
                                if c.page_num and c.page_num >= img["page_num"]:
                                    matching_chunk_idx = i
                                    break
                            chunk_id_for_img = (
                                chunk_ids[matching_chunk_idx]
                                if matching_chunk_idx is not None
                                else chunk_ids[0]
                            )
                            conn.execute(
                                """INSERT INTO chunk_images (id, chunk_id, doc_id, image_path, image_type, page_num, width, height)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                                (
                                    img["id"],
                                    chunk_id_for_img,
                                    doc_id,
                                    img["image_path"],
                                    img["image_type"],
                                    img["page_num"],
                                    img["width"],
                                    img["height"],
                                ),
                            )
                        if extracted_images:
                            logger.info("Linked %d images to chunks", len(extracted_images))
                    except Exception as e:
                        logger.warning("Image extraction failed (non-critical): %s", e)

                # Update document status
                conn.execute(
                    "UPDATE documents SET status='ready', chunk_count=? WHERE id=?",
                    (len(chunks), doc_id),
                )

                # Update collection doc_count if applicable
                if collection_id:
                    conn.execute(
                        "UPDATE collections SET doc_count = doc_count + 1 WHERE id=?",
                        (collection_id,),
                    )

                conn.commit()

                logger.info("Document ingested: %s (%d chunks)", filename, len(chunks))
                return {"doc_id": doc_id, "status": "ready", "chunk_count": len(chunks)}

        except Exception as e:
            logger.exception("Ingestion failed for %s", filename)
            try:
                with get_db() as conn:
                    conn.execute(
                        "UPDATE documents SET status='error', error_message=? WHERE id=?",
                        (str(e), doc_id),
                    )
                    conn.commit()
            except Exception as inner_e:
                logger.warning("Failed to update document status to 'error': %s", inner_e)
            return {"doc_id": doc_id, "status": "error", "error": str(e)}

    def reindex_document(self, doc_id: str) -> dict:
        """Rebuild active chunks while retaining old rows for historical citations."""
        with get_db() as conn:
            document = conn.execute("SELECT * FROM documents WHERE id=?", (doc_id,)).fetchone()
            if not document:
                return {"success": False, "error": "Document not found"}
            old_chunk_ids = [
                row["id"]
                for row in conn.execute(
                    "SELECT id FROM chunks WHERE doc_id=? AND is_active=1",
                    (doc_id,),
                ).fetchall()
            ]

        parse_result = self.parser.parse(document["file_path"], document["file_type"])
        if parse_result.error:
            return {"success": False, "error": parse_result.error}
        chunks = self.chunker.chunk_segments(parse_result.segments)
        if not chunks:
            return {"success": False, "error": "文档内容无法分块"}

        chunk_ids = [str(uuid.uuid4()) for _ in chunks]
        embeddings = self.embedder.embed([chunk.embedding_text for chunk in chunks])
        chunk_texts = [chunk.text for chunk in chunks]
        metadatas = [
            {
                "doc_id": doc_id,
                "doc_name": document["filename"],
                "chunk_index": chunk.chunk_index,
                "page_num": chunk.page_num if chunk.page_num is not None else 0,
                "heading": chunk.heading or "",
                "collection_id": document["collection_id"] or "",
            }
            for chunk in chunks
        ]
        quality_scores = batch_score_chunks(chunk_texts)

        try:
            self.vector_store.add_chunks(
                chunk_ids=chunk_ids,
                embeddings=embeddings,
                texts=chunk_texts,
                metadatas=metadatas,
            )
            with get_db() as conn:
                conn.execute(
                    "UPDATE chunks SET is_active=0 WHERE doc_id=? AND is_active=1",
                    (doc_id,),
                )
                for chunk_id, chunk, quality in zip(
                    chunk_ids,
                    chunks,
                    quality_scores,
                    strict=True,
                ):
                    conn.execute(
                        """INSERT INTO chunks
                           (id, doc_id, chunk_index, text, page_num, heading,
                            token_count, is_active)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 1)""",
                        (
                            chunk_id,
                            doc_id,
                            chunk.chunk_index,
                            chunk.text,
                            chunk.page_num,
                            chunk.heading,
                            chunk.token_count,
                        ),
                    )
                    conn.execute(
                        """INSERT INTO chunk_quality
                           (chunk_id, info_density, is_low_quality, reason)
                           VALUES (?, ?, ?, ?)""",
                        (
                            chunk_id,
                            quality["info_density"],
                            1 if quality["is_low_quality"] else 0,
                            quality["reason"],
                        ),
                    )
                conn.execute(
                    """UPDATE documents
                       SET chunk_count=?, status='ready', error_message=NULL
                       WHERE id=?""",
                    (len(chunks), doc_id),
                )
                conn.commit()
        except Exception as error:
            self.vector_store.delete_chunks(chunk_ids)
            logger.exception("Re-index failed for document %s", doc_id)
            return {"success": False, "error": str(error)}

        removed_vectors = self.vector_store.delete_chunks(old_chunk_ids)
        logger.info(
            "Re-indexed document %s: %d -> %d active chunks",
            doc_id,
            len(old_chunk_ids),
            len(chunks),
        )
        return {
            "success": True,
            "doc_id": doc_id,
            "chunk_count": len(chunks),
            "old_vectors_removed": removed_vectors,
        }

    # ── Query ──────────────────────────────────────────────

    async def query(
        self,
        question: str,
        history: list[dict] | None = None,
        collection_id: str | None = None,
        document_ids: list[str] | None = None,
        answer_language: AnswerLanguage = "auto",
    ) -> tuple[GenerationResult, DebugInfo]:
        """Full query pipeline: rewrite → embed → retrieve → generate.

        This is the core RAG query flow, called by the chat endpoint for each
        user message. It handles:
        1. Query rewriting for multi-turn conversations (optional)
        2. Vector retrieval from ChromaDB
        3. LLM generation with context and history
        4. Debug info collection for the Debug Panel

        Args:
            question: User's raw question text.
            history: Conversation history as [{"role": "user"/"assistant", "content": "..."}].
                     Used for both query rewriting and multi-turn prompt context.
            collection_id: Optional collection ID to restrict search to a knowledge base.
            document_ids: Optional document IDs to restrict retrieval for focused Q&A or comparison.

        Returns:
            Tuple of (GenerationResult with answer + citations, DebugInfo for Debug Panel).

        Design Notes:
            - Query rewrite only triggers when history has ≥2 messages (at least 1 turn).
              This avoids unnecessary LLM calls for the first question in a session.
            - The rewritten query is used for RETRIEVAL but the ORIGINAL question is
              passed to the generator. This way the LLM sees the user's exact words
              while retrieval benefits from a more complete query.
            - Debug info includes the full prompt sent to the LLM, which is critical
              for debugging retrieval quality and prompt engineering.
        """
        settings = self.settings
        query_profile = analyze_query(question)
        query_language = detect_text_language(question)
        corpus_languages = detect_corpus_languages(collection_id, document_ids)

        # ── Step 0: Query Rewrite ──────────────────────────────
        # Purpose: Convert context-dependent queries ("那第二章呢？") into
        # self-contained queries ("第二章中关于XX的内容是什么？")
        # This improves retrieval accuracy for multi-turn conversations.
        # Only triggers when there's enough history to understand context.
        rewritten_query = question
        if history and len(history) >= 2:
            rewritten_query = await self.generator.rewrite_query(question, history)
            # Log rewrite for debugging: "那第二章呢？" → "第二章中关于RAG流程的描述"
            if rewritten_query != question:
                logger.info("Query rewritten: '%s' → '%s'", question[:50], rewritten_query[:50])

        # ── Step 1: Hybrid Retrieval ──────────────────────────
        # Uses the REWRITTEN query for better retrieval results.
        # The retriever handles: embed query → ChromaDB search → threshold filter.
        # Returns chunks sorted by similarity score (highest first).
        retriever = Retriever(
            vector_store=self.vector_store,
            embedder=self.embedder,
            top_k=max(settings.top_k, settings.context_candidate_top_k),
            similarity_threshold=settings.similarity_threshold,  # default: 0.3
            hybrid_search_enabled=settings.hybrid_search_enabled,
            candidate_multiplier=settings.retrieval_candidate_multiplier,
            rrf_k=settings.rrf_k,
            confidence_gate_enabled=settings.retrieval_confidence_gate_enabled,
            vector_only_min_score=settings.vector_only_min_score,
            reranker=self.reranker,
            rerank_top_n=settings.reranker_top_n,
        )
        translated_queries: list[str] = []
        if settings.cross_language_retrieval_enabled:
            for target_language in translation_targets(query_language, corpus_languages):
                translated = await self.generator.translate_query_for_retrieval(
                    rewritten_query,
                    target_language,
                )
                if translated != rewritten_query and translated not in translated_queries:
                    translated_queries.append(translated)

        retrieval_queries = [rewritten_query, *translated_queries]
        if settings.query_decomposition_enabled:
            retrieval_result, retrieval_queries = retrieve_with_query_plan(
                retriever,
                rewritten_query,
                collection_id=collection_id,
                document_ids=document_ids,
                max_subqueries=settings.query_decomposition_max_subqueries,
                additional_queries=translated_queries,
            )
        else:
            retrieval_result, retrieval_queries = retrieve_with_query_plan(
                retriever,
                rewritten_query,
                collection_id=collection_id,
                document_ids=document_ids,
                max_subqueries=0,
                additional_queries=translated_queries,
            )

        # HyDE is a guarded fallback, not trusted evidence. It only proposes a
        # semantic search passage when ordinary and translated retrieval fail.
        if settings.hyde_fallback_enabled and corpus_languages and not retrieval_result.chunks:
            hyde_language = (
                "en"
                if "en" in translation_targets(query_language, corpus_languages)
                else "zh"
                if query_language != "en"
                else "en"
            )
            hypothetical_passage = await self.generator.generate_hypothetical_passage(
                rewritten_query,
                hyde_language,
            )
            if hypothetical_passage:
                retrieval_result, retrieval_queries = retrieve_with_query_plan(
                    retriever,
                    rewritten_query,
                    collection_id=collection_id,
                    document_ids=document_ids,
                    max_subqueries=settings.query_decomposition_max_subqueries,
                    additional_queries=[*translated_queries, hypothetical_passage],
                )
                retrieval_result.mode = f"hyde_{retrieval_result.mode}"

        # If no chunks pass the threshold, generator will return a
        # "资料不足" message instead of hallucinating an answer.
        context_selection = optimize_context_chunks(
            rewritten_query,
            retrieval_result.chunks,
            profile=query_profile,
            max_chunks=settings.context_max_chunks,
            max_chars=settings.context_max_chars,
            document_ids=document_ids,
            diversity_lambda=settings.context_mmr_lambda,
            coverage_queries=[rewritten_query, *translated_queries],
        )
        generation_chunks = context_selection.chunks
        has_lexical_context = any(
            source in {"fts", "exact"}
            for chunk in generation_chunks
            for source in chunk.retrieval_sources
        )
        context_strategy = context_selection.strategy
        if (
            generation_chunks
            and not has_lexical_context
            and context_selection.coverage_score < settings.context_min_coverage_score
        ):
            logger.info(
                "Context coverage gate rejected query '%s' (coverage=%.4f)",
                question[:80],
                context_selection.coverage_score,
            )
            retrieval_result.confidence_rejected = True
            retrieval_result.rejection_reason = "context_coverage_below_threshold"
            generation_chunks = []
            context_strategy = f"{context_selection.strategy}:coverage_gate"

        if generation_chunks:
            generation_chunks = expand_chunk_neighbors(
                generation_chunks,
                window=settings.context_neighbor_window,
                max_neighbors=settings.context_max_neighbors,
                max_chunks=settings.context_max_chunks + settings.context_max_neighbors,
                max_chars=settings.context_max_chars,
            )
            if len(generation_chunks) > context_selection.selected_count:
                context_strategy = f"{context_strategy}:neighbors"

        # ── Step 2: LLM Generation ───────────────────────────
        # Uses the ORIGINAL question (not rewritten) so the LLM responds
        # to what the user actually asked. The rewritten query was only
        # for improving retrieval.
        # History is passed as additional context (last 10 messages = 5 turns).
        gen_start = time.time()
        response_instructions = (
            build_response_instructions(query_profile)
            if settings.intent_aware_prompt_enabled
            else None
        )
        generation_result = await self.generator.generate(
            query=question,  # original question for LLM
            chunks=generation_chunks,  # selected context
            history=history,  # multi-turn context
            response_instructions=response_instructions,
            answer_language=answer_language,
        )
        gen_elapsed = (time.time() - gen_start) * 1000
        generation_result.generation_time_ms = gen_elapsed

        # ── Step 3: Build Debug Info ─────────────────────────
        # Collected for the Debug Panel (toggle button in chat page).
        # Helps developers and users understand:
        # - What was actually searched (rewritten query vs original)
        # - How good the retrieval was (similarity scores)
        # - Token consumption and latency breakdown
        debug_info = DebugInfo(
            query=question,
            rewritten_query=rewritten_query if rewritten_query != question else None,
            retrieval_queries=retrieval_queries,
            query_intent=query_profile.intent,
            answer_style=query_profile.answer_style,
            query_keywords=query_profile.keywords,
            query_language=query_language,
            corpus_languages=corpus_languages,
            answer_language=resolve_answer_language(answer_language, question),
            embedding_model=settings.embedding_model,
            retrieval_mode=retrieval_result.mode,
            confidence_rejected=retrieval_result.confidence_rejected,
            confidence_score=retrieval_result.confidence_score,
            rejection_reason=retrieval_result.rejection_reason,
            context_strategy=context_strategy,
            context_chunks_before=context_selection.original_count,
            context_chunks_after=len(generation_chunks),
            context_coverage_score=round(context_selection.coverage_score, 4),
            top_k_chunks=[
                RetrievedChunkInfo(
                    chunk_id=c.chunk_id,
                    text_preview=c.text[:150],  # first 150 chars for preview
                    similarity_score=round(c.score, 4),
                    doc_name=c.doc_name,
                    page_num=c.page_num,
                    vector_score=(round(c.vector_score, 4) if c.vector_score is not None else None),
                    lexical_score=(
                        round(c.lexical_score, 4) if c.lexical_score is not None else None
                    ),
                    rerank_score=(round(c.rerank_score, 4) if c.rerank_score is not None else None),
                    retrieval_sources=c.retrieval_sources,
                )
                for c in generation_chunks
            ],
            final_prompt=generation_result.final_prompt,  # full prompt for debugging
            token_usage=TokenUsage(
                prompt_tokens=generation_result.prompt_tokens,
                completion_tokens=generation_result.completion_tokens,
                total_tokens=generation_result.total_tokens,
            ),
            retrieval_time_ms=round(retrieval_result.retrieval_time_ms, 2),
            generation_time_ms=round(generation_result.generation_time_ms, 2),
        )

        self.last_debug_info = debug_info
        return generation_result, debug_info

    # ── Delete ─────────────────────────────────────────────

    def delete_document(self, doc_id: str) -> dict:
        """Delete a document and all associated data (vectors + metadata + file)."""
        with get_db() as conn:
            try:
                # Get document info
                row = conn.execute(
                    "SELECT file_path, filename FROM documents WHERE id=?", (doc_id,)
                ).fetchone()
                if not row:
                    return {"success": False, "error": "Document not found"}

                file_path = row["file_path"]
                filename = row["filename"]

                # Step 1: Delete from ChromaDB
                chunks_deleted = self.vector_store.delete_by_doc_id(doc_id)

                # Step 2: Delete from SQLite
                # citations.chunk_id → chunks.id → chunks.doc_id (documents has no session_id)
                conn.execute(
                    "DELETE FROM citations WHERE chunk_id IN (SELECT id FROM chunks WHERE doc_id=?)",
                    (doc_id,),
                )
                conn.execute("DELETE FROM chunks WHERE doc_id=?", (doc_id,))
                conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
                conn.commit()

                # Step 3: Delete local file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except OSError as e:
                    logger.warning("Could not delete file %s: %s", file_path, e)

                logger.info("Deleted document: %s (%d chunks removed)", filename, chunks_deleted)
                return {"success": True, "chunks_deleted": chunks_deleted}

            except Exception as e:
                conn.rollback()
                logger.exception("Failed to delete document %s", doc_id)
                return {"success": False, "error": str(e)}
