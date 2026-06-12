from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.utils.enums import Channel, SaleStatus


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    lead_id: Optional[UUID] = None
    customer: str
    product: str
    amount: float
    status: SaleStatus
    channel: Channel
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def date(self) -> datetime:
        return self.created_at


class SaleCreate(BaseModel):
    lead_id: Optional[UUID] = None
    customer: str = Field(min_length=1, max_length=255)
    product: str = Field(min_length=1, max_length=255)
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    status: SaleStatus = SaleStatus.PENDING
    channel: Channel = Channel.WHATSAPP


class SaleUpdate(BaseModel):
    lead_id: Optional[UUID] = None
    customer: Optional[str] = Field(default=None, min_length=1, max_length=255)
    product: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    status: Optional[SaleStatus] = None
    channel: Optional[Channel] = None


class SaleListResponse(BaseModel):
    items: list[SaleRead]
    total: int


class SaleSummary(BaseModel):
    total_orders: int
    completed_orders: int
    pending_orders: int
    refunded_orders: int
    total_revenue: float
    gross_revenue: float
    pending_revenue: float
    refunded_revenue: float
    average_order_value: float
    refund_rate: float
