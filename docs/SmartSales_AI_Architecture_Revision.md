# SmartSales AI — Architecture Revision Patch

This document contains the exact architectural modifications that should be applied to the original implementation guide. Any section not mentioned here remains unchanged.

---

# 1. Add Business Model (NEW)

## New Model: `app/models/business.py`

```python
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base
import uuid, datetime

class Business(Base):
    __tablename__ = "businesses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    name = Column(String, nullable=False)

    whatsapp_phone_number_id = Column(String, nullable=False, unique=True)

    created_at = Column(
        DateTime,
        default=datetime.datetime.utcnow
    )

    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow
    )
```

---

# 2. Update Folder Structure

Add:

```text
models/
└── business.py

schemas/
└── business.py
```

---

# 3. Multi-Tenant Business Ownership

Add `business_id` to:

- Lead
- Message
- Sale
- BusinessSettings

Example:

```python
business_id = Column(
    UUID(as_uuid=True),
    ForeignKey("businesses.id"),
    nullable=False,
    index=True
)
```

---

# 4. Lead Model Changes

Add:

```python
business_id
lead_score
is_human_mode
human_assigned_to
last_customer_message_at
```

Recommended fields:

```python
lead_score = Column(Integer, default=0)

is_human_mode = Column(Boolean, default=False)

human_assigned_to = Column(String, nullable=True)

last_customer_message_at = Column(DateTime, nullable=True)
```

---

# 5. Business Settings Changes

Replace:

```python
knowledge_base
```

With:

```python
business_id
knowledge_base
```

Relationship becomes:

```text
Business 1 ---> 1 BusinessSettings
```

Each business now owns its own configuration.

---

# 6. Knowledge Base Roadmap

Current implementation remains:

```python
knowledge_base = Column(Text)
```

Add engineering note:

```text
Future Version:

Move knowledge_base to a RAG architecture.

New tables:

KnowledgeDocument
KnowledgeChunk

Chunks should be embedded and retrieved at runtime instead
of injecting the full knowledge base into every Gemini request.
```

Hackathon implementation remains unchanged.

---

# 7. Human Handoff Changes

Remove Redis TTL ownership of handoff state.

Current:

```python
human_mode:{lead_id}
```

becomes:

```python
Lead.is_human_mode
Lead.human_assigned_to
```

Redis may still cache the value.

Source of truth becomes PostgreSQL.

---

# 8. Lead Scoring System

Replace:

```python
Buying -> hot
Pricing -> warm
```

with:

```python
Pricing   +10
Buying    +30
Support   +5
Complaint +5
```

Example:

```python
if intent_tag == "Pricing":
    lead.lead_score += 10

elif intent_tag == "Buying":
    lead.lead_score += 30
```

Status derived from score:

```text
0-19     -> new
20-49    -> warm
50-99    -> hot
100+     -> closed
```

---

# 9. Conversation Memory Changes

Redis remains.

PostgreSQL becomes source of truth.

New flow:

```text
Redis Hit
    ↓
Use Cached History

Redis Miss
    ↓
Load Recent Messages From PostgreSQL
    ↓
Rebuild Cache
```

This prevents memory loss after Redis expiration.

---

# 10. Webhook Processing Architecture

Current synchronous processing:

```text
Webhook
 → Save
 → Gemini
 → Intent
 → Send Reply
 → Return
```

Recommended architecture:

```text
Webhook
 → Save Message
 → Queue Job
 → Return 200 Immediately
```

Worker:

```text
Worker
 → Generate Intent
 → Generate AI Reply
 → Save Reply
 → Send WhatsApp Message
 → Emit Socket Event
```

---

# 11. Background Jobs

Add service:

```text
services/
└── job_service.py
```

Recommended technologies:

- ARQ
- Dramatiq
- Celery

For hackathon deployment the synchronous flow may remain enabled.

---

# 12. Socket.IO Fix

Current implementation broadcasts globally.

Replace:

```python
await sio.emit("new_message", payload)
```

with:

```python
await sio.emit(
    "new_message",
    payload,
    room=f"lead_{lead.id}"
)
```

Use rooms consistently for:

- messages
- lead updates
- conversation updates

---

# 13. Authentication Requirements

Before production:

Add:

```text
JWT Authentication
Role-Based Access Control
Business Isolation
```

Every API query should be scoped by:

```python
business_id
```

Example:

```python
select(Lead).where(
    Lead.business_id == current_business.id
)
```

---

# 14. AI Optimization Roadmap

Current:

```text
Gemini Pro
+
Gemini Flash
```

Future optimization:

Single structured call:

```json
{
  "reply": "...",
  "intent": "Pricing"
}
```

Reduces AI cost and latency.

Current implementation may remain unchanged during hackathon development.

---

# 15. Analytics Changes

Every analytics query should include:

```python
business_id
```

Example:

```python
select(func.count(Lead.id))
.where(Lead.business_id == business_id)
```

This prevents cross-business data leakage.

---

# 16. Build Order Additions

Insert before Lead model creation:

```text
Create Business model
Create Business migration
Create BusinessSettings relationship
Add business_id foreign keys
```

---

# 17. Production Priority List

Highest priority:

1. Business model
2. business_id isolation
3. Human handoff persistence
4. Background workers
5. Lead scoring
6. PostgreSQL-backed conversation recovery
7. RAG knowledge base

Everything else from the original implementation guide remains unchanged.
