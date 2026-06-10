from pydantic import BaseModel


class ConnectWhatsAppRequest(BaseModel):
    authorization_code: str
    whatsapp_business_account_id: str
    phone_number_id: str


class ConnectWhatsAppResponse(BaseModel):
    connected: bool
    phone_number: str
    business_name: str
    phone_number_id: str
    whatsapp_business_account_id: str
    status: str
