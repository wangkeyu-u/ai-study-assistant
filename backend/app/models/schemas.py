"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from pydantic import BaseModel

# ── Document ───────────────────────────────────────────────


class DocumentResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str  # processing | ready | error
    error_message: str | None = None
    tags: list[str] = []  # tag names
    collection_id: str | None = None
    collection_name: str | None = None
    created_at: str


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]


class ChunkResponse(BaseModel):
    chunk_id: str
    text_preview: str
    page_num: int | None = None
    heading: str | None = None
    chunk_index: int


# ── Tags ───────────────────────────────────────────────────


class TagResponse(BaseModel):
    id: str
    name: str


class TagAssignRequest(BaseModel):
    tag_name: str


# ── Summary ────────────────────────────────────────────────


class SummaryResponse(BaseModel):
    doc_id: str
    filename: str
    summary: str


# ── Chat ───────────────────────────────────────────────────


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    collection_id: str | None = None


class CitationData(BaseModel):
    doc_name: str
    page_num: int | None = None
    chunk_id: str
    chunk_index: int
    text_preview: str


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str


class ChatMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: list[CitationData] = []
    created_at: str


# ── Debug ──────────────────────────────────────────────────


class RetrievedChunkInfo(BaseModel):
    chunk_id: str
    text_preview: str
    similarity_score: float
    doc_name: str
    page_num: int | None = None
    vector_score: float | None = None
    lexical_score: float | None = None
    rerank_score: float | None = None
    retrieval_sources: list[str] = []


class TokenUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class DebugInfo(BaseModel):
    query: str
    rewritten_query: str | None = None
    retrieval_queries: list[str] = []
    embedding_model: str
    retrieval_mode: str = "vector"
    confidence_rejected: bool = False
    confidence_score: float | None = None
    rejection_reason: str | None = None
    top_k_chunks: list[RetrievedChunkInfo]
    final_prompt: str
    token_usage: TokenUsage
    retrieval_time_ms: float
    generation_time_ms: float


# ── Collections ─────────────────────────────────────────────


class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    doc_count: int
    created_at: str


class CollectionAssignRequest(BaseModel):
    collection_id: str | None = None


# ── Quiz ──────────────────────────────────────────────────


class QuizGenerateRequest(BaseModel):
    doc_ids: list[str] | None = None
    tag: str | None = None
    count: int = 5  # number of questions


class QuizQuestionResponse(BaseModel):
    id: str
    question_type: str  # 'choice' | 'true_false'
    question_text: str
    options: list[str] | None = None
    correct_answer: str | None = None  # hidden until submission
    explanation: str | None = None


class QuizResponse(BaseModel):
    id: str
    topic: str | None = None
    total_count: int
    questions: list[QuizQuestionResponse]
    created_at: str


class QuizSubmitRequest(BaseModel):
    answers: list[dict]  # [{"question_id": "...", "user_answer": "..."}]


class QuizResultItem(BaseModel):
    question_id: str
    question_text: str
    user_answer: str
    correct_answer: str
    is_correct: bool
    explanation: str | None = None


class QuizResultResponse(BaseModel):
    quiz_id: str
    correct_count: int
    total_count: int
    results: list[QuizResultItem]


class WrongAnswerResponse(BaseModel):
    id: str
    question_text: str
    question_type: str
    options: list[str] | None = None
    correct_answer: str
    explanation: str | None = None
    user_answer: str
    review_count: int
    mastery_level: int
    created_at: str


class DashboardResponse(BaseModel):
    total_documents: int
    total_chunks: int
    total_questions_asked: int
    total_quizzes: int
    tag_stats: list[dict]
    weak_points: list[dict]
    recent_activity: list[dict]
