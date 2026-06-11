from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.utils.enums import MessageSender


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    lead_id: UUID
    sender: MessageSender
    content: str
    intent_tag: Optional[str] = None
    wa_message_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AgentMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class HandoffUpdate(BaseModel):
    isHuman: bool
    assignedTo: Optional[str] = Field(default=None, max_length=255)


class HandoffResponse(BaseModel):
    lead_id: UUID
    isHuman: bool
    assignedTo: Optional[str] = None
