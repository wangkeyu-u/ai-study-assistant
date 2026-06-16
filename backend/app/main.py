"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import init_db
from app.routers import (
    backup as backup_router,
)
from app.routers import (
    chat,
    documents,
)
from app.routers import (
    collections as collections_router,
)
from app.routers import (
    knowledge_graph as knowledge_graph_router,
)
from app.routers import (
    multi_agent as multi_agent_router,
)
from app.routers import (
    quiz as quiz_router,
)
from app.routers import (
    settings as settings_router,
)
from app.services.embedder import create_embedder
from app.services.generator import Generator
from app.services.model_catalog import resolve_llm_client_config
from app.services.rag import RAGPipeline
from app.services.vectorstore import VectorStore

# ── Logging ────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Global state ───────────────────────────────────────────
rag_pipeline: RAGPipeline | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and teardown."""
    global rag_pipeline

    settings = get_settings()
    logger.info("Starting AI Study Assistant...")
    logger.info("Data dir: %s", settings.app_data_dir)

    # Initialize SQLite
    init_db(settings.db_path)
    logger.info("SQLite database initialized")

    # Initialize embedder
    logger.info(
        "Loading embedding model (provider=%s, model=%s)...",
        settings.embedding_provider,
        settings.embedding_model,
    )
    embed_kwargs = {"model": settings.embedding_model}
    if settings.embedding_provider == "openai":
        embed_kwargs["api_key"] = settings.openai_api_key
        if settings.openai_base_url:
            embed_kwargs["base_url"] = settings.openai_base_url
    embedder = create_embedder(settings.embedding_provider, **embed_kwargs)
    logger.info("Embedding model loaded")

    # Initialize vector store
    vector_store = VectorStore(
        persist_dir=settings.chroma_dir,
        embedding_dimension=settings.embedding_dimension,
    )
    logger.info("Vector store ready (%d vectors)", vector_store.count())

    # Initialize generator
    llm_config = resolve_llm_client_config(settings)
    generator = Generator(
        provider=llm_config["provider"] or "openai",
        model=llm_config["model"] or settings.llm_model,
        api_key=llm_config["api_key"] or "",
        base_url=llm_config["base_url"],
    )
    logger.info(
        "LLM generator ready (provider=%s, model=%s)", settings.llm_provider, settings.llm_model
    )

    # Initialize RAG pipeline
    rag_pipeline = RAGPipeline(
        embedder=embedder,
        vector_store=vector_store,
        generator=generator,
    )
    logger.info("RAG pipeline initialized. Server ready!")

    yield

    logger.info("Shutting down...")


# ── App ────────────────────────────────────────────────────
app = FastAPI(
    title="AI Study Assistant",
    description="本地优先的 RAG 学习助手 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(documents.router)
app.include_router(chat.router)
app.include_router(collections_router.router)
app.include_router(backup_router.router)
app.include_router(quiz_router.router)
app.include_router(knowledge_graph_router.router)
app.include_router(multi_agent_router.router)
app.include_router(settings_router.router)


# ── Debug endpoint ─────────────────────────────────────────


@app.get("/api/debug/last-query")
async def get_last_debug_info():
    """Return debug info from the last RAG query."""
    if rag_pipeline and rag_pipeline.last_debug_info:
        return rag_pipeline.last_debug_info.model_dump()
    return {"error": "还没有进行过查询"}


# ── Health check ───────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    """Basic health check."""
    settings = get_settings()
    vs = rag_pipeline.vector_store if rag_pipeline else None

    return {
        "status": "ok",
        "vector_store_healthy": vs.health_check() if vs else False,
        "vector_count": vs.count() if vs else 0,
        "embedding_provider": settings.embedding_provider,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
    }


# ── Run ────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )
