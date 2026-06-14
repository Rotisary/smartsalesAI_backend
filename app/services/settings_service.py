import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
 
from app.models.settings import BusinessSettings
from app.models.business import Business

logger = logging.getLogger(__name__)
 


class SettingsHelperService:
    async def get_or_create_settings(
        db: AsyncSession,
        business: Business,
    ) -> BusinessSettings:
        """
        Fetch the settings row for this business, creating it with defaults if
        it doesn't exist yet (first-run behaviour after business creation).
        """
        result = await db.execute(
            select(BusinessSettings).where(
                BusinessSettings.business_id == business.id
            )
        )
        settings_row = result.scalar_one_or_none()
    
        if not settings_row:
            logger.info(
                "No settings row found for business %s — creating defaults", business.id
            )
            settings_row = BusinessSettings(
                business_id=business.id,
                business_name=business.name,
            )
            db.add(settings_row)
            await db.commit()
            await db.refresh(settings_row)
    
        return settings_row