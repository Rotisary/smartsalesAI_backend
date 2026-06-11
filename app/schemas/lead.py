from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.utils.enums import Channel, LeadStatus


class LeadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    name: Optional[str] = None
    phone: str
    channel: Channel
    status: LeadStatus
    intent_tags: list[str]
    unread_count: int
    last_message: Optional[str] = None
    lead_score: int
    is_human_mode: bool
    human_assigned_to: Optional[str] = None
    last_customer_message_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class LeadUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=255)
    status: Optional[LeadStatus] = None
    unread_count: Optional[int] = Field(default=None, ge=0)
    lead_score: Optional[int] = Field(default=None, ge=0)
    is_human_mode: Optional[bool] = None
    human_assigned_to: Optional[str] = Field(default=None, max_length=255)


class LeadListResponse(BaseModel):
    items: list[LeadRead]
    total: int
