import uuid
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from app.models.knowledge_base import KnowledgeChunk, KnowledgeDocument
from app.services.embeddings_service import EmbeddingService

logger = logging.getLogger(__name__)

TOP_K_DEFAULT = 5
MIN_SIMILARITY = 0.3 


async def retrieve_context(
    db: AsyncSession,
    business_id: uuid.UUID,
    query: str,
    top_k: int = TOP_K_DEFAULT,
) -> Optional[str]:
    """
    Embed the query, find the top-k most similar chunks for this business,
    and return them concatenated as a single string for prompt injection.

    Returns None if no relevant chunks are found.
    """
    try:
        service = EmbeddingService()
        query_embedding = await service.embed_query_async(query)
    except Exception as exc:
        logger.warning("RAG embedding failed, skipping context: %s", exc)
        return None

    stmt = text("""
        SELECT kc.content,
               1 - (kc.embedding <=> cast(:embedding AS vector)) AS similarity
        FROM   knowledge_chunks kc
        JOIN   knowledge_documents kd ON kd.id = kc.document_id
        WHERE  kc.business_id = :business_id
          AND  kd.status      = 'ready'
          AND  1 - (kc.embedding <=> cast(:embedding AS vector)) >= :min_sim
        ORDER BY similarity DESC
        LIMIT  :top_k
    """)

    result = await db.execute(
        stmt,
        {
            "embedding": str(query_embedding),
            "business_id": str(business_id),
            "min_sim": MIN_SIMILARITY,
            "top_k": top_k,
        },
    )
    rows = result.fetchall()

    if not rows:
        return None

    chunks = [row.content for row in rows]
    context = "\n\n---\n\n".join(chunks)

    return context


def build_rag_system_prompt(base_prompt: str, context: Optional[str]) -> str:
    """
    Inject retrieved context into the base system prompt.

    Call this inside your ai_service.py, replacing the current
    knowledge_base injection with:

        context = await retrieve_context(db, business_id, user_message)
        system_prompt = build_rag_system_prompt(base_prompt, context)
    """
    if not context:
        return base_prompt

    rag_block = (
        "\n\n## Relevant Knowledge Base Excerpts\n"
        "Use the following information to answer the customer's question accurately. "
        "If the answer is not in these excerpts, say you'll check and follow up.\n\n"
        f"{context}"
    )

    return base_prompt + rag_block