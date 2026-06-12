from app.utils.enums.base import BaseEnum


class DocumentProcessingStatus(BaseEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"
