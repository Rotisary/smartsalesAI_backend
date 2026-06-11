from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.utils.enums import Channel, SaleStatus


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    lead_id: Optional[UUID] = None
    customer: str
    product: str
    amount: Decimal
    status: SaleStatus
    channel: Channel
    created_at: datetime
    updated_at: datetime
