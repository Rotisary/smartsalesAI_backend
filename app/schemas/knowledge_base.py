from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from app.config import settings
from app.utils.enums import DocumentProcessingStatus 


ALLOWED_CONTENT_TYPES: set[str] = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
    "text/markdown",
}

ALLOWED_EXTENSIONS: set[str] = {".pdf", ".docx", ".doc", ".txt", ".md"}



class PresignedUrlRequest(BaseModel):
    filename: str = Field(..., min_length=1, max_length=512)
    content_type: str = Field(
        ...,
        description=(
            "MIME type of the file. "
            f"Allowed: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        ),
    )
    file_size_bytes: Optional[int] = Field(
        None,
        gt=0,
        le=settings.MAX_FILE_SIZE_BYTES,
        description=f"File size in bytes. Maximum {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB.",
    )

    @field_validator("filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        import os
        value = os.path.basename(value)
        _, ext = os.path.splitext(value.lower())
        if not ext:
            raise ValueError("Filename must include a file extension e.g. 'report.pdf'")
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(
                f"File extension '{ext}' is not supported. "
                f"Allowed extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
            )
        return value

    @field_validator("content_type")
    @classmethod
    def validate_content_type(cls, value: str) -> str:
        if value not in ALLOWED_CONTENT_TYPES:
            raise ValueError(
                f"Content type '{value}' is not supported. "
                f"Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
            )
        return value


class PresignedUrlResponse(BaseModel):
    document_id: UUID
    upload_url: str 
    s3_key: str
    expires_in: int


class UploadConfirmRequest(BaseModel):
    file_size_bytes: Optional[int] = None


class KnowledgeDocumentResponse(BaseModel):
    id: UUID  
    business_id: UUID 
    filename: str 
    s3_key: str 
    content_type: str
    file_size_bytes: Optional[int] = None
    status: DocumentProcessingStatus
    error_message: Optional[str]
    chunk_count: int
    created_at: datetime
    updated_at: datetime 

    model_config = {"from_attributes": True}


class ReprocessResponse(BaseModel):
    document_id: UUID 
    message: str 


class DeleteDocumentResponse(BaseModel):
    message: str