import uuid

from sqlalchemy import Boolean, Column, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import BaseModel


class BusinessSettings(BaseModel):
    __tablename__ = "business_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    business_name = Column(String(255), nullable=False)
    ai_persona_name = Column(String(255), default="Aria", nullable=False)
    ai_tone = Column(String(64), default="Friendly", nullable=False)
    auto_followup = Column(Boolean, default=True, nullable=False)
    human_handoff_trigger = Column(Boolean, default=True, nullable=False)

    business = relationship("Business", back_populates="settings")