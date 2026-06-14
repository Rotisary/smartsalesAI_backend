import logging
 
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
 
from app.database import get_db
from app.models.settings import BusinessSettings
from app.models.business import Business
from app.schemas.settings import BusinessSettingsRead, BusinessSettingsUpdate
from app.services.settings_service import SettingsHelperService
from app.core.dependencies import get_current_business
 
logger = logging.getLogger(__name__)
 
router = APIRouter(prefix="/api/settings", tags=["Settings"])
 
 
@router.get("/", response_model=BusinessSettingsRead)
async def get_settings(
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    settings_row = await SettingsHelperService().get_or_create_settings(db, business)
    return BusinessSettingsRead.model_validate(settings_row)
 
 
@router.put("/", response_model=BusinessSettingsRead)
async def update_settings(
    body: BusinessSettingsUpdate,
    business: Business = Depends(get_current_business),
    db: AsyncSession = Depends(get_db),
):
    settings_row = await SettingsHelperService().get_or_create_settings(db, business)
 
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request body is empty — nothing to update.",
        )
 
    for field, value in updates.items():
        setattr(settings_row, field, value)
 
    await db.commit()
    await db.refresh(settings_row)
 
    logger.info(
        "Settings updated for business %s — fields changed: %s",
        business.id,
        list(updates.keys()),
    )
 
    return BusinessSettingsRead.model_validate(settings_row)