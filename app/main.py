from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import socketio
from app.core.socket_manager import sio

from app.config import settings
from app.routers.auth import router as auth_router
from app.routers.leads import router as leads_router
from app.routers.messages import router as messages_router
from app.routers.sales import router as sales_router
from app.routers.webhook import router as webhook_router
from app.routers.whatsapp import router as whatsapp_router
from app.routers.knowledge import router as knowledge_router
from app.routers.settings import router as settings_router

app = FastAPI(
    title="SmartSales AI Backend",
    version="1.0.0",
    description="AI-powered WhatsApp sales automation backend",
)

_cors_origins = (
    [settings.FRONTEND_URL, "http://127.0.0.1:3000"]
    if settings.is_development
    else [settings.FRONTEND_URL]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(leads_router)
app.include_router(messages_router)
app.include_router(sales_router)
app.include_router(webhook_router)
app.include_router(whatsapp_router)
app.include_router(knowledge_router)
app.include_router(settings_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "SmartSales AI Backend",
        "env": settings.APP_ENV,
    }

socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
