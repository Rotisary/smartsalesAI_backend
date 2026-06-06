from app.core.exceptions.base import (
    AppConfigurationError,
    AppError,
    ExternalServiceError,
)
from app.core.exceptions.whatsapp import (
    WhatsAppAPIError,
    WhatsAppConfigurationError,
)

__all__ = [
    "AppConfigurationError",
    "AppError",
    "ExternalServiceError",
    "WhatsAppAPIError",
    "WhatsAppConfigurationError",
]
