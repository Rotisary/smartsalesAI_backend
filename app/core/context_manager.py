import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from typing import Literal

import redis.asyncio as redis
from redis.asyncio import Redis

from app.config import settings

ConversationRole = Literal["customer", "ai", "agent", "system"]


@dataclass(frozen=True)
class ConversationMessage:
    role: ConversationRole
    content: str


class ContextManager:
    """Redis-backed short-term conversation memory.

    PostgreSQL stores the durable message history. Redis is only the fast cache
    used by the AI pipeline.
    """

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        history_ttl_seconds: int = 60 * 60 * 24,
        human_mode_ttl_seconds: int = 60 * 10,
        max_messages: int = 20,
    ) -> None:
        self.redis_url = redis_url or settings.REDIS_URL
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
        raw_history = await self.client.get(self._history_key(lead_id))
        if not raw_history:
            return []

        try:
            items = json.loads(raw_history)
        except json.JSONDecodeError:
            await self.clear_history(lead_id)
            return []

        history: list[ConversationMessage] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            role = item.get("role")
            content = item.get("content")
            if role in {"customer", "ai", "agent", "system"} and isinstance(content, str):
                history.append(ConversationMessage(role=role, content=content))
        return history

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

    async def rebuild_history(
        self,
        lead_id: str,
        messages: Sequence[ConversationMessage],
    ) -> list[ConversationMessage]:
        return await self.set_history(lead_id, messages)

    async def clear_history(self, lead_id: str) -> None:
        await self.client.delete(self._history_key(lead_id))

    async def cache_human_mode(self, lead_id: str, is_human_mode: bool) -> None:
        await self.client.setex(
            self._human_mode_key(lead_id),
            self.human_mode_ttl_seconds,
            "1" if is_human_mode else "0",
        )

    async def get_cached_human_mode(self, lead_id: str) -> bool | None:
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
