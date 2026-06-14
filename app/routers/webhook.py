import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.context_manager import context_manager
from app.database import get_db
from app.models.whatsapp_connection import WhatsAppConnection
from app.services.lead_service import LeadService
from app.utils.enums import Channel, MessageSender

router = APIRouter(prefix="/webhook", tags=["Webhook"])
lead_service = LeadService()
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
    processed_messages = 0
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

            message_text = _extract_message_text(message_data)
            if message_text is None:
                message_text = _unsupported_message_text(message_data)

            lead = await lead_service.get_or_create_lead(
                db,
                business_id=connection.business_id,
                phone=str(sender_phone),
                name=contacts_by_phone.get(str(sender_phone)),
                channel=Channel.WHATSAPP,
            )
            await lead_service.save_message(
                db,
                business_id=connection.business_id,
                lead=lead,
                sender=MessageSender.CUSTOMER,
                content=message_text,
                wa_message_id=str(wa_message_id),
            )
            try:
                await context_manager.append_message(
                    str(lead.id),
                    role="customer",
                    content=message_text,
                )
            except Exception:
                logger.exception("Failed to cache WhatsApp conversation context")
            processed_messages += 1

    return {
        "status": "ok",
        "processed_messages": processed_messages,
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


def _extract_message_text(message_data: dict[str, Any]) -> str | None:
    message_type = message_data.get("type")
    if message_type == "text":
        text = message_data.get("text", {})
        body = text.get("body") if isinstance(text, dict) else None
        return str(body).strip() if body else None

    if message_type == "button":
        button = message_data.get("button", {})
        text = button.get("text") if isinstance(button, dict) else None
        return str(text).strip() if text else None

    if message_type == "interactive":
        interactive = message_data.get("interactive", {})
        if not isinstance(interactive, dict):
            return None
        button_reply = interactive.get("button_reply", {})
        list_reply = interactive.get("list_reply", {})
        if isinstance(button_reply, dict) and button_reply.get("title"):
            return str(button_reply["title"]).strip()
        if isinstance(list_reply, dict) and list_reply.get("title"):
            return str(list_reply["title"]).strip()

    return None


def _unsupported_message_text(message_data: dict[str, Any]) -> str:
    message_type = str(message_data.get("type") or "unknown")
    return f"[Unsupported WhatsApp message type: {message_type}]"
