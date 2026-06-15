"""
Knowledge Graph Service (Phase 5).
Extracts concepts and relations from document chunks using LLM,
builds a graph in SQLite, and provides query APIs for visualization
and chat-based concept recommendations.
"""

import asyncio
import json
import logging
import re
import uuid

from openai import AsyncOpenAI

from app.config import get_settings
from app.db.database import get_db

logger = logging.getLogger(__name__)

# Max concurrent LLM calls for concept extraction
MAX_CONCURRENT_EXTRACTIONS = 10


# ---------------------------------------------------------------------------
# Concept extraction
# ---------------------------------------------------------------------------

EXTRACTION_PROMPT = """你是一个知识图谱构建专家。请从以下文本中提取关键概念和它们之间的关系。

文本内容：
{text}

请按以下JSON格式返回结果：
{{
  "concepts": [
    {{"name": "概念名称", "category": "类别", "description": "简短描述"}},
    ...
  ],
  "relations": [
    {{"source": "源概念名称", "target": "目标概念名称", "type": "关系类型"}},
    ...
  ]
}}

类别可以是：技术、人物、组织、概念、方法、工具、领域、理论
关系类型可以是：相关、属于、使用、包含、依赖、对比、衍生

要求：
1. 提取文本中最重要的 3-10 个概念
2. 概念名称使用标准术语，保持简洁
3. 关系应反映概念间的真实语义联系
4. 仅返回JSON，不要附加其他文字"""


