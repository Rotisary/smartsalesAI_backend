# SmartSales AI Backend

FastAPI backend for multi-business WhatsApp sales automation.

## Local Setup

Use Python 3.10, 3.11, or 3.12. The pinned PostgreSQL dependencies do not install cleanly on Python 3.14 yet.

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env` from `.env.example`, then run migrations:

```bash
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

## First Implemented API Slice

All endpoints require `Authorization: Bearer <access_token>` and are scoped to the logged-in business.

```http
GET /api/leads/?status=hot&channel=whatsapp&search=080
GET /api/leads/{lead_id}
PATCH /api/leads/{lead_id}
GET /api/messages/{lead_id}
POST /api/messages/{lead_id}/agent-reply
POST /api/messages/{lead_id}/handoff
```

Handoff request body:

```json
{
  "isHuman": true,
  "assignedTo": "Ada"
}
```
