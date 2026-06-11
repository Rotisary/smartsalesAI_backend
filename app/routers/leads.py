from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_business
from app.database import get_db
from app.models.business import Business
from app.schemas.lead import LeadListResponse, LeadRead, LeadUpdate
from app.services.lead_service import LeadService
from app.utils.enums import Channel, LeadStatus

router = APIRouter(prefix="/api/leads", tags=["Leads"])
lead_service = LeadService()


@router.get("/", response_model=LeadListResponse)
async def list_leads(
    status_filter: Optional[LeadStatus] = Query(default=None, alias="status"),
    channel: Optional[Channel] = None,
    search: Optional[str] = Query(default=None, min_length=1, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    leads, total = await lead_service.list_leads(
        db,
        business_id=current_business.id,
        status=status_filter,
        channel=channel,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {"items": leads, "total": total}


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(
    lead_id: UUID,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    lead = await lead_service.get_lead(
        db,
        business_id=current_business.id,
        lead_id=lead_id,
    )
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )
    return lead


@router.patch("/{lead_id}", response_model=LeadRead)
async def update_lead(
    lead_id: UUID,
    payload: LeadUpdate,
    current_business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    lead = await lead_service.get_lead(
        db,
        business_id=current_business.id,
        lead_id=lead_id,
    )
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lead not found",
        )

    return await lead_service.update_lead(
        db,
        lead=lead,
        values=payload.model_dump(exclude_unset=True),
    )
