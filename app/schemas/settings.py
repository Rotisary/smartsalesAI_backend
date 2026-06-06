from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class BusinessSettingsBase(BaseModel):
    business_name: Optional[str] = None
    ai_persona_name: Optional[str] = None
    ai_tone: Optional[str] = None
    knowledge_base: Optional[str] = None
    auto_followup: Optional[bool] = None
    human_handoff_trigger: Optional[bool] = None


class BusinessSettingsCreate(BusinessSettingsBase):
    pass


class BusinessSettingsRead(BusinessSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: str
    business_id: str
    business_name: str
    ai_persona_name: str
    ai_tone: str
    knowledge_base: str
    auto_followup: bool
    human_handoff_trigger: bool
    created_at: datetime
    updated_at: datetime