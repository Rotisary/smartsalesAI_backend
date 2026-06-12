import asyncio
from typing import List

import google.generativeai as genai

from app.config import settings


class EmbeddingService:
    def __init__(
        self, 
        batch_size: int = 100, 
        embedding_dim: int = 768
    ):
        self.embedding_model = settings.EMBEDDING_MODEL
        self.batch_size = batch_size
        self.embedding_dim = embedding_dim

    @staticmethod    
    def _configure():
        genai.configure(api_key=settings.GEMINI_API_KEY)

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Synchronous embedding of a list of texts.
        Returns a list of 768-dimensional float vectors in the same order.

        Called from the async processing task via asyncio.to_thread().
        """

        EmbeddingService._configure()

        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            result = genai.embed_content(
                model=self.embedding_model,
                content=batch,
                task_type="RETRIEVAL_DOCUMENT",
            )
            all_embeddings.extend(result["embedding"])

        return all_embeddings


    async def embed_texts_async(self, texts: List[str]) -> List[List[float]]:
        """Async wrapper — runs embed_texts in a thread pool to avoid blocking the event loop."""
        return await asyncio.to_thread(self.embed_texts, texts)


    def embed_query(self, query: str) -> List[float]:
        """
        Embed a single query string for similarity search.
        Uses RETRIEVAL_QUERY task type (produces better retrieval results than DOCUMENT).
        """
        EmbeddingService._configure()
        result = genai.embed_content(
            model=self.embedding_model,
            content=query,
            task_type="RETRIEVAL_QUERY",
        )
        return result["embedding"]


    async def embed_query_async(self, query: str) -> List[float]:
        return await asyncio.to_thread(self.embed_query, query)