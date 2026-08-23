"""Tests for RAG readiness and interview-demo endpoints."""


def test_rag_readiness_endpoint_returns_capability_map(test_app):
    response = test_app.get("/api/rag/readiness")

    assert response.status_code == 200
    data = response.json()
    assert 0 <= data["readiness_score"] <= 1
    assert data["runtime"]["vector_store_healthy"] is True
    assert data["data"]["vectors"] == 0
    assert {module["id"] for module in data["modules"]} >= {
        "ingestion",
        "retrieval",
        "planning",
        "context",
        "generation",
        "observability",
    }
    assert any(gate["name"] == "Citation validation" for gate in data["quality_gates"])
    assert len(data["demo_script"]) >= 3
