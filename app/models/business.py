import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base
from app.utils.enums import IndustryCategory


class Business(Base):
    __tablename__ = "businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    business_owner_name = Column(String(255), nullable=False)
    business_email = Column(String(255), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    business_name = Column(String(255), nullable=False)
    industry_category = Column(
        SAEnum(
            IndustryCategory,
            name="industry_category_enum",
            values_callable=IndustryCategory.values,
        ),
        nullable=False,
    )
    support_whatsapp = Column(String(32), nullable=False)
    website_url = Column(String(512), nullable=True)

    whatsapp_phone_number_id = Column(String(64), nullable=False, unique=True)
    whatsapp_connected = Column(Boolean, default=False, nullable=False)
    connected_at = Column(DateTime, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    timezone = Column(String(64), default="Africa/Lagos", nullable=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<Business(id={self.id!s}, business_name={self.business_name!r}, "
            f"business_email={self.business_email!r})>"
        )
