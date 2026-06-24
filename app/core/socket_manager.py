import logging
import socketio
 
logger = logging.getLogger(__name__)
 
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)
 
@sio.event
async def connect(sid, environ):
    logger.info("[Socket.IO] Client connected: %s", sid)
 
 
@sio.event
async def disconnect(sid):
    logger.info("[Socket.IO] Client disconnected: %s", sid)
 

 
@sio.event
async def join_lead_room(sid, data):
    """
    Client usage:
        socket.emit('join_lead_room', { lead_id: 'uuid-string' })
    """
    lead_id = data.get("lead_id")
    if not lead_id:
        logger.warning("[Socket.IO] join_lead_room called without lead_id from %s", sid)
        return
 
    room = f"lead_{lead_id}"
    await sio.enter_room(sid, room)
    logger.info("[Socket.IO] %s joined room %s", sid, room)
 
 
@sio.event
async def leave_lead_room(sid, data):
    """
    Client usage:
        socket.emit('leave_lead_room', { lead_id: 'uuid-string' })
    """
    lead_id = data.get("lead_id")
    if not lead_id:
        return
 
    room = f"lead_{lead_id}"
    await sio.leave_room(sid, room)
    logger.info("[Socket.IO] %s left room %s", sid, room)
 
 
@sio.event
async def join_business_room(sid, data):
    """
    Client usage:
        socket.emit('join_business_room', { business_id: 'uuid-string' })
    """
    business_id = data.get("business_id")
    if not business_id:
        logger.warning("[Socket.IO] join_business_room called without business_id from %s", sid)
        return
 
    room = f"business_{business_id}"
    await sio.enter_room(sid, room)
    logger.info("[Socket.IO] %s joined business room %s", sid, room)
 
 
class SocketManager:

    async def emit_new_message(
        self,
        lead,
        ai_reply: str,
        customer_message: str,
    ):
        """
        Push a new message event to clients watching this lead's conversation.
        """
        await sio.emit(
            "new_message",
            {
                "leadId": str(lead.id),
                "customerMessage": customer_message,
                "aiReply": ai_reply,
                "leadName": lead.name,
                "leadPhone": lead.phone,
            },
            room=f"lead_{lead.id}",
        )
 
    async def emit_lead_updated(self, lead):
        """
        Notify the frontend when a lead's status or score changes.
        Emitted to the lead's own room so the conversation view updates,
        and also broadcast globally so the leads list sidebar updates.
        """
        payload = {
            "leadId":    str(lead.id),
            "status":    lead.status,
            "name":      lead.name,
            "leadScore": getattr(lead, "lead_score", 0),
        }
        await sio.emit("lead_updated", payload, room=f"lead_{lead.id}")
        await sio.emit("lead_updated", payload)
 
    async def emit_stats_updated(self, business_id: str, stats: dict):
        """
        Push updated dashboard KPIs to the Overview page.
        Emitted to room: business_{business_id}
        """
        await sio.emit(
            "stats_updated",
            stats,
            room=f"business_{business_id}",
        )
 
    async def emit_knowledge_document_ready(
        self,
        business_id: str,
        document_id: str,
        chunk_count: int,
    ):
        """
        Notify the frontend when a knowledge base document finishes processing.
        Emitted to room: business_{business_id}
        """
        await sio.emit(
            "knowledge_document_ready",
            {
                "documentId": document_id,
                "chunkCount": chunk_count,
            },
            room=f"business_{business_id}",
        )
 
    async def emit_handoff_updated(self, lead_id: str, is_human: bool, assigned_to: str | None = None):
        """
        Notify the dashboard when human mode is toggled for a conversation.
        Emitted to room: lead_{lead_id}

        """
        await sio.emit(
            "handoff_updated",
            {
                "leadId":     lead_id,
                "isHuman":    is_human,
                "assignedTo": assigned_to,
            },
            room=f"lead_{lead_id}",
        )

 
socket_manager = SocketManager()
 