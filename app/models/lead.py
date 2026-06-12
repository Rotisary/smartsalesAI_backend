import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import relationship

from app.database import BaseModel
from app.utils.enums import Channel, LeadStatus


class Lead(BaseModel):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("business_id", "phone", name="uq_leads_business_phone"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    name = Column(String(255), nullable=True)
    phone = Column(String(32), nullable=False, index=True)
    channel = Column(
        SAEnum(Channel, name="channel_enum", values_callable=Channel.values),
        default=Channel.WHATSAPP,
        nullable=False,
    )
    status = Column(
        SAEnum(LeadStatus, name="lead_status_enum", values_callable=LeadStatus.values),
        default=LeadStatus.NEW,
        nullable=False,
        index=True,
    )
    intent_tags = Column(ARRAY(String), default=list, nullable=False)
    unread_count = Column(Integer, default=0, nullable=False)
    last_message = Column(String, nullable=True)

    lead_score = Column(Integer, default=0, nullable=False)
    is_human_mode = Column(Boolean, default=False, nullable=False)
    human_assigned_to = Column(String(255), nullable=True)
    last_customer_message_at = Column(DateTime(timezone=True), nullable=True)

    business = relationship("Business", back_populates="leads")
    messages = relationship(
        "Message",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    sales = relationship("Sale", back_populates="lead")
