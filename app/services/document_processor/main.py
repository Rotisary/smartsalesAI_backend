import uuid
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import select, delete
from sqlalchemy.orm import sessionmaker

from app.database import engine
from app.models.knowledge_base import KnowledgeDocument, KnowledgeChunk
from app.services.s3_service import read_object_bytes
from .extraction_service import ExtractionService
from .chunking_service import chunk_text
from app.services.embeddings_service import EmbeddingService
from app.utils.enums import  DocumentProcessingStatus

logger = logging.getLogger(__name__)


class DocumentProcessor:

    @staticmethod
    def _make_session() -> AsyncSession:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return factory()

    @staticmethod
    async def process_document(document_id: uuid.UUID, business_id: uuid.UUID) -> dict:
        async with DocumentProcessor._make_session() as db:
            return await DocumentProcessor._run(db, document_id, business_id)


    @staticmethod
    async def mark_document_failed(document_id: uuid.UUID, error: str) -> None:
        async with DocumentProcessor._make_session() as db:
            result = await db.execute(
                select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
            )
            doc = result.scalar_one_or_none()
            if doc:
                doc.status = DocumentProcessingStatus.FAILED.value
                doc.error_message = error[:1000]
                await db.commit()

    @staticmethod
    async def _run(db: AsyncSession, document_id: uuid.UUID, business_id: uuid.UUID) -> dict:
        import asyncio

        result = await db.execute(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id)
        )
        doc: KnowledgeDocument | None = result.scalar_one_or_none()

        if doc is None:
            raise ValueError(f"Document {document_id} not found in database.")

        if doc.status == DocumentProcessingStatus.READY.value:
            return {"document_id": str(document_id), "chunk_count": doc.chunk_count}

        doc.status = DocumentProcessingStatus.PROCESSING.value
        doc.error_message = None
        await db.commit()

        try:
            file_bytes = await asyncio.to_thread(read_object_bytes, doc.s3_key)

            logger.info("Extracting text from %s (%s)", doc.filename, doc.content_type)
            raw_text = ExtractionService.extract_text(file_bytes, doc.content_type, doc.filename)

            if not raw_text.strip():
                raise ValueError("No readable text found in document. Check that the file is not empty or image-only.")

            chunks = chunk_text(raw_text)
            logger.info("Created %d chunks for document %s", len(chunks), document_id)

            if not chunks:
                raise ValueError("Document produced zero chunks after splitting. File may be too short.")
            
            logger.info("Embedding %d chunks...", len(chunks))
            embedding_service = EmbeddingService()
            embeddings = await embedding_service.embed_texts_async(chunks)

            await db.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.document_id == document_id)
            )

            chunk_rows = [
                KnowledgeChunk(
                    document_id=document_id,
                    business_id=doc.business_id,
                    chunk_index=i,
                    content=chunk,
                    embedding=embedding,
                )
                for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
            ]
            db.add_all(chunk_rows)

            doc.status = DocumentProcessingStatus.READY.value
            doc.chunk_count = len(chunk_rows)
            await db.commit()

            logger.info(
                "Document %s ready — %d chunks stored", document_id, len(chunk_rows)
            )

            await _emit_ready(business_id=doc.business_id, document_id=document_id, chunk_count=len(chunk_rows))

            return {"document_id": str(document_id), "chunk_count": len(chunk_rows)}

        except Exception as exc:
            doc.status = DocumentProcessingStatus.FAILED.value
            doc.error_message = str(exc)[:1000]
            await db.commit()
            raise


async def _emit_ready(business_id: uuid.UUID, document_id: uuid.UUID, chunk_count: int) -> None:
    """
    Push a Socket.IO event to the business room so the frontend knows
    the document is ready without polling.
    """
    try:
        from app.core.socket_manager import sio

        await sio.emit(
            "knowledge_document_ready",
            {
                "document_id": str(document_id),
                "chunk_count": chunk_count,
            },
            room=f"business_{business_id}",
        )
        logger.info("Emitted knowledge_document_ready to room business_%s", business_id)
    except Exception as exc:
        logger.warning("Socket.IO emit failed (non-critical): %s", exc)