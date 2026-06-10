from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_business
from app.core.exceptions.whatsapp import WhatsAppAPIError, WhatsAppConfigurationError
from app.database import get_db
from app.models.business import Business
from app.schemas.whatsapp import ConnectWhatsAppRequest, ConnectWhatsAppResponse
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])
whatsapp_service = WhatsAppService()


@router.post("/connect", response_model=ConnectWhatsAppResponse)
async def connect_whatsapp(
    payload: ConnectWhatsAppRequest,
    db: AsyncSession = Depends(get_db),
    current_business: Business = Depends(get_current_business),
):
    try:
        return await whatsapp_service.connect_embedded_signup(
            db,
            current_business,
            payload,
        )
    except WhatsAppConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except WhatsAppAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
