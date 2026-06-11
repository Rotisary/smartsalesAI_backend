from app.utils.enums.base import BaseEnum


class Channel(BaseEnum):
    WHATSAPP = "whatsapp"
    INSTAGRAM = "instagram"
    WEB = "web"


class LeadStatus(BaseEnum):
    NEW = "new"
    WARM = "warm"
    HOT = "hot"
    CLOSED = "closed"
    LOST = "lost"


class MessageSender(BaseEnum):
    CUSTOMER = "customer"
    AI = "ai"
    AGENT = "agent"


class SaleStatus(BaseEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    REFUNDED = "refunded"
