import asyncio
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.knowledge_base import KnowledgeDocument
from app.models.business import Business
from app.schemas.knowledge_base import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    UploadConfirmRequest,
    KnowledgeDocumentResponse,
    ReprocessResponse,
    DeleteDocumentResponse,
)
from app.services.s3_service import build_s3_key, generate_presigned_upload_url, delete_object
from app.tasks.knowledge_tasks import process_document_task
from app.core.dependencies import get_current_business
from app import settings
from app.utils.enums import DocumentProcessingStatus
from app.utils.knowledge_base import _get_doc_or_404

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Base"])


@router.post(
    "/get-presigned-url",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request an S3 presigned upload URL",
)
async def request_presigned_url(
    body: PresignedUrlRequest,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> PresignedUrlResponse:
    document_id = uuid.uuid4()
    s3_key = build_s3_key(current_business.id, document_id, body.filename)

    try:
        upload_url = await asyncio.to_thread(
            generate_presigned_upload_url,
            s3_key,
            body.content_type,
            settings.PRESIGNED_URL_TTL,
        )
    except Exception as exc:
        logger.exception("Presigned URL generation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate upload URL. Please try again.",
        )

    doc = KnowledgeDocument(
        id=document_id,
        business_id=current_business.id,
        filename=body.filename,
        s3_key=s3_key,
        content_type=body.content_type,
        file_size_bytes=body.file_size_bytes,
        status=DocumentProcessingStatus.PENDING.value,
    )
    db.add(doc)
    await db.commit()

    return PresignedUrlResponse(
        document_id=document_id,
        upload_url=upload_url,
        s3_key=s3_key,
        expires_in=settings.PRESIGNED_URL_TTL,
    )


@router.post(
    "/{document_id}/confirm",
    response_model=KnowledgeDocumentResponse,
    summary="Confirm S3 upload complete — triggers background processing",
)
async def confirm_upload(
    document_id: uuid.UUID,
    body: UploadConfirmRequest,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    document = await _get_doc_or_404(db, document_id, current_business.id)

    if document.status == DocumentProcessingStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is already being processed.",
        )

    if document.status == DocumentProcessingStatus.READY.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document has already been processed successfully. Use /reprocess to re-run.",
        )

    if body.file_size_bytes:
        document.file_size_bytes = body.file_size_bytes
        await db.commit()

    process_document_task.delay(str(document_id), str(current_business.id))
    await db.refresh(document)
    return KnowledgeDocumentResponse.model_validate(document)


@router.get(
    "/",
    response_model=list[KnowledgeDocumentResponse],
    summary="List all knowledge documents for a business",
)
async def list_documents(
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> list[KnowledgeDocumentResponse]:
    result = await db.execute(
        select(KnowledgeDocument)
        .where(KnowledgeDocument.business_id == current_business.id)
        .order_by(KnowledgeDocument.created_at.desc())
    )
    docs = result.scalars().all()
    return [KnowledgeDocumentResponse.model_validate(d) for d in docs]


@router.get(
    "/{document_id}",
    response_model=KnowledgeDocumentResponse,
    summary="Get a single knowledge document (use for status polling)",
)
async def get_document(
    document_id: uuid.UUID,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> KnowledgeDocumentResponse:
    doc = await _get_doc_or_404(db, document_id, current_business.id)
    return KnowledgeDocumentResponse.model_validate(doc)


@router.post(
    "/{document_id}/reprocess",
    response_model=ReprocessResponse,
    summary="Re-trigger processing for a failed document",
)
async def reprocess_document(
    document_id: uuid.UUID,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> ReprocessResponse:
    """
    Useful when a document is stuck in 'failed' status.
    Resets the status to 'pending' and re-dispatches the Celery task.
    """
    doc = await _get_doc_or_404(db, document_id, current_business.id)

    if doc.status == DocumentProcessingStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is currently being processed.",
        )

    doc.status = DocumentProcessingStatus.PENDING.value
    doc.error_message = None
    await db.commit()
    process_document_task.delay(str(document_id), str(current_business.id))

    return ReprocessResponse(
        document_id=document_id,
        message="Reprocessing started. Listen for the 'knowledge_document_ready' event or poll status.",
    )


@router.delete(
    "/{document_id}",
    response_model=DeleteDocumentResponse,
    summary="Delete a knowledge document, all its chunks, and its S3 object",
)
async def delete_document(
    document_id: uuid.UUID,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
) -> DeleteDocumentResponse:
    doc = await _get_doc_or_404(db, document_id, current_business.id)

    if doc.status == DocumentProcessingStatus.PROCESSING.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete a document that is currently being processed.",
        )

    try:
        await asyncio.to_thread(delete_object, doc.s3_key)
    except Exception as exc:
        logger.warning("S3 delete failed for key %s: %s", doc.s3_key, exc)

    await db.delete(doc)
    await db.commit()

    return DeleteDocumentResponse(
        message=f"Document '{doc.filename}' and all associated chunks have been deleted."
    )

