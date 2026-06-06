from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.business import BusinessCreate, BusinessRead
from app.schemas.settings import BusinessSettingsCreate, BusinessSettingsRead


class WhatsAppConnectionData(BaseModel):
    whatsapp_phone_number_id: str
    connected_at: Optional[datetime] = None


class SignupRequest(BaseModel):
    business: BusinessCreate
    settings: BusinessSettingsCreate
    whatsapp_connection: Optional[WhatsAppConnectionData] = None


class LoginRequest(BaseModel):
    business_email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_in: int
    refresh_token_expires_in: int


class LogoutResponse(BaseModel):
    status: str
    revoked_at: Optional[datetime] = None
    message: str


class AuthResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    business: BusinessRead
    settings: BusinessSettingsRead
    tokens: TokenResponse