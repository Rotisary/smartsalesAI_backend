from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.utils.enums import IndustryCategory


class BusinessBase(BaseModel):
    business_owner_name: str
    business_email: str
    business_name: str
    industry_category: IndustryCategory
    support_whatsapp: str
    website_url: Optional[str] = None
    timezone: str = "Africa/Lagos"


class BusinessCreate(BusinessBase):
    password: str


class BusinessRead(BusinessBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_connected: bool
    connected_at: Optional[datetime] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime