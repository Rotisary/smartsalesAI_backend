import json
import uuid
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import redis.asyncio as redis
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.message import Message
from app.utils.enums import MessageSender

ConversationRole = Literal["customer", "ai", "agent", "system"]


@dataclass(frozen=True)
class ConversationMessage:
    role: ConversationRole
    content: str


class ContextManager:
    """Redis-backed short-term conversation memory with PostgreSQL fallback.

    PostgreSQL stores the durable message history. Redis is only the fast cache
    used by the AI pipeline. When Redis cache is empty, history is rebuilt from PostgreSQL.
    """

    def __init__(
        self,
        *,
        history_ttl_seconds: int = 60 * 60 * 24,
        human_mode_ttl_seconds: int = 60 * 10,
        max_messages: int = 20,
    ) -> None:
        self.redis_url = settings.REDIS_URL
        self.history_ttl_seconds = history_ttl_seconds
        self.human_mode_ttl_seconds = human_mode_ttl_seconds
        self.max_messages = max_messages
        self._redis: Redis | None = None

    @property
    def client(self) -> Redis:
        if self._redis is None:
            self._redis = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def get_history(self, lead_id: str) -> list[ConversationMessage]:
        """Get conversation history from Redis cache, with PostgreSQL fallback."""
        raw_history = await self.client.get(self._history_key(lead_id))
        
        if raw_history:
            try:
                items = json.loads(raw_history)
                history: list[ConversationMessage] = []
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    role = item.get("role")
                    content = item.get("content")
                    if role in {"customer", "ai", "agent", "system"} and isinstance(content, str):
                        history.append(ConversationMessage(role=role, content=content))
                return history
            except json.JSONDecodeError:
                await self.clear_history(lead_id)

        # Redis cache miss - rebuild from PostgreSQL
        return await self._rebuild_history_from_postgres(lead_id)

    async def _rebuild_history_from_postgres(self, lead_id: str) -> list[ConversationMessage]:
        """Rebuild conversation history from PostgreSQL messages."""
        try:
            async with get_db() as db:
                stmt = (
                    select(Message)
                    .where(Message.lead_id == uuid.UUID(lead_id))
                    .order_by(Message.created_at.desc())
                    .limit(self.max_messages)
                )
                result = await db.execute(stmt)
                messages = result.scalars().all()

                history: list[ConversationMessage] = []
                for msg in messages:
                    # Map MessageSender enum to ConversationRole
                    role_mapping = {
                        MessageSender.CUSTOMER: "customer",
                        MessageSender.AI: "ai",
                        MessageSender.AGENT: "agent",
                    }
                    role = role_mapping.get(msg.sender, "customer")
                    history.append(ConversationMessage(role=role, content=msg.content))

                # Cache the rebuilt history in Redis
                await self.set_history(lead_id, history)
                return history

        except Exception as e:
            return []

    async def set_history(
        self,
        lead_id: str,
        messages: Sequence[ConversationMessage],
    ) -> list[ConversationMessage]:
        trimmed = list(messages)[-self.max_messages :]
        await self.client.setex(
            self._history_key(lead_id),
            self.history_ttl_seconds,
            json.dumps([asdict(message) for message in trimmed]),
        )
        return trimmed

    async def append_message(
        self,
        lead_id: str,
        *,
        role: ConversationRole,
        content: str,
    ) -> list[ConversationMessage]:
        history = await self.get_history(lead_id)
        history.append(ConversationMessage(role=role, content=content))
        return await self.set_history(lead_id, history)

    async def append_turn(
        self,
        lead_id: str,
        *,
        customer_message: str,
        ai_reply: str,
    ) -> list[ConversationMessage]:
        history = await self.get_history(lead_id)
        history.extend(
            [
                ConversationMessage(role="customer", content=customer_message),
                ConversationMessage(role="ai", content=ai_reply),
            ]
        )
        return await self.set_history(lead_id, history)

    # async def rebuild_history(
    #     self,
    #     lead_id: str,
    #     messages: Sequence[ConversationMessage],
    # ) -> list[ConversationMessage]:
    #     return await self.set_history(lead_id, messages)

    async def clear_history(self, lead_id: str) -> None:
        await self.client.delete(self._history_key(lead_id))

    async def cache_human_mode(self, lead_id: str, is_human_mode: bool) -> None:
        await self.client.setex(
            self._human_mode_key(lead_id),
            self.human_mode_ttl_seconds,
            "1" if is_human_mode else "0",
        )

    async def is_human_mode(self, lead_id: str) -> bool | None:
        value = await self.client.get(self._human_mode_key(lead_id))
        if value is None:
            return None
        return value == "1"

    async def clear_human_mode_cache(self, lead_id: str) -> None:
        await self.client.delete(self._human_mode_key(lead_id))

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None

    @staticmethod
    def _history_key(lead_id: str) -> str:
        return f"conversation_history:{lead_id}"

    @staticmethod
    def _human_mode_key(lead_id: str) -> str:
        return f"human_mode:{lead_id}"


context_manager = ContextManager()
