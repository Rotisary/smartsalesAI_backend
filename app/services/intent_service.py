import asyncio
import logging

from app.ai.agent import get_intent

logger = logging.getLogger(__name__)


class IntentService:

    async def detect_intent(self, message: str) -> str:
        """
        Classify the intent of a customer message.

        Returns one of: Buying | Pricing | Support | Inquiry | Complaint.
        Falls back to "Inquiry" on any error so the webhook never crashes.
        """
        try:
            return await asyncio.to_thread(get_intent, message)
        except Exception as exc:
            logger.error("Intent detection failed: %s — defaulting to Inquiry", exc)
            return "Inquiry"   # Safe fallback
