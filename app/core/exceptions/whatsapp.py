from typing import Any

from app.core.exceptions.base import AppConfigurationError, ExternalServiceError


class WhatsAppConfigurationError(AppConfigurationError):
    code = "whatsapp_configuration_error"


class WhatsAppAPIError(ExternalServiceError):
    code = "whatsapp_api_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        meta_error: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            details={"meta_error": meta_error} if meta_error else None,
        )
        self.meta_error = meta_error
