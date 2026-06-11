from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_business
from app.core.exceptions.whatsapp import WhatsAppAPIError, WhatsAppConfigurationError
from app.database import get_db
from app.models.business import Business
from app.models.whatsapp_connection import WhatsAppConnection
from app.schemas.message import (
    AgentMessageCreate,
    HandoffResponse,
    HandoffUpdate,
    MessageRead,
)
from app.services.lead_service import LeadService
from app.services.whatsapp_service import WhatsAppService
from app.utils.enums import MessageSender

router = APIRouter(prefix="/api/messages", tags=["Messages"])
lead_service = LeadService()


@router.get("/{lead_id}", response_model=list[MessageRead])
async def list_messages(
    lead_id: UUID,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
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

    return await lead_service.list_messages(
        db,
        business_id=current_business.id,
        lead_id=lead_id,
        limit=limit,
        offset=offset,
    )


@router.post("/{lead_id}/agent-reply", response_model=MessageRead, status_code=status.HTTP_201_CREATED)
async def send_agent_reply(
    lead_id: UUID,
    payload: AgentMessageCreate,
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
    if not current_business.whatsapp_connected or not current_business.whatsapp_phone_number_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp is not connected for this business",
        )

    connection = await db.get(
        WhatsAppConnection,
        current_business.whatsapp_phone_number_id,
    )
    if not connection or connection.business_id != current_business.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="WhatsApp connection details are missing for this business",
        )

    whatsapp = WhatsAppService()
    try:
        await whatsapp.send_text(connection, lead.phone, payload.content)
    except (WhatsAppAPIError, WhatsAppConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return await lead_service.save_message(
        db,
        business_id=current_business.id,
        lead=lead,
        sender=MessageSender.AGENT,
        content=payload.content,
    )


@router.post("/{lead_id}/handoff", response_model=HandoffResponse)
async def toggle_handoff(
    lead_id: UUID,
    payload: HandoffUpdate,
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

    lead.is_human_mode = payload.isHuman
    lead.human_assigned_to = payload.assignedTo if payload.isHuman else None
    await db.flush()

    return {
        "lead_id": lead.id,
        "isHuman": lead.is_human_mode,
        "assignedTo": lead.human_assigned_to,
    }
