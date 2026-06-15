"""Shared context-building utilities used by Generator and specialist agents."""

CONTEXT_TEMPLATE = """[{index}] 文档: {doc_name}{page_info}
{heading_info}---
{chunk_text}
"""


def build_context_text(chunks: list) -> str:
    """Format retrieved chunks into a single context string for LLM prompts.

    Each chunk is formatted with its index, document name, page number, and
    heading (if available).  Chunks are separated by newlines.

    Args:
        chunks: List of ChunkResult objects with attributes:
                doc_name, page_num, heading, text.

    Returns:
        A formatted context string suitable for injection into a system prompt.
    """
    parts = []
    for i, chunk in enumerate(chunks, 1):
        page_info = f", 第{chunk.page_num}页" if chunk.page_num else ""
        heading_info = f"标题: {chunk.heading}\n" if chunk.heading else ""
        parts.append(
            CONTEXT_TEMPLATE.format(
                index=i,
                doc_name=chunk.doc_name,
                page_info=page_info,
                heading_info=heading_info,
                chunk_text=chunk.text,
            )
        )
    return "\n".join(parts)
