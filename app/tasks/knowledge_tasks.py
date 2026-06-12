import asyncio
import logging
import uuid

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.celery import celery_app
from app.services.document_processor import DocumentProcessor 

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


class DocumentProcessingTask(Task):
    """
    Custom base task class.
    Gives us on_failure / on_success hooks without cluttering the task body.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        document_id_str = args[0] if args else kwargs.get("document_id")
        logger.error(
            "Task %s failed permanently for document %s: %s",
            task_id,
            document_id_str,
            exc,
        )
        if document_id_str:
            try:
                asyncio.run(
                    DocumentProcessor.mark_document_failed(
                        document_id=uuid.UUID(document_id_str),
                        error=f"Processing failed after retries: {exc}",
                    )
                )
            except Exception:
                logger.exception("Could not mark document as failed in DB")

    def on_success(self, retval, task_id, args, kwargs):
        document_id_str = args[0] if args else kwargs.get("document_id")
        logger.info(
            "Task %s completed successfully for document %s",
            task_id,
            document_id_str,
        )


@celery_app.task(
    bind=True,
    base=DocumentProcessingTask,
    name="knowledge.process_document",
    max_retries=3,
    default_retry_delay=30,
)
def process_document_task(self, document_id: str, business_id: str) -> dict:
    """
    Main Celery task entry point.

    Args:
        document_id:  str UUID of the KnowledgeDocument row
        business_id:  str UUID of the owning Business (for logging / Socket.IO)
    """
    logger.info(
        "Starting document processing: document_id=%s business_id=%s attempt=%d",
        document_id,
        business_id,
        self.request.retries + 1,
    )

    try:
        result = asyncio.run(
            DocumentProcessor.process_document(
                document_id=uuid.UUID(document_id),
                business_id=uuid.UUID(business_id),
            )
        )
        return result

    except ValueError as exc:
        logger.error(
            "Non-retryable error for document %s: %s — marking as failed",
            document_id,
            exc,
        )
        raise

    except RETRYABLE_EXCEPTIONS as exc:
        retry_in = 60 * (2 ** self.request.retries)
        logger.warning(
            "Transient error for document %s (attempt %d): %s — retrying in %ds",
            document_id,
            self.request.retries + 1,
            exc,
            retry_in,
        )
        try:
            raise self.retry(exc=exc, countdown=retry_in)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for document %s", document_id)
            raise

    except Exception as exc:
        retry_in = 60 * (2 ** self.request.retries)
        logger.exception(
            "Unexpected error for document %s (attempt %d): %s",
            document_id,
            self.request.retries + 1,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=retry_in)
        except MaxRetriesExceededError:
            raise
