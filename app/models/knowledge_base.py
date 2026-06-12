import uuid

from sqlalchemy import (
    Column, String, Text, Integer,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.database import BaseModel

from app.utils.enums import DocumentProcessingStatus

class KnowledgeDocument(BaseModel):
    __tablename__ = "knowledge_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    filename = Column(String(512), nullable=False)
    s3_key = Column(String(1024), nullable=False)
    content_type = Column(String(256), nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    status = Column(
        SAEnum(
            DocumentProcessingStatus,
            name="document_status",
            values_callable=DocumentProcessingStatus.values,
        ),
        default=DocumentProcessingStatus.PENDING.value,
        nullable=False,
        index=True
    )
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)

    chunks = relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )


# Embedding dimension for Google text-embedding-004
EMBEDDING_DIM = 768


class KnowledgeChunk(BaseModel):
    __tablename__ = "knowledge_chunks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("knowledge_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding   = Column(Vector(EMBEDDING_DIM), nullable=True)
    document = relationship("KnowledgeDocument", back_populates="chunks")