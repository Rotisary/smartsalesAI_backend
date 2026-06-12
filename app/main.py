from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.auth import router as auth_router
from app.routers.whatsapp import router as whatsapp_router
from app.routers.knowledge import router as knowledge_router

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
app.include_router(whatsapp_router)
app.include_router(knowledge_router)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "SmartSales AI Backend",
        "env": settings.APP_ENV,
    }


# --- Socket.IO ASGI (enable when socket_manager is implemented) ---
# import socketio
# from app.core.socket_manager import sio
# socket_app = socketio.ASGIApp(sio, other_asgi_app=app)
