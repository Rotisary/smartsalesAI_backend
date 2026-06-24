from asyncio.log import logger
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.database import engine
from app.core.exceptions.whatsapp import WhatsAppAPIError, WhatsAppConfigurationError
from app.core.context_manager import context_manager
from app.core.socket_manager import socket_manager
from app.services.lead_service import LeadService
from app.services.whatsapp_service import WhatsAppService
from app.utils.enums import Channel, MessageSender
from app.services.ai_service import AIService


import uuid

class WebhookService:

    def __init__(self, phone_number_id: str):
        self.lead_service = LeadService()
        self.whatsapp_service = WhatsAppService()
        self.ai_service = AIService()
        self.logger = logging.getLogger(__name__)
        self.phone_number_id = phone_number_id

    @staticmethod
    def _make_session() -> AsyncSession:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        return factory()

    async def process_message(
        self,
        message_data: dict[str, Any],
        *,
        business_id: uuid.UUID,
        contacts_by_phone: dict[str, str],
        customer_name: str,
    ) -> dict:
        """
        Async wrapper for AI message processing.
        """
        async with WebhookService._make_session() as db:
            try:
                message_text = await self._extract_message_text(message_data)
                if not message_text:
                    return {"status": "failed", "detail": "unsupported message type"}
                sender_phone = message_data.get("from")

                lead = await self.lead_service.get_or_create_lead(
                    db,
                    business_id=business_id,
                    phone=str(sender_phone),
                    name=contacts_by_phone.get(str(sender_phone)),
                    channel=Channel.WHATSAPP.value,
                )

                if await context_manager.is_human_mode(str(lead.id), db=db):
                    await self.lead_service.save_message(
                        db=db,
                        lead=lead,
                        sender=MessageSender.CUSTOMER.value,
                        content=message_text,
                        wa_message_id=message_data.get("id"),
                        business_id=business_id,
                    )
                    await socket_manager.emit_new_message(lead, "", message_text)
                    return {"status": "ok"}
                
                saved = await self.lead_service.save_message(
                    db,
                    business_id=business_id,
                    lead=lead,
                    sender=MessageSender.CUSTOMER.value,
                    content=message_text,
                    wa_message_id=str(message_data.get("id")),
                )
                ai_reply, intent_tag = await self.ai_service.generate_reply(
                    lead_id=str(lead.id),
                    business_id=str(business_id),
                    customer_message=message_text,
                    customer_name=customer_name,
                    db=db,
                )

                await self.lead_service.save_message(
                    db=db,
                    lead_id=lead.id,
                    sender=MessageSender.AI.value,
                    content=ai_reply,
                    intent_tag=intent_tag,
                    business_id=business_id,
                )
                updated_lead = await self.lead_service.update_lead_intent(db, lead=lead.id, intent_tag=intent_tag)

                try:
                    await self.whatsapp_service.send_text(
                        to=sender_phone,
                        message=ai_reply,
                        phone_number_id=self.phone_number_id,
                    )
                except (WhatsAppAPIError, WhatsAppConfigurationError) as exc:
                    logger.exception("whatsapp gateway error %s", exc)

                lead_for_emit = updated_lead or lead
                await socket_manager.emit_new_message(lead_for_emit, ai_reply, message_text)
                await socket_manager.emit_lead_updated(lead_for_emit)
            except Exception as exc:
                logger.exception("Unhandled error in webhook handler: %s", exc)
            
            return {"status": "ok"}   

    async def _extract_message_text(self, message_data: dict[str, Any]) -> str | None:
        message_type = message_data.get("type")
        if message_type == "text":
            text = message_data.get("text", {})
            body = text.get("body") if isinstance(text, dict) else None
            return str(body).strip() if body else None

        if message_type == "button":
            button = message_data.get("button", {})
            text = button.get("text") if isinstance(button, dict) else None
            return str(text).strip() if text else None
        
        await self.whatsapp_service.send_text(
            to=message_data.get("from"),
            message="Sorry, I can't process this type of message at the moment. 🙏",
            phone_number_id=self.phone_number_id,
        )
        return None