from celery import Celery
from app.config import settings

celery_app = Celery(
    "smartsales",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks.knowledge_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    timezone="UTC",
    enable_utc=True,

    result_expires=3600,

    task_acks_late=True,           
    task_reject_on_worker_lost=True,   
    worker_prefetch_multiplier=1,     

    task_default_retry_delay=30, 
    task_max_retries=3,
)