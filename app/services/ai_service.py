import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ai.agent import get_reply
from app.config import settings
from app.core.context_manager import context_manager
from app.services.intent_service import IntentService
from app.services.rag_service import retrieve_context
from app.models.settings import BusinessSettings

logger = logging.getLogger(__name__)

intent_service  = IntentService()

MAX_HISTORY_TURNS = 20


class AIService:

    async def generate_reply(
        self,
        lead_id: str,
        business_id: str,
        customer_message: str,
        db: AsyncSession,
    ) -> tuple[str, str]:
        """
        Generate a WhatsApp reply and classify intent for an incoming message.

        Calls agent.get_reply() for the reply and agent.get_intent() (via
        IntentService) for the intent. Both are run in parallel where possible.
        """

        history = await context_manager.get_history(lead_id, db=db)
        history_text = self._format_history(history)

        business_settings  = await self._get_business_settings(db, business_id)
        persona_name  = business_settings.ai_persona_name
        business_name = business_settings.business_name
        tone = business_settings.ai_tone

        rag_context = await retrieve_context(
            db=db,
            business_id=uuid.UUID(business_id),
            query=customer_message,
            top_k=5,
        )
        context_chunk = rag_context or "No specific product information available yet."

        reply_coro  = asyncio.to_thread(
            get_reply,
            customer_message,
            context_chunk,
            persona_name,
            business_name,
            tone,   
            history_text, 
        )
        intent_coro = intent_service.detect_intent(customer_message)

        ai_reply, intent_tag = await asyncio.gather(reply_coro, intent_coro)

        await context_manager.append_turn(lead_id, customer_message, ai_reply)

        logger.info(
            "Reply generated for lead %s — intent=%s chars=%d",
            lead_id, intent_tag, len(ai_reply),
        )

        return ai_reply, intent_tag

    def _format_history(self, history: list[dict]) -> str:
        """
        Converts the list of {customer, ai} turn dicts from ContextManager
        into the plain-text format agent.get_reply() expects.
        """
        if not history:
            return "(No previous messages)"

        lines = []
        for turn in history[-MAX_HISTORY_TURNS:]:
            lines.append(f"Customer: {turn['customer']}")
            lines.append(f"Assistant: {turn['ai']}")
        return "\n".join(lines)

    async def _get_business_settings(
        self, db: AsyncSession, business_id: str
    ) -> BusinessSettings | None:
        """
        Load BusinessSettings for this business.
        """
        result = await db.execute(
            select(BusinessSettings).where(
                BusinessSettings.business_id == uuid.UUID(business_id)
            )
        )
        return result.scalar_one_or_none()