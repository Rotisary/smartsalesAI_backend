import uuid

from sqlalchemy import Column, Enum as SAEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import BaseModel
from app.utils.enums import MessageSender


class Message(BaseModel):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("business_id", "wa_message_id", name="uq_messages_business_wa_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender = Column(
        SAEnum(MessageSender, name="message_sender_enum", values_callable=MessageSender.values),
        nullable=False,
        index=True,
    )
    content = Column(String, nullable=False)
    intent_tag = Column(String(64), nullable=True)
    wa_message_id = Column(String(255), nullable=True)

    business = relationship("Business", back_populates="messages")
    lead = relationship("Lead", back_populates="messages")