async def extract_concepts_from_chunks(
    chunks: list[dict],
) -> dict:
    """
    Extract concepts and relations from a list of text chunks using LLM.

    Args:
        chunks: list of {"id": str, "text": str, ...}

    Returns:
        Merged result:
        {
          "concepts": [{"name", "category", "description"}],
          "relations": [{"source", "target", "type", "count"}]
        }
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url or None)

    # Filter valid chunks first
    valid_chunks = [c for c in chunks if c.get("text") and len(c["text"].strip()) >= 50]

    if not valid_chunks:
        return {"concepts": [], "relations": []}

    # Process chunks in parallel with concurrency limit
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)

    async def extract_one(chunk: dict) -> dict:
        async with semaphore:
            try:
                return await _extract_single_chunk(client, chunk["text"], settings.llm_model)
            except Exception as e:
                logger.warning(f"[KG] Chunk extraction failed: {e}")
                return {"concepts": [], "relations": []}

    results = await asyncio.gather(*(extract_one(c) for c in valid_chunks))

    # Merge results (sequential, no race conditions)
    all_concepts: dict[str, dict] = {}  # name -> concept info
    all_relations: dict[str, dict] = {}  # (src, tgt, type) -> relation info

    for result in results:
        # Merge concepts (deduplicate by name)
        for concept in result.get("concepts", []):
            name = concept.get("name", "").strip()
            if not name:
                continue
            if name in all_concepts:
                existing_desc = all_concepts[name].get("description", "")
                new_desc = concept.get("description", "")
                if len(new_desc) > len(existing_desc):
                    all_concepts[name]["description"] = new_desc
                if not all_concepts[name].get("category") and concept.get("category"):
                    all_concepts[name]["category"] = concept["category"]
            else:
                all_concepts[name] = {
                    "name": name,
                    "category": concept.get("category", "概念"),
                    "description": concept.get("description", ""),
                }

        # Merge relations (accumulate strength by count)
        for rel in result.get("relations", []):
            source = rel.get("source", "").strip()
            target = rel.get("target", "").strip()
            rtype = rel.get("type", "相关").strip()
            if not source or not target:
                continue
            key = f"{source}||{target}||{rtype}"
            if key in all_relations:
                all_relations[key]["count"] += 1
            else:
                all_relations[key] = {
                    "source": source,
                    "target": target,
                    "type": rtype,
                    "count": 1,
                }

    return {
        "concepts": list(all_concepts.values()),
        "relations": list(all_relations.values()),
    }


async def _extract_single_chunk(client: AsyncOpenAI, text: str, model: str) -> dict:
    """Extract concepts and relations from a single text chunk."""
    messages = [
        {"role": "system", "content": "你是一个精确的知识图谱构建助手，仅返回JSON格式的结果。"},
        {"role": "user", "content": EXTRACTION_PROMPT.format(text=text)},
    ]

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.1,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        logger.error(f"[KG] LLM call failed: {e}")
        return {"concepts": [], "relations": []}

    # Try to parse JSON from the response
    try:
        return json.loads(raw)  # type: ignore[no-any-return]
    except json.JSONDecodeError:
        # Attempt to extract JSON block from response
        match = re.search(r"\{[\s\S]*\}", raw)
        if match:
            try:
                return json.loads(match.group())  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                return {"concepts": [], "relations": []}
        return {"concepts": [], "relations": []}


# ---------------------------------------------------------------------------
# Graph building (persist to database)
# ---------------------------------------------------------------------------


async def build_graph_for_document(
    doc_id: str,
    chunks: list[dict],
) -> dict:
    """
    Extract concepts from chunks and persist them into the database.
    Updates existing concepts (increment doc_count) and relations (add strength).

    Args:
        doc_id: Document ID
        chunks: list of {"id": str, "text": str, ...}

    Returns:
        {"concepts_added": int, "relations_added": int}
    """
    extracted = await extract_concepts_from_chunks(chunks)

    concept_id_map: dict[str, str] = {}  # name -> concept_id

    with get_db() as conn:
        # Upsert concepts
        for concept in extracted["concepts"]:
            name = concept["name"]

            existing = conn.execute(
                "SELECT id, doc_count FROM concepts WHERE name = ?", (name,)
            ).fetchone()

            if existing:
                concept_id = existing["id"]
                conn.execute(
                    "UPDATE concepts SET doc_count = doc_count + 1 WHERE id = ?",
                    (concept_id,),
                )
            else:
                concept_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO concepts (id, name, category, description, doc_count)
                       VALUES (?, ?, ?, ?, 1)""",
                    (
                        concept_id,
                        name,
                        concept.get("category", "概念"),
                        concept.get("description", ""),
                    ),
                )

            concept_id_map[name] = concept_id

        # Upsert relations
        for rel in extracted["relations"]:
            source_id = concept_id_map.get(rel["source"])
            target_id = concept_id_map.get(rel["target"])
            if not source_id or not target_id:
                continue

            existing_rel = conn.execute(
                """SELECT id, strength FROM concept_relations
                   WHERE source_concept_id = ? AND target_concept_id = ?
                   AND relation_type = ?""",
                (source_id, target_id, rel["type"]),
            ).fetchone()

            if existing_rel:
                new_strength = existing_rel["strength"] + rel.get("count", 1)
                conn.execute(
                    "UPDATE concept_relations SET strength = ? WHERE id = ?",
                    (new_strength, existing_rel["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO concept_relations
                       (id, source_concept_id, target_concept_id,
                        relation_type, strength, doc_id)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        str(uuid.uuid4()),
                        source_id,
                        target_id,
                        rel["type"],
                        float(rel.get("count", 1)),
                        doc_id,
                    ),
                )

        conn.commit()

    return {
        "concepts_added": len(extracted["concepts"]),
        "relations_added": len(extracted["relations"]),
    }


async def build_graph(doc_ids: list[str] | None = None) -> dict:
    """
    Build/update the knowledge graph for specified documents.
    If no doc_ids provided, processes all documents with status='ready'.

    Returns:
        {"documents_processed": int, "concepts_added": int, "relations_added": int}
    """
    with get_db() as conn:
        if doc_ids:
            placeholders = ",".join("?" for _ in doc_ids)
            rows = conn.execute(
                f"SELECT id, filename FROM documents WHERE id IN ({placeholders}) AND status = 'ready'",
                doc_ids,
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, filename FROM documents WHERE status = 'ready'"
            ).fetchall()

    total_concepts = 0
    total_relations = 0

    for row in rows:
        doc_id = row["id"]
        # Load chunks for this document
        with get_db() as conn:
            chunks = conn.execute(
                "SELECT id, text FROM chunks WHERE doc_id = ?",
                (doc_id,),
            ).fetchall()

        if not chunks:
            continue

        chunk_list = [{"id": c["id"], "text": c["text"]} for c in chunks]

        result = await build_graph_for_document(doc_id, chunk_list)
        total_concepts += result["concepts_added"]
        total_relations += result["relations_added"]
        logger.info(
            f"[KG] Document {doc_id}: {result['concepts_added']} concepts, {result['relations_added']} relations"
        )

    return {
        "documents_processed": len(rows),
        "concepts_added": total_concepts,
        "relations_added": total_relations,
    }


# ---------------------------------------------------------------------------
# Query APIs
# ---------------------------------------------------------------------------


def get_related_concepts(concept_name: str, top_k: int = 5) -> list[dict]:
    """
    Get concepts related to the given concept name.
    Returns related concepts sorted by relation strength.
    """
    with get_db() as conn:
        concept = conn.execute("SELECT id FROM concepts WHERE name = ?", (concept_name,)).fetchone()

        if not concept:
            return []

        concept_id = concept["id"]

        # Find all relations involving this concept (both directions)
        rows = conn.execute(
            """
            SELECT c.name, c.category, c.description,
                   cr.relation_type, cr.strength,
                   CASE WHEN cr.source_concept_id = ? THEN 'outgoing' ELSE 'incoming' END as direction
            FROM concept_relations cr
            JOIN concepts c ON (
                CASE WHEN cr.source_concept_id = ?
                     THEN cr.target_concept_id
                     ELSE cr.source_concept_id
                END
            ) = c.id
            WHERE cr.source_concept_id = ? OR cr.target_concept_id = ?
            ORDER BY cr.strength DESC
            LIMIT ?
            """,
            (concept_id, concept_id, concept_id, concept_id, top_k),
        ).fetchall()

        return [
            {
                "name": r["name"],
                "category": r["category"],
                "description": r["description"],
                "relation_type": r["relation_type"],
                "strength": r["strength"],
                "direction": r["direction"],
            }
            for r in rows
        ]


def get_graph_data(doc_ids: list[str] | None = None) -> dict:
    """
    Get full graph data (nodes + edges) for visualization.
    Optionally filter by document IDs.

    Returns:
        {
            "nodes": [{"id", "name", "category", "description", "doc_count"}],
            "edges": [{"source", "target", "relation_type", "strength"}]
        }
    """
    with get_db() as conn:
        if doc_ids:
            # Filter: get concepts that appear in the specified documents
            placeholders = ",".join("?" for _ in doc_ids)
            concept_rows = conn.execute(
                f"""SELECT DISTINCT c.id, c.name, c.category, c.description, c.doc_count
                    FROM concepts c
                    JOIN concept_relations cr ON (
                        c.id = cr.source_concept_id OR c.id = cr.target_concept_id
                    )
                    WHERE cr.doc_id IN ({placeholders})
                    ORDER BY c.doc_count DESC""",
                doc_ids,
            ).fetchall()

            concept_ids = [c["id"] for c in concept_rows]
            if not concept_ids:
                return {"nodes": [], "edges": []}

            edge_placeholders = ",".join("?" for _ in concept_ids)
            edge_rows = conn.execute(
                f"""SELECT cr.source_concept_id, cr.target_concept_id,
                           cr.relation_type, cr.strength
                    FROM concept_relations cr
                    WHERE cr.source_concept_id IN ({edge_placeholders})
                    AND cr.target_concept_id IN ({edge_placeholders})""",
                concept_ids + concept_ids,
            ).fetchall()
        else:
            concept_rows = conn.execute(
                """SELECT id, name, category, description, doc_count
                   FROM concepts ORDER BY doc_count DESC"""
            ).fetchall()
            edge_rows = conn.execute(
                """SELECT source_concept_id, target_concept_id,
                          relation_type, strength
                   FROM concept_relations"""
            ).fetchall()

        nodes = [
            {
                "id": c["id"],
                "name": c["name"],
                "category": c["category"],
                "description": c["description"],
                "doc_count": c["doc_count"],
            }
            for c in concept_rows
        ]

        edges = [
            {
                "source": e["source_concept_id"],
                "target": e["target_concept_id"],
                "relation_type": e["relation_type"],
                "strength": e["strength"],
            }
            for e in edge_rows
        ]

        return {"nodes": nodes, "edges": edges}
