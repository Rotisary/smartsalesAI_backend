from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _get_fernet() -> Fernet:
    if not settings.WHATSAPP_TOKEN_ENCRYPTION_KEY:
        raise ValueError("WHATSAPP_TOKEN_ENCRYPTION_KEY is required")
    return Fernet(settings.WHATSAPP_TOKEN_ENCRYPTION_KEY.encode("utf-8"))


def encrypt_token(raw_token: str) -> str:
    if not raw_token:
        raise ValueError("Token is required")
    return _get_fernet().encrypt(raw_token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    if not encrypted_token:
        raise ValueError("Encrypted token is required")
    try:
        return _get_fernet().decrypt(encrypted_token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Encrypted token is invalid") from exc
