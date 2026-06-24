from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.message import Message
from app.utils.enums import Channel, LeadStatus, MessageSender


class LeadService:
    async def list_leads(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        status: Optional[LeadStatus] = None,
        channel: Optional[Channel] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Lead], int]:
        filters = [Lead.business_id == business_id]
        if status is not None:
            filters.append(Lead.status == status)
        if channel is not None:
            filters.append(Lead.channel == channel)
        if search:
            pattern = f"%{search.strip()}%"
            filters.append(or_(Lead.name.ilike(pattern), Lead.phone.ilike(pattern)))

        count_stmt = select(func.count()).select_from(Lead).where(*filters)
        total = await db.scalar(count_stmt)

        stmt = (
            select(Lead)
            .where(*filters)
            .order_by(Lead.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all()), int(total or 0)

    async def get_lead(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        lead_id: UUID,
    ) -> Lead | None:
        stmt = select(Lead).where(Lead.id == lead_id, Lead.business_id == business_id)
        return await db.scalar(stmt)

    async def get_or_create_lead(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        phone: str,
        name: Optional[str] = None,
        channel: Channel = Channel.WHATSAPP,
    ) -> Lead:
        stmt = select(Lead).where(Lead.business_id == business_id, Lead.phone == phone)
        lead = await db.scalar(stmt)
        if lead:
            if name and not lead.name:
                lead.name = name
            return lead

        lead = Lead(
            business_id=business_id,
            phone=phone,
            name=name,
            channel=channel,
        )
        db.add(lead)
        await db.flush()
        return lead

    async def update_lead(
        self,
        db: AsyncSession,
        *,
        lead: Lead,
        values: dict,
    ) -> Lead:
        for field, value in values.items():
            if value is not None:
                setattr(lead, field, value)
        await db.flush()
        return lead

    async def list_messages(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        lead_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.business_id == business_id, Message.lead_id == lead_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def message_exists(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        wa_message_id: str,
    ) -> bool:
        stmt = select(Message.id).where(
            Message.business_id == business_id,
            Message.wa_message_id == wa_message_id,
        )
        return await db.scalar(stmt) is not None

    async def save_message(
        self,
        db: AsyncSession,
        *,
        business_id: UUID,
        lead: Lead,
        sender: MessageSender,
        content: str,
        intent_tag: Optional[str] = None,
        wa_message_id: Optional[str] = None,
    ) -> Message:
        message = Message(
            business_id=business_id,
            lead_id=lead.id,
            sender=sender,
            content=content,
            intent_tag=intent_tag,
            wa_message_id=wa_message_id,
        )
        db.add(message)

        lead.last_message = content
        if sender == MessageSender.CUSTOMER:
            lead.unread_count += 1
            lead.last_customer_message_at = datetime.now(timezone.utc)
        elif sender == MessageSender.AGENT:
            lead.unread_count = 0

        await db.flush()
        return message

    async def update_lead_intent(
        self,
        db: AsyncSession,
        *,
        lead: Lead,
        intent_tag: str,
    ) -> Lead:
        """
        Updates lead score based on detected intent and derives status from score.
        
        Scoring system (from architecture revision):
        - Pricing: +10
        - Buying: +30
        - Support: +5
        - Complaint: +5
        - Inquiry: +0
        
        Status derived from score:
        - 0-19: new
        - 20-49: warm
        - 50-99: hot
        - 100+: closed
        """
        # Add intent tag to lead's intent_tags if not already present
        tags = lead.intent_tags or []
        if intent_tag not in tags:
            tags.append(intent_tag)
            lead.intent_tags = tags

        # Update lead score based on intent
        score_mapping = {
            "Pricing": 10,
            "Buying": 30,
            "Support": 5,
            "Complaint": 5,
            "Inquiry": 0,
        }
        lead.lead_score += score_mapping.get(intent_tag, 0)

        # Derive status from score
        if lead.lead_score >= 100:
            lead.status = LeadStatus.CLOSED
        elif lead.lead_score >= 50:
            lead.status = LeadStatus.HOT
        elif lead.lead_score >= 20:
            lead.status = LeadStatus.WARM
        else:
            lead.status = LeadStatus.NEW

        await db.flush()
        return lead
