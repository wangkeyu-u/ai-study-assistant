"""Knowledge Graph API routes (Phase 5)."""

from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional

from app.services.knowledge_graph import build_graph, get_graph_data, get_related_concepts

router = APIRouter(prefix="/api/knowledge-graph", tags=["knowledge-graph"])


class BuildRequest(BaseModel):
    doc_ids: Optional[list[str]] = None


@router.post("/build")
async def build_knowledge_graph(request: BuildRequest):
    """Build or update knowledge graph for specified documents."""
    result = await build_graph(request.doc_ids)
    return {
        "success": True,
        "documents_processed": result["documents_processed"],
        "concepts_added": result["concepts_added"],
        "relations_added": result["relations_added"],
    }


@router.get("")
async def get_graph(doc_ids: Optional[str] = Query(None, description="Comma-separated document IDs")):
    """Get knowledge graph data for visualization."""
    doc_id_list = None
    if doc_ids:
        doc_id_list = [id.strip() for id in doc_ids.split(",")]

    graph_data = get_graph_data(doc_id_list)
    return graph_data


@router.get("/related")
async def get_related(
    q: str = Query(..., description="Concept name to search"),
    top_k: int = Query(5, description="Number of related concepts to return"),
):
    """Get concepts related to a given concept name."""
    related = get_related_concepts(q, top_k)
    return {"concept": q, "related": related}
