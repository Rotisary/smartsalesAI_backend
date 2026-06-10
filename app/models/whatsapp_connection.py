from sqlalchemy import Column, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import BaseModel


class WhatsAppConnection(BaseModel):
    __tablename__ = "whatsapp_connections"

    phone_number_id = Column(String(64), primary_key=True)
    business_id = Column(
        UUID(as_uuid=True),
        ForeignKey("businesses.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    whatsapp_business_account_id = Column(String(64), nullable=False, index=True)
    display_phone_number = Column(String(32), nullable=False)
    verified_name = Column(String(255), nullable=True)
    encrypted_access_token = Column(String, nullable=False)
    status = Column(String(32), default="connected", nullable=False)

    business = relationship("Business", back_populates="whatsapp_connection")
