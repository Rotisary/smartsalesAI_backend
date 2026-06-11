import uuid

from sqlalchemy import Column, Enum as SAEnum, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import BaseModel
from app.utils.enums import Channel, SaleStatus


class Sale(BaseModel):
    __tablename__ = "sales"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    customer = Column(String(255), nullable=False)
    product = Column(String(255), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    status = Column(
        SAEnum(SaleStatus, name="sale_status_enum", values_callable=SaleStatus.values),
        default=SaleStatus.PENDING,
        nullable=False,
        index=True,
    )
    channel = Column(
        SAEnum(Channel, name="sale_channel_enum", values_callable=Channel.values),
        default=Channel.WHATSAPP,
        nullable=False,
    )

    business = relationship("Business", back_populates="sales")
    lead = relationship("Lead", back_populates="sales")
