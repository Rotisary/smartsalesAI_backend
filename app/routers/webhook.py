import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.whatsapp_connection import WhatsAppConnection
from app.tasks.ai_tasks import process_message_task
from app.services.lead_service import LeadService
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/webhook", tags=["Webhook"])
lead_service = LeadService()
whatsapp_service = WhatsAppService()
logger = logging.getLogger(__name__)


@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Webhook verification failed",
    )


@router.post("/whatsapp")
async def receive_whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    payload = await request.json()
    queued_messages = 0
    duplicate_messages = 0
    ignored_messages = 0

    for event in _iter_whatsapp_events(payload):
        value = event.get("value", {})
        metadata = value.get("metadata", {})
        phone_number_id = metadata.get("phone_number_id")
        if not phone_number_id:
            ignored_messages += 1
            continue

        connection = await db.get(WhatsAppConnection, str(phone_number_id))
        if not connection or connection.status != "connected":
            ignored_messages += 1
            continue

        contacts_by_phone = _contacts_by_phone(value.get("contacts", []))
        messages = value.get("messages", [])
        if not isinstance(messages, list):
            ignored_messages += 1
            continue

        for message_data in messages:
            if not isinstance(message_data, dict):
                ignored_messages += 1
                continue

            wa_message_id = message_data.get("id")
            sender_phone = message_data.get("from")
            if not wa_message_id or not sender_phone:
                ignored_messages += 1
                continue

            if await lead_service.message_exists(
                db,
                business_id=connection.business_id,
                wa_message_id=str(wa_message_id),
            ):
                duplicate_messages += 1
                continue

            process_message_task.delay(
                message_data,
                business_id=str(connection.business_id),
                contacts_by_phone=contacts_by_phone,
                customer_name=contacts_by_phone.get(sender_phone, "Customer"),
            )
            queued_messages += 1

    return {
        "status": "ok",
        "queued_messages": queued_messages,
        "duplicate_messages": duplicate_messages,
        "ignored_messages": ignored_messages,
    }


def _iter_whatsapp_events(payload: dict[str, Any]) -> list[dict[str, Any]]:
    entries = payload.get("entry", [])
    if not isinstance(entries, list):
        return []

    events: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        changes = entry.get("changes", [])
        if not isinstance(changes, list):
            continue
        for change in changes:
            if isinstance(change, dict):
                events.append(change)
    return events


def _contacts_by_phone(contacts: list[Any]) -> dict[str, str]:
    names_by_phone: dict[str, str] = {}
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        phone = contact.get("wa_id")
        profile = contact.get("profile", {})
        name = profile.get("name") if isinstance(profile, dict) else None
        if phone and name:
            names_by_phone[str(phone)] = str(name)
    return names_by_phone
