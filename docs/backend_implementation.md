# SmartSales AI — FastAPI Backend Full Implementation Guide

> **Stack:** Python · FastAPI · Google Gemini · WhatsApp Cloud API · Socket.IO · PostgreSQL · Redis  
> **Read top to bottom. Build in the order presented.**

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Project Setup](#part-1--project-setup)
3. [Database Models](#part-2--database-models)
4. [WhatsApp Cloud API Integration](#part-3--whatsapp-cloud-api-integration)
5. [Google Gemini AI Service](#part-4--google-gemini-ai-service)
6. [Conversation Context Manager](#part-5--conversation-context-manager)
7. [Lead Service](#part-6--lead-service)
8. [REST API Endpoints](#part-7--rest-api-endpoints)
9. [Socket.IO Real-Time Server](#part-8--socketio-real-time-server)
10. [Database Setup & Migrations](#part-9--database-setup--migrations)
11. [Pydantic Schemas](#part-10--pydantic-schemas)
12. [WhatsApp Cloud API Setup (Meta)](#part-11--whatsapp-cloud-api-setup-meta)
13. [Human Handoff Flow](#part-12--human-handoff-flow)
14. [Environment Configurations](#part-13--environment-specific-configurations)
15. [API Endpoint Reference](#part-14--api-endpoint-reference)
16. [Build Order Checklist](#part-15--build-order-checklist)
17. [Engineer Notes](#notes-for-the-engineer)

---

## Architecture Overview

```
WhatsApp Cloud API
        │
        ▼ (webhook POST)
┌──────────────────────────────────────────────┐
│              FastAPI Backend                 │
│                                              │
│  ┌────────────┐    ┌─────────────────────┐   │
│  │  Webhook   │───▶│  AI Pipeline        │   │
│  │  Handler   │    │  (Gemini Pro)       │   │
│  └────────────┘    └──────────┬──────────┘   │
│                               │              │
│  ┌────────────┐    ┌──────────▼──────────┐   │
│  │  REST API  │    │  Context Manager    │   │
│  │  Endpoints │    │  (Redis)            │   │
│  └────────────┘    └──────────┬──────────┘   │
│                               │              │
│  ┌────────────────────────────▼──────────┐   │
│  │         PostgreSQL Database           │   │
│  │  leads · messages · sales · settings  │   │
│  └───────────────────────────────────────┘   │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │       Socket.IO Server                 │  │
│  │  (real-time push to Next.js frontend)  │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
        │
        ▼
  Next.js Frontend
```

**Request Flow Summary:**

1. Customer sends WhatsApp message → Meta Cloud API delivers it to your webhook
2. Webhook handler extracts the message and upserts the lead in PostgreSQL
3. AI Service loads conversation history from Redis and calls Gemini Pro
4. Gemini generates a reply; Intent Service (Gemini Flash) classifies the message
5. Reply is saved to DB, sent back via WhatsApp API, and pushed to the frontend via Socket.IO

---

## PART 1 — Project Setup

### 1.1 Folder Structure

Create this exact structure before writing any code:

```
smartsales-backend/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── config.py                # Environment config (Pydantic Settings)
│   ├── database.py              # DB connection + session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── lead.py
│   │   ├── message.py
│   │   ├── sale.py
│   │   └── settings.py
│   ├── schemas/
│   │   ├── lead.py
│   │   ├── message.py
│   │   ├── sale.py
│   │   └── settings.py
│   ├── routers/
│   │   ├── webhook.py           # WhatsApp webhook endpoint
│   │   ├── leads.py
│   │   ├── messages.py
│   │   ├── sales.py
│   │   ├── analytics.py
│   │   └── settings.py
│   ├── services/
│   │   ├── ai_service.py        # Gemini integration
│   │   ├── whatsapp_service.py  # Send messages via Meta API
│   │   ├── lead_service.py      # Lead lifecycle logic
│   │   └── intent_service.py    # Intent detection
│   ├── core/
│   │   ├── socket_manager.py    # Socket.IO server
│   │   └── context_manager.py  # Conversation memory (Redis)
│   └── utils/
│       ├── formatters.py
│       └── validators.py
├── alembic/                     # DB migrations
├── tests/
├── .env
├── requirements.txt
└── Dockerfile
```

### 1.2 Install Dependencies

```bash
pip install \
  fastapi==0.111.0 \
  uvicorn[standard]==0.30.0 \
  python-socketio==5.11.2 \
  google-generativeai==0.7.2 \
  httpx==0.27.0 \
  sqlalchemy==2.0.30 \
  alembic==1.13.1 \
  asyncpg==0.29.0 \
  psycopg2-binary==2.9.9 \
  redis==5.0.4 \
  pydantic==2.7.1 \
  pydantic-settings==2.3.0 \
  python-dotenv==1.0.1 \
  python-multipart==0.0.9 \
  tenacity==8.3.0
```

Save all versions to `requirements.txt` so your environment is reproducible.

### 1.3 Environment Variables

Create `.env` at the project root:

```env
# App
APP_ENV=development
SECRET_KEY=your_secret_key_here
FRONTEND_URL=http://localhost:3000

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/smartsales

# Redis (conversation context cache)
REDIS_URL=redis://localhost:6379

# Google Gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-pro

# WhatsApp Cloud API (Meta)
WHATSAPP_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_ACCESS_TOKEN=your_permanent_access_token
WHATSAPP_VERIFY_TOKEN=your_custom_verify_token
WHATSAPP_API_VERSION=v19.0

# Business defaults
DEFAULT_AI_PERSONA_NAME=Aria
DEFAULT_BUSINESS_NAME=Acme Store
```

> **Security note:** Never commit `.env` to version control. Add it to `.gitignore`.

### 1.4 Config — `app/config.py`

Pydantic Settings reads directly from the `.env` file and validates all values at startup:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_ENV: str = "development"
    SECRET_KEY: str
    FRONTEND_URL: str = "http://localhost:3000"

    DATABASE_URL: str
    REDIS_URL: str

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-1.5-pro"

    WHATSAPP_PHONE_NUMBER_ID: str
    WHATSAPP_ACCESS_TOKEN: str
    WHATSAPP_VERIFY_TOKEN: str
    WHATSAPP_API_VERSION: str = "v19.0"

    DEFAULT_AI_PERSONA_NAME: str = "Aria"
    DEFAULT_BUSINESS_NAME: str = "Acme Store"

    class Config:
        env_file = ".env"

settings = Settings()
```

> Import `settings` from this module everywhere you need env vars. Never call `os.environ` directly.

---

## PART 2 — Database Models

All models extend `Base` from `app/database.py` (see Part 9). They map directly to PostgreSQL tables.

### 2.1 Lead Model — `app/models/lead.py`

```python
from sqlalchemy import Column, String, Integer, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.database import Base
import uuid, datetime

class Lead(Base):
    __tablename__ = "leads"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name          = Column(String, nullable=True)
    phone         = Column(String, unique=True, nullable=False)
    channel       = Column(
                      SAEnum("whatsapp", "instagram", "web", name="channel_enum"),
                      default="whatsapp"
                    )
    status        = Column(
                      SAEnum("new", "hot", "warm", "closed", "lost", name="lead_status_enum"),
                      default="new"
                    )
    intent_tags   = Column(ARRAY(String), default=[])
    unread_count  = Column(Integer, default=0)
    last_message  = Column(String, nullable=True)
    created_at    = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at    = Column(
                      DateTime,
                      default=datetime.datetime.utcnow,
                      onupdate=datetime.datetime.utcnow
                    )
```

**Key design decisions:**

- `phone` is `unique=True` — used as the natural key for WhatsApp leads.
- `intent_tags` is a PostgreSQL `ARRAY` — stores all detected intents across the conversation.
- `status` auto-upgrades based on intent (handled in `LeadService`).

### 2.2 Message Model — `app/models/message.py`

```python
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid, datetime

class Message(Base):
    __tablename__ = "messages"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id        = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    sender         = Column(
                       SAEnum("customer", "ai", "agent", name="sender_enum"),
                       nullable=False
                     )
    content        = Column(String, nullable=False)
    intent_tag     = Column(String, nullable=True)
    wa_message_id  = Column(String, nullable=True)  # WhatsApp ID for deduplication
    created_at     = Column(DateTime, default=datetime.datetime.utcnow)
```

> `wa_message_id` is critical. Meta sometimes re-delivers webhooks. Always check this field before saving.

### 2.3 Sale Model — `app/models/sale.py`

```python
from sqlalchemy import Column, String, DateTime, Numeric, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid, datetime

class Sale(Base):
    __tablename__ = "sales"

    id        = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id   = Column(UUID(as_uuid=True), ForeignKey("leads.id"), nullable=True)
    customer  = Column(String, nullable=False)
    product   = Column(String, nullable=False)
    amount    = Column(Numeric(12, 2), nullable=False)
    status    = Column(
                  SAEnum("completed", "pending", "refunded", name="sale_status_enum"),
                  default="pending"
                )
    date      = Column(DateTime, default=datetime.datetime.utcnow)
    channel   = Column(
                  SAEnum("whatsapp", "instagram", "web", name="sale_channel_enum"),
                  default="whatsapp"
                )
```

### 2.4 Business Settings Model — `app/models/settings.py`

```python
from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid

class BusinessSettings(Base):
    __tablename__ = "business_settings"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_name         = Column(String, default="Acme Store")
    ai_persona_name       = Column(String, default="Aria")
    ai_tone               = Column(String, default="Friendly")  # Friendly | Professional | Casual
    knowledge_base        = Column(Text, default="")
    auto_followup         = Column(Boolean, default=True)
    human_handoff_trigger = Column(Boolean, default=True)
```

> The `knowledge_base` field is the core of the AI's product knowledge. Clients paste their full price list, FAQs, and product descriptions here via the Settings page.

---

## PART 3 — WhatsApp Cloud API Integration

### 3.1 How WhatsApp Webhooks Work

Meta delivers messages to your endpoint in this flow:

1. **Verification (GET):** When you register the webhook URL in the Meta Developer Portal, Meta sends a GET request with your verify token. Your endpoint must echo back the challenge string.
2. **Message delivery (POST):** Every incoming WhatsApp message is POSTed to your endpoint as JSON.

### 3.2 Webhook Router — `app/routers/webhook.py`

```python
from fastapi import APIRouter, Request, Response, HTTPException, Query
from app.config import settings
from app.services.whatsapp_service import WhatsAppService
from app.services.ai_service import AIService
from app.services.lead_service import LeadService
from app.core.socket_manager import socket_manager
from app.core.context_manager import ContextManager

router = APIRouter(prefix="/webhook", tags=["Webhook"])
whatsapp        = WhatsAppService()
ai_service      = AIService()
lead_service    = LeadService()
context_manager = ContextManager()


# ── STEP 1: Webhook Verification (GET) ────────────────────────────────────────
@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str         = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str    = Query(alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return Response(content=hub_challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")


# ── STEP 2: Receive Incoming Messages (POST) ──────────────────────────────────
@router.post("/whatsapp")
async def receive_message(request: Request):
    body = await request.json()

    try:
        entry    = body["entry"][0]
        changes  = entry["changes"][0]["value"]

        # Meta also sends delivery receipts, read receipts, etc.
        # Only process actual messages.
        if "messages" not in changes:
            return {"status": "ok"}

        message_data  = changes["messages"][0]
        contact       = changes["contacts"][0]

        wa_message_id = message_data["id"]
        phone         = message_data["from"]          # e.g. "2348012345678"
        message_type  = message_data["type"]          # "text", "image", "audio", etc.
        customer_name = contact["profile"]["name"]

        # Only handle text messages for now; gracefully reject others
        if message_type != "text":
            await whatsapp.send_text(
                phone,
                "Sorry, I can only process text messages at the moment. 🙏"
            )
            return {"status": "ok"}

        incoming_text = message_data["text"]["body"]

        # 1. Upsert lead in DB
        lead = await lead_service.get_or_create_lead(
            phone=phone,
            name=customer_name,
            channel="whatsapp"
        )

        # 2. Check if a human agent has taken over this conversation
        if await context_manager.is_human_mode(str(lead.id)):
            await lead_service.save_message(
                lead_id=lead.id,
                sender="customer",
                content=incoming_text,
                wa_message_id=wa_message_id,
            )
            await socket_manager.emit_new_message(lead, "", incoming_text)
            return {"status": "ok"}

        # 3. Save customer message to DB
        await lead_service.save_message(
            lead_id=lead.id,
            sender="customer",
            content=incoming_text,
            wa_message_id=wa_message_id,
        )

        # 4. Generate AI reply
        ai_reply, intent_tag = await ai_service.generate_reply(
            lead_id=str(lead.id),
            customer_message=incoming_text,
            customer_name=customer_name,
        )

        # 5. Save AI reply to DB
        await lead_service.save_message(
            lead_id=lead.id,
            sender="ai",
            content=ai_reply,
            intent_tag=intent_tag,
        )

        # 6. Update lead status based on detected intent
        await lead_service.update_lead_intent(lead.id, intent_tag)

        # 7. Send AI reply back to WhatsApp
        await whatsapp.send_text(phone, ai_reply)

        # 8. Push real-time update to the dashboard
        await socket_manager.emit_new_message(lead, ai_reply, incoming_text)

    except (KeyError, IndexError):
        # Malformed payload — return 200 to prevent Meta from retrying indefinitely
        pass

    return {"status": "ok"}
```

> **Always return 200.** If you return any non-200 status, Meta will retry the webhook delivery repeatedly, flooding your endpoint.

### 3.3 WhatsApp Service — `app/services/whatsapp_service.py`

```python
import httpx
from app.config import settings


class WhatsAppService:
    BASE_URL = "https://graph.facebook.com/{version}/{phone_id}/messages"

    def __init__(self):
        self.url = self.BASE_URL.format(
            version=settings.WHATSAPP_API_VERSION,
            phone_id=settings.WHATSAPP_PHONE_NUMBER_ID,
        )
        self.headers = {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

    async def send_text(self, to: str, message: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": message},
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()

    async def send_interactive_buttons(
        self, to: str, body: str, buttons: list[str]
    ) -> dict:
        """
        Send quick-reply buttons.
        WhatsApp spec allows a maximum of 3 buttons per message.
        """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": f"btn_{i}", "title": btn}
                        }
                        for i, btn in enumerate(buttons[:3])
                    ]
                },
            },
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(self.url, json=payload, headers=self.headers)
            response.raise_for_status()
            return response.json()
```

---

## PART 4 — Google Gemini AI Service

This is the core intelligence layer. Every incoming message is processed through a structured prompt pipeline before Gemini generates a reply.

### 4.1 Model Choice Strategy

| Model              | Use Case              | Why                              |
| ------------------ | --------------------- | -------------------------------- |
| `gemini-1.5-pro`   | Full reply generation | Higher quality, richer reasoning |
| `gemini-1.5-flash` | Intent classification | Faster, ~70% cheaper per call    |

Using Flash for intent classification reduces your cost per message significantly.

### 4.2 AI Service — `app/services/ai_service.py`

```python
import google.generativeai as genai
from app.config import settings
from app.core.context_manager import ContextManager
from app.services.intent_service import IntentService

genai.configure(api_key=settings.GEMINI_API_KEY)

context_manager = ContextManager()
intent_service  = IntentService()


class AIService:

    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            generation_config={
                "temperature": 0.7,
                "top_p": 0.9,
                "max_output_tokens": 512,
            },
        )

    async def generate_reply(
        self,
        lead_id: str,
        customer_message: str,
        customer_name: str,
    ) -> tuple[str, str]:
        """
        Generates an AI reply for an incoming customer message.
        Returns: (ai_reply_text, intent_tag)
        """

        # 1. Load conversation history from Redis
        history = await context_manager.get_history(lead_id)

        # 2. Load the business knowledge base
        kb = await self._get_knowledge_base()

        # 3. Build the system prompt
        system_prompt = self._build_system_prompt(kb, customer_name)

        # 4. Build full chat history in Gemini's expected format
        contents = self._build_contents(history, customer_message)

        # 5. Call Gemini Pro for the reply
        response = self.model.generate_content(
            contents=[
                {"role": "user", "parts": [system_prompt]},
                *contents
            ],
        )
        ai_reply = response.text.strip()

        # 6. Detect intent with Gemini Flash (separate, cheaper call)
        intent_tag = await intent_service.detect_intent(customer_message)

        # 7. Save this turn to Redis for the next round
        await context_manager.add_turn(lead_id, customer_message, ai_reply)

        return ai_reply, intent_tag

    def _build_system_prompt(self, knowledge_base: str, customer_name: str) -> str:
        persona_name  = settings.DEFAULT_AI_PERSONA_NAME
        business_name = settings.DEFAULT_BUSINESS_NAME

        return f"""
You are {persona_name}, a friendly and professional AI sales assistant for {business_name}.
Your job is to help customers with their inquiries, guide them toward making a purchase,
answer product questions, share pricing, and close sales — all via WhatsApp chat.

CUSTOMER NAME: {customer_name}

BUSINESS KNOWLEDGE BASE:
{knowledge_base if knowledge_base else "No specific product information provided yet. Use general helpful responses."}

RULES:
1. Keep replies SHORT — max 3 sentences or 60 words. WhatsApp users dislike long messages.
2. Always be warm, helpful, and focused on moving the customer toward a purchase.
3. If asked about pricing, give it clearly and add a value statement.
4. If a customer seems frustrated, acknowledge their concern first before problem-solving.
5. Never make up product details not in the knowledge base. Say "Let me check on that for you."
6. End responses with a soft question to keep the conversation going when appropriate.
7. Use Nigerian informal style when the customer writes in pidgin or casual tone.
8. Never break character or mention that you are an AI unless directly asked.
9. If a customer asks to speak with a human, reply: "Sure! I'll connect you with a team member right away. Please hold on a moment. 🙏"
""".strip()

    def _build_contents(
        self,
        history: list[dict],
        current_message: str
    ) -> list[dict]:
        """
        Formats conversation history into Gemini's alternating user/model format.
        Caps at last 10 turns to keep latency and cost predictable.
        """
        contents = []
        for turn in history[-10:]:
            contents.append({"role": "user",  "parts": [turn["customer"]]})
            contents.append({"role": "model", "parts": [turn["ai"]]})
        contents.append({"role": "user", "parts": [current_message]})
        return contents

    async def _get_knowledge_base(self) -> str:
        """
        TODO: Replace with a real DB lookup per business account.
        Currently returns empty string; the Settings API populates this field.
        """
        return ""
```

### 4.3 Intent Detection Service — `app/services/intent_service.py`

Runs as a fast, separate Gemini Flash call to classify the customer's intent:

```python
import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)

VALID_INTENTS = ["Buying", "Pricing", "Support", "Inquiry", "Complaint"]

INTENT_PROMPT = """
Classify the customer message below into EXACTLY ONE of these categories:
Buying | Pricing | Support | Inquiry | Complaint

Reply with ONLY the single category word. Nothing else.

Customer message: "{message}"
"""


class IntentService:

    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.0,
                "max_output_tokens": 10
            },
        )

    async def detect_intent(self, message: str) -> str:
        prompt = INTENT_PROMPT.format(message=message)
        try:
            response = self.model.generate_content(prompt)
            intent = response.text.strip()
            return intent if intent in VALID_INTENTS else "Inquiry"
        except Exception:
            return "Inquiry"   # Safe fallback
```

---

## PART 5 — Conversation Context Manager

Gemini has no memory between API calls. The Context Manager stores conversation turns in Redis so the AI has the full history on every request.

### 5.1 Context Manager — `app/core/context_manager.py`

```python
import json
import redis.asyncio as aioredis
from app.config import settings

MAX_HISTORY_TURNS = 20   # Store last 20 turns per conversation


class ContextManager:

    def __init__(self):
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

    def _conv_key(self, lead_id: str) -> str:
        return f"conversation:{lead_id}"

    def _human_mode_key(self, lead_id: str) -> str:
        return f"human_mode:{lead_id}"

    # ── Conversation History ───────────────────────────────────────────────────

    async def get_history(self, lead_id: str) -> list[dict]:
        """Returns list of {customer: str, ai: str} dicts."""
        raw = await self.redis.get(self._conv_key(lead_id))
        if not raw:
            return []
        return json.loads(raw)

    async def add_turn(self, lead_id: str, customer_message: str, ai_reply: str):
        history = await self.get_history(lead_id)
        history.append({"customer": customer_message, "ai": ai_reply})
        history = history[-MAX_HISTORY_TURNS:]     # Trim to last N turns
        await self.redis.setex(
            self._conv_key(lead_id),
            86400,                                 # Expire after 24h of inactivity
            json.dumps(history),
        )

    async def clear_history(self, lead_id: str):
        await self.redis.delete(self._conv_key(lead_id))

    # ── Human Handoff Mode ─────────────────────────────────────────────────────

    async def set_human_mode(self, lead_id: str, is_human: bool):
        key = self._human_mode_key(lead_id)
        if is_human:
            await self.redis.set(key, "1", ex=3600)   # Auto-expire after 1 hour
        else:
            await self.redis.delete(key)

    async def is_human_mode(self, lead_id: str) -> bool:
        return await self.redis.exists(self._human_mode_key(lead_id)) == 1
```

**Why Redis (not PostgreSQL) for context?**

- Redis `GET`/`SET` is sub-millisecond; adding DB round-trips to every AI call would significantly increase latency.
- Conversation context is ephemeral by design — 24h TTL means stale sessions expire automatically without cleanup jobs.
- Redis pipelines allow batching if you later parallelize multiple AI calls.

---

## PART 6 — Lead Service

### 6.1 Lead Service — `app/services/lead_service.py`

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.lead import Lead
from app.models.message import Message
from app.database import get_db
import uuid


class LeadService:

    async def get_or_create_lead(
        self,
        phone: str,
        name: str,
        channel: str = "whatsapp",
    ) -> Lead:
        """
        Looks up a lead by phone number. Creates one if it doesn't exist.
        Also fills in the name if it was missing on previous contacts.
        """
        async with get_db() as db:
            result = await db.execute(select(Lead).where(Lead.phone == phone))
            lead = result.scalar_one_or_none()

            if not lead:
                lead = Lead(phone=phone, name=name, channel=channel, status="new")
                db.add(lead)
                await db.commit()
                await db.refresh(lead)
            elif not lead.name and name:
                lead.name = name
                await db.commit()

            return lead

    async def save_message(
        self,
        lead_id: uuid.UUID,
        sender: str,
        content: str,
        intent_tag: str | None = None,
        wa_message_id: str | None = None,
    ) -> Message | None:
        """
        Saves a message to the database with deduplication via wa_message_id.
        Also updates the lead's last_message preview and unread_count.
        """
        async with get_db() as db:

            # Deduplicate by WhatsApp message ID
            if wa_message_id:
                existing = await db.execute(
                    select(Message).where(Message.wa_message_id == wa_message_id)
                )
                if existing.scalar_one_or_none():
                    return None   # Already processed, skip silently

            message = Message(
                lead_id=lead_id,
                sender=sender,
                content=content,
                intent_tag=intent_tag,
                wa_message_id=wa_message_id,
            )
            db.add(message)

            # Keep lead's last_message preview current
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if lead:
                lead.last_message = content
                if sender == "customer":
                    lead.unread_count = (lead.unread_count or 0) + 1

            await db.commit()
            await db.refresh(message)
            return message

    async def update_lead_intent(self, lead_id: uuid.UUID, intent_tag: str):
        """
        Appends the new intent to the lead's tag list (no duplicates)
        and auto-upgrades the lead status based on intent signals.

        Upgrade logic:
          "Buying"  + status "new"  → "hot"
          "Pricing" + status "new"  → "warm"
        """
        async with get_db() as db:
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if lead:
                tags = lead.intent_tags or []
                if intent_tag not in tags:
                    tags.append(intent_tag)
                lead.intent_tags = tags

                if intent_tag == "Buying" and lead.status == "new":
                    lead.status = "hot"
                elif intent_tag == "Pricing" and lead.status == "new":
                    lead.status = "warm"

                await db.commit()
```

---

## PART 7 — REST API Endpoints

### 7.1 Leads Router — `app/routers/leads.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.models.lead import Lead
from app.database import get_db
from app.schemas.lead import LeadOut, LeadUpdate

router = APIRouter(prefix="/api/leads", tags=["Leads"])


@router.get("/", response_model=list[LeadOut])
async def list_leads(
    channel: str | None = None,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Returns all leads, newest first.
    Supports optional filtering by channel and/or status.
    """
    query = select(Lead).order_by(desc(Lead.updated_at))
    if channel:
        query = query.where(Lead.channel == channel)
    if status:
        query = query.where(Lead.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{lead_id}", response_model=LeadOut)
async def get_lead(lead_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.patch("/{lead_id}", response_model=LeadOut)
async def update_lead(
    lead_id: str,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Partial update — agents can change name, status, or reset unread_count.
    """
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lead, field, value)
    await db.commit()
    await db.refresh(lead)
    return lead
```

### 7.2 Messages Router — `app/routers/messages.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, asc
from app.models.message import Message
from app.models.lead import Lead
from app.database import get_db
from app.schemas.message import MessageOut, AgentMessageIn
from app.services.whatsapp_service import WhatsAppService
from app.services.lead_service import LeadService
from app.core.context_manager import ContextManager

router = APIRouter(prefix="/api/messages", tags=["Messages"])
whatsapp        = WhatsAppService()
lead_service    = LeadService()
context_manager = ContextManager()


@router.get("/{lead_id}", response_model=list[MessageOut])
async def get_messages(lead_id: str, db: AsyncSession = Depends(get_db)):
    """Returns all messages for a conversation in chronological order."""
    result = await db.execute(
        select(Message)
        .where(Message.lead_id == lead_id)
        .order_by(asc(Message.created_at))
    )
    return result.scalars().all()


@router.post("/{lead_id}/agent-reply")
async def agent_reply(
    lead_id: str,
    body: AgentMessageIn,
    db: AsyncSession = Depends(get_db),
):
    """Human agent sends a manual message from the dashboard."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    await lead_service.save_message(
        lead_id=lead.id,
        sender="agent",
        content=body.content,
    )
    await whatsapp.send_text(lead.phone, body.content)
    return {"status": "sent"}


@router.post("/{lead_id}/handoff")
async def toggle_handoff(lead_id: str, data: dict):
    """
    Toggles human takeover mode for a conversation.
    When ON, the AI stops responding automatically.
    POST body: { "isHuman": true | false }
    """
    is_human = data.get("isHuman", False)
    await context_manager.set_human_mode(lead_id, is_human)
    return {"status": "ok", "isHuman": is_human}
```

### 7.3 Analytics Router — `app/routers/analytics.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, cast, Date
from app.models.lead import Lead
from app.models.message import Message
from app.models.sale import Sale
from app.database import get_db
import datetime

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/dashboard-stats")
async def dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Returns today's KPI snapshot for the Overview page stat cards."""
    today = datetime.date.today()

    total_chats_today = await db.scalar(
        select(func.count(Message.id))
        .where(cast(Message.created_at, Date) == today)
    )
    new_leads = await db.scalar(
        select(func.count(Lead.id))
        .where(cast(Lead.created_at, Date) == today)
    )
    sales_closed = await db.scalar(
        select(func.count(Sale.id))
        .where(
            Sale.status == "completed",
            cast(Sale.date, Date) == today,
        )
    )
    revenue = await db.scalar(
        select(func.sum(Sale.amount))
        .where(
            Sale.status == "completed",
            cast(Sale.date, Date) == today,
        )
    ) or 0

    return {
        "totalChatsToday": total_chats_today or 0,
        "newLeads":        new_leads or 0,
        "salesClosed":     sales_closed or 0,
        "revenueGenerated": float(revenue),
    }


@router.get("/funnel")
async def funnel_data(db: AsyncSession = Depends(get_db)):
    """Returns lead count per funnel stage for the SalesFunnelWidget."""
    stages = {
        "New Leads":   ("new",),
        "Interested":  ("warm",),
        "Negotiating": ("hot",),
        "Converted":   ("closed",),
    }
    colors = {
        "New Leads":   "#2563EB",
        "Interested":  "#7C3AED",
        "Negotiating": "#F97316",
        "Converted":   "#22C55E",
    }
    result = []
    for stage, statuses in stages.items():
        count = await db.scalar(
            select(func.count(Lead.id)).where(Lead.status.in_(statuses))
        )
        result.append({
            "stage": stage,
            "count": count or 0,
            "color": colors[stage]
        })
    return result
```

### 7.4 Settings Router — `app/routers/settings.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.settings import BusinessSettings
from app.database import get_db
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["Settings"])


@router.get("/", response_model=SettingsOut)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """
    Returns the business settings row.
    Auto-creates a default row if one doesn't exist yet (first-run behavior).
    """
    result = await db.execute(select(BusinessSettings).limit(1))
    settings_row = result.scalar_one_or_none()
    if not settings_row:
        settings_row = BusinessSettings()
        db.add(settings_row)
        await db.commit()
        await db.refresh(settings_row)
    return settings_row


@router.put("/", response_model=SettingsOut)
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(BusinessSettings).limit(1))
    settings_row = result.scalar_one_or_none()
    if not settings_row:
        settings_row = BusinessSettings()
        db.add(settings_row)

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings_row, field, value)

    await db.commit()
    await db.refresh(settings_row)
    return settings_row
```

---

## PART 8 — Socket.IO Real-Time Server

The frontend dashboard needs to update live when new messages arrive — without polling. Socket.IO provides persistent bidirectional connections between the backend and the Next.js frontend.

### 8.1 Socket Manager — `app/core/socket_manager.py`

```python
import socketio
from app.models.lead import Lead

# Async Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",   # Restrict to FRONTEND_URL in production
    logger=False,
    engineio_logger=False,
)


@sio.event
async def connect(sid, environ):
    print(f"[Socket.IO] Client connected: {sid}")


@sio.event
async def disconnect(sid):
    print(f"[Socket.IO] Client disconnected: {sid}")


@sio.event
async def join_room(sid, data):
    """
    Frontend joins a room for a specific lead conversation.
    Only clients in the room receive that lead's messages.
    Usage: socket.emit('join_room', { lead_id: '...' })
    """
    room = f"lead_{data['lead_id']}"
    await sio.enter_room(sid, room)


class SocketManager:

    async def emit_new_message(
        self,
        lead: Lead,
        ai_reply: str,
        customer_message: str,
    ):
        """Push new message event to all dashboard clients."""
        await sio.emit(
            "new_message",
            {
                "leadId":          str(lead.id),
                "customerMessage": customer_message,
                "aiReply":         ai_reply,
                "leadName":        lead.name,
                "leadPhone":       lead.phone,
            },
        )

    async def emit_lead_update(self, lead: Lead):
        await sio.emit(
            "lead_updated",
            {
                "leadId": str(lead.id),
                "status": lead.status,
                "name":   lead.name,
            },
        )

    async def emit_stats_update(self, stats: dict):
        await sio.emit("stats_updated", stats)


socket_manager = SocketManager()
```

### 8.2 Main Entry Point — `app/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio

from app.config import settings
from app.core.socket_manager import sio
from app.routers import (
    webhook,
    leads,
    messages,
    analytics,
    settings as settings_router,
)

app = FastAPI(
    title="SmartSales AI Backend",
    version="1.0.0",
    description="AI-powered WhatsApp sales automation backend"
)

# CORS — allow frontend origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all routers
app.include_router(webhook.router)
app.include_router(leads.router)
app.include_router(messages.router)
app.include_router(analytics.router)
app.include_router(settings_router.router)

# Mount Socket.IO as an ASGI sub-application on the same port
socket_app = socketio.ASGIApp(sio, other_asgi_app=app)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "SmartSales AI Backend"}
```

### 8.3 Run Command

```bash
# IMPORTANT: entry point is socket_app, not app
# This ensures Socket.IO and FastAPI share the same port
uvicorn app.main:socket_app --host 0.0.0.0 --port 8000 --reload
```

### 8.4 Update Next.js Socket Client

Replace the simulated socket in `src/lib/socket.ts` with:

```typescript
import { io, Socket } from "socket.io-client";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

let socket: Socket | null = null;

export function getSocket(): Socket {
  if (!socket) {
    socket = io(BACKEND_URL, { transports: ["websocket"] });
  }
  return socket;
}

export function joinLeadRoom(leadId: string) {
  getSocket().emit("join_room", { lead_id: leadId });
}
```

Add to `.env.local` in the Next.js project:

```env
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

---

## PART 9 — Database Setup & Migrations

### 9.1 Async DB Session — `app/database.py`

```python
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from app.config import settings
from contextlib import asynccontextmanager

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


@asynccontextmanager
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

### 9.2 Alembic Migration Setup

```bash
# Initialize Alembic in the project root
alembic init alembic
```

Edit `alembic/env.py` — find the `target_metadata` line and replace it with:

```python
from app.database import Base
from app.models import lead, message, sale, settings   # import all models to register them
target_metadata = Base.metadata
```

Also update the connection URL in `alembic/env.py`:

```python
from app.config import settings as app_settings

# Replace the hardcoded url with:
config.set_main_option("sqlalchemy.url", app_settings.DATABASE_URL.replace("+asyncpg", ""))
```

Run migrations:

```bash
# Generate the initial migration from your models
alembic revision --autogenerate -m "initial schema"

# Apply it to the database
alembic upgrade head
```

---

## PART 10 — Pydantic Schemas

### `app/schemas/lead.py`

```python
from pydantic import BaseModel
from typing import Optional
import uuid, datetime

class LeadOut(BaseModel):
    id:           uuid.UUID
    name:         Optional[str]
    phone:        str
    channel:      str
    status:       str
    intent_tags:  list[str]
    unread_count: int
    last_message: Optional[str]
    created_at:   datetime.datetime
    updated_at:   datetime.datetime

    class Config:
        from_attributes = True


class LeadUpdate(BaseModel):
    name:         Optional[str] = None
    status:       Optional[str] = None
    unread_count: Optional[int] = None
```

### `app/schemas/message.py`

```python
from pydantic import BaseModel
from typing import Optional
import uuid, datetime

class MessageOut(BaseModel):
    id:         uuid.UUID
    lead_id:    uuid.UUID
    sender:     str
    content:    str
    intent_tag: Optional[str]
    created_at: datetime.datetime

    class Config:
        from_attributes = True


class AgentMessageIn(BaseModel):
    content: str
```

### `app/schemas/settings.py`

```python
from pydantic import BaseModel
from typing import Optional

class SettingsOut(BaseModel):
    business_name:         str
    ai_persona_name:       str
    ai_tone:               str
    knowledge_base:        str
    auto_followup:         bool
    human_handoff_trigger: bool

    class Config:
        from_attributes = True


class SettingsUpdate(BaseModel):
    business_name:         Optional[str]  = None
    ai_persona_name:       Optional[str]  = None
    ai_tone:               Optional[str]  = None
    knowledge_base:        Optional[str]  = None
    auto_followup:         Optional[bool] = None
    human_handoff_trigger: Optional[bool] = None
```

### `app/schemas/sale.py`

```python
from pydantic import BaseModel
from typing import Optional
import uuid, datetime

class SaleOut(BaseModel):
    id:       uuid.UUID
    customer: str
    product:  str
    amount:   float
    status:   str
    date:     datetime.datetime
    channel:  str

    class Config:
        from_attributes = True
```

---

## PART 11 — WhatsApp Cloud API Setup (Meta)

### 11.1 Meta Developer App Setup

Follow these steps on the Meta Developer Portal:

1. Go to [developers.facebook.com](https://developers.facebook.com) and create a new App → choose **Business** type
2. Add the **WhatsApp** product to your app
3. Under **WhatsApp > API Setup**, note your:
   - **Phone Number ID** → goes into `WHATSAPP_PHONE_NUMBER_ID`
   - **Temporary Access Token** (replace with a permanent token before going live)
4. Under **WhatsApp > Configuration**:
   - Set **Webhook URL** to: `https://yourdomain.com/webhook/whatsapp`
   - Set **Verify Token** to the same value as `WHATSAPP_VERIFY_TOKEN` in `.env`
   - Subscribe to the **messages** webhook field only
5. Under **WhatsApp > Phone Numbers**, add and verify your business phone number

### 11.2 Local Development with ngrok

Meta requires a public HTTPS URL to deliver webhooks. During development:

```bash
# Install ngrok (https://ngrok.com) then run:
ngrok http 8000
```

Copy the `https://` forwarding URL and paste it as your webhook URL in the Meta portal.

> **Note:** The ngrok URL changes on every restart unless you have a paid ngrok plan. If you frequently restart, consider a free subdomain on ngrok or use Cloudflare Tunnel instead.

### 11.3 Permanent Access Token

The temporary token expires in 24 hours. Generate a permanent one:

1. In Meta Business Suite → **Settings → Users → System Users**
2. Create a System User, assign it to your WhatsApp app with `whatsapp_business_messaging` permission
3. Click **Generate Token** — this is your permanent `WHATSAPP_ACCESS_TOKEN`

Store this token securely. Never commit it to Git.

### 11.4 WhatsApp 24-Hour Window

Meta only allows free-form messages within **24 hours** of the customer's last inbound message. After that window closes, you must use pre-approved **Message Templates** to reach the customer.

Plan for this in the auto-follow-up feature — the backend must track `last_customer_message_at` per lead and switch to template messages for follow-ups sent after 24 hours.

---

## PART 12 — Human Handoff Flow

When a customer requests a human agent — or when a dashboard agent clicks "Human Takeover" — the AI must immediately stop responding.

### How It Works

1. The dashboard sends `POST /api/messages/{leadId}/handoff` with `{ "isHuman": true }`
2. The backend sets a Redis flag: `human_mode:{lead_id} = 1` (expires in 1 hour)
3. On the next incoming WhatsApp message, the webhook checks this flag before calling Gemini
4. If the flag is set, the message is saved and pushed to the frontend — but no AI reply is generated
5. The agent sees the message in the dashboard and replies manually

### Webhook Check (already included in Part 3)

```python
# In app/routers/webhook.py — before calling ai_service.generate_reply():
if await context_manager.is_human_mode(str(lead.id)):
    await lead_service.save_message(
        lead_id=lead.id,
        sender="customer",
        content=incoming_text,
        wa_message_id=wa_message_id,
    )
    await socket_manager.emit_new_message(lead, "", incoming_text)
    return {"status": "ok"}
```

### Handoff Endpoint (already in Part 7)

```python
# In app/routers/messages.py
@router.post("/{lead_id}/handoff")
async def toggle_handoff(lead_id: str, data: dict):
    is_human = data.get("isHuman", False)
    await context_manager.set_human_mode(lead_id, is_human)
    return {"status": "ok", "isHuman": is_human}
```

### Frontend Integration

In `ChatWindow.tsx`, call this endpoint when the "Human Takeover" toggle is switched:

```typescript
const toggleHandoff = async (isHuman: boolean) => {
  await fetch(`/api/messages/${leadId}/handoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ isHuman }),
  });
};
```

---

## PART 13 — Environment-Specific Configurations

### Development

```bash
# Start PostgreSQL and Redis with Docker
docker compose up -d db redis

# Run backend with hot reload
uvicorn app.main:socket_app --reload --port 8000

# Expose to Meta's webhook delivery
ngrok http 8000
```

### Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:socket_app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2"]
```

> For production with multiple workers, ensure Redis is used for all shared state (context, human mode flags). Never store per-request state in Python class instances.

### docker-compose.yml

```yaml
version: "3.9"

services:
  backend:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:16
    environment:
      POSTGRES_USER: smartsales
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: smartsales
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
```

### Recommended Hosting

| Platform                  | Notes                                                                    |
| ------------------------- | ------------------------------------------------------------------------ |
| Railway                   | Easiest — one-click PostgreSQL + Redis add-ons, auto-deploys from GitHub |
| Render                    | Free tier available, WebSocket support works well for Socket.IO          |
| DigitalOcean App Platform | Good for production, managed DB and Redis add-ons available              |
| Fly.io                    | Low latency globally, good for WhatsApp workloads with African traffic   |

---

## PART 14 — API Endpoint Reference

| Method  | URL                                   | Description                                  |
| ------- | ------------------------------------- | -------------------------------------------- |
| `GET`   | `/health`                             | Health check                                 |
| `GET`   | `/webhook/whatsapp`                   | Meta webhook verification                    |
| `POST`  | `/webhook/whatsapp`                   | Receive incoming WhatsApp messages           |
| `GET`   | `/api/leads/`                         | List all leads (filter: `channel`, `status`) |
| `GET`   | `/api/leads/{id}`                     | Get a single lead                            |
| `PATCH` | `/api/leads/{id}`                     | Update a lead (name, status, unread_count)   |
| `GET`   | `/api/messages/{lead_id}`             | Get all messages for a lead (chronological)  |
| `POST`  | `/api/messages/{lead_id}/agent-reply` | Human agent sends a manual message           |
| `POST`  | `/api/messages/{lead_id}/handoff`     | Toggle human takeover on/off                 |
| `GET`   | `/api/analytics/dashboard-stats`      | Today's KPI stats                            |
| `GET`   | `/api/analytics/funnel`               | Sales funnel stage counts                    |
| `GET`   | `/api/settings/`                      | Get business settings                        |
| `PUT`   | `/api/settings/`                      | Update business settings                     |

### Socket.IO Events

| Event           | Direction       | Payload                                                     |
| --------------- | --------------- | ----------------------------------------------------------- |
| `connect`       | Client → Server | (automatic)                                                 |
| `join_room`     | Client → Server | `{ lead_id: string }`                                       |
| `new_message`   | Server → Client | `{ leadId, customerMessage, aiReply, leadName, leadPhone }` |
| `lead_updated`  | Server → Client | `{ leadId, status, name }`                                  |
| `stats_updated` | Server → Client | `{ totalChatsToday, newLeads, ... }`                        |

---

## PART 15 — Build Order Checklist

Follow this order exactly. Each step depends on the one before it.

- [ ] **1.** Create folder structure, install all dependencies
- [ ] **2.** Write `.env` with all keys filled in
- [ ] **3.** Write `app/config.py` and `app/database.py`
- [ ] **4.** Create all 4 SQLAlchemy models (`lead`, `message`, `sale`, `settings`)
- [ ] **5.** Run `alembic revision --autogenerate` and `alembic upgrade head`
- [ ] **6.** Build `ContextManager` (Redis — get/set/clear history + human mode flags)
- [ ] **7.** Build `IntentService` (Gemini Flash — intent classification)
- [ ] **8.** Build `AIService` (Gemini Pro — full reply generation with history)
- [ ] **9.** Build `WhatsAppService` (send_text + send_interactive_buttons)
- [ ] **10.** Build `LeadService` (get_or_create, save_message, update_lead_intent)
- [ ] **11.** Build webhook router (GET verify + POST receive + human mode check)
- [ ] **12.** Build Socket.IO server + `SocketManager` class
- [ ] **13.** Write `app/main.py` — mount all routers + Socket.IO ASGI app
- [ ] **14.** Test end-to-end locally with ngrok (send a real WhatsApp message, watch the logs)
- [ ] **15.** Build all Pydantic schemas
- [ ] **16.** Build leads router
- [ ] **17.** Build messages router (including agent-reply and handoff endpoints)
- [ ] **18.** Build analytics router
- [ ] **19.** Build settings router
- [ ] **20.** Implement human handoff flow (Redis flag + webhook check + API endpoint)
- [ ] **21.** Update Next.js socket client (`src/lib/socket.ts`) to point to real backend
- [ ] **22.** Replace frontend mock data with real `fetch()` calls to the API
- [ ] **23.** Write Dockerfile + `docker-compose.yml`
- [ ] **24.** Deploy to production (Railway / Render / DigitalOcean)
- [ ] **25.** Generate permanent WhatsApp access token + update production webhook URL in Meta portal
- [ ] **26.** Final end-to-end QA: real WhatsApp message → Gemini reply → dashboard live update

---

## Notes for the Engineer

### Gemini Model Selection

Use `gemini-1.5-pro` for reply generation and `gemini-1.5-flash` for intent classification. This hybrid approach reduces cost per message by approximately 70% while keeping reply quality high. Flash's lower quality is acceptable for a simple 5-category classification task.

### Context Window Management

Gemini 1.5 Pro has a 1M token context window, but cap Redis history at 10–20 turns. Sending 100 turns of history adds latency and cost without meaningful quality improvement — most relevant context is in the last 5–10 exchanges.

### Knowledge Base Per Business

The `knowledge_base` field in `BusinessSettings` is what makes the AI useful for each client. Instruct clients to paste their complete product catalogue, pricing table, FAQs, and return policy into the Settings page. The system prompt injects this directly into every Gemini call.

### Deduplication is Non-Negotiable

Always check `wa_message_id` before processing. Meta's webhook delivery is "at least once" — duplicate deliveries happen regularly, especially during network instability. Without deduplication, customers receive double AI replies and your DB accumulates duplicate messages.

### Rate Limits

Gemini 1.5 Pro allows 360 requests/minute on the free tier. At scale, add a rate limiter using `asyncio.Semaphore`:

```python
import asyncio
_gemini_semaphore = asyncio.Semaphore(50)  # Max concurrent Gemini calls

async def generate_reply(...):
    async with _gemini_semaphore:
        # ... call Gemini
```

### Currency

All monetary values should be stored as `Numeric(12, 2)` in PostgreSQL (already done in the Sale model) and returned as Python `float`. The Next.js frontend formats them with the `₦` symbol using `Intl.NumberFormat`.

### Type Safety

Match Python type hints rigorously with the TypeScript interfaces defined in `src/types/index.ts`. The FastAPI `response_model` + Pydantic schemas enforce this at the API boundary. Never use `Any` — type mismatches become hard-to-debug frontend bugs.

### Production Security Checklist

- [ ] Set `cors_allowed_origins` in Socket.IO to `FRONTEND_URL` only (remove `"*"`)
- [ ] Add authentication middleware to all `/api/*` routes before going live
- [ ] Store `WHATSAPP_ACCESS_TOKEN` in a secrets manager (AWS Secrets Manager, Doppler, etc.)
- [ ] Set `APP_ENV=production` — consider enabling rate limiting on the webhook endpoint
- [ ] Use SSL/TLS termination at the load balancer level (Meta requires HTTPS for webhook delivery)

---

_SmartSales AI Backend — Built to Sell While You Sleep. 🚀_
