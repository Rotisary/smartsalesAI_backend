import asyncio
import logging
import uuid

from celery import Task
from celery.exceptions import MaxRetriesExceededError

from app.celery import celery_app
from app.database import get_db
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)

RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,
)


class AIMessageProcessingTask(Task):
    """
    Custom base task class for AI message processing.
    Gives us on_failure / on_success hooks without cluttering the task body.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        lead_id_str = args[0] if args else kwargs.get("lead_id")
        logger.error(
            "AI processing task %s failed for lead %s: %s",
            task_id,
            lead_id_str,
            exc,
        )

    def on_success(self, retval, task_id, args, kwargs):
        lead_id_str = args[0] if args else kwargs.get("lead_id")
        logger.info(
            "AI processing task %s completed successfully for lead %s",
            task_id,
            lead_id_str,
        )


@celery_app.task(
    bind=True,
    base=AIMessageProcessingTask,
    name="ai.process_message",
    max_retries=3,
    default_retry_delay=30,
)
def process_message_task(
    self,
    message_data: dict,
    *,
    business_id: str,
    contacts_by_phone: dict[str, str],
    customer_name: str,
) -> dict:
    """
    Celery task for asynchronous AI message processing.
    this task calls the process_messasge method of the WebhookService
    """
    logger.info(
        "Starting AI message processing: lead_id=%s business_id=%s attempt=%d",
        message_data.get("id"),
        business_id,
        self.request.retries + 1,
    )

    try:
        service = WebhookService()
        result = asyncio.run(
            service.process_message(
                message_data,
                business_id=uuid.UUID(business_id),
                contacts_by_phone=contacts_by_phone,
                customer_name=customer_name,
            )
        )
        return result
    
    except ValueError as exc:
        logger.error(
            "Non-retryable error for message %s: %s — marking as failed",
            message_data.get("id"),
            exc,
        )
        raise

    except RETRYABLE_EXCEPTIONS as exc:
        retry_in = 60 * (2 ** self.request.retries)
        logger.warning(
            "Transient error for lead %s (attempt %d): %s — retrying in %ds",
            message_data.get("id"),
            self.request.retries + 1,
            exc,
            retry_in,
        )
        try:
            raise self.retry(exc=exc, countdown=retry_in)
        except MaxRetriesExceededError:
            logger.error("Max retries exceeded for lead %s", message_data.get("id"))
            raise

    except Exception as exc:
        retry_in = 60 * (2 ** self.request.retries)
        logger.exception(
            "Unexpected error for lead %s (attempt %d): %s",
            message_data.get("id"),
            self.request.retries + 1,
            exc,
        )
        try:
            raise self.retry(exc=exc, countdown=retry_in)
        except MaxRetriesExceededError:
            raise

