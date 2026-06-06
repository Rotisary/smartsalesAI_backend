from typing import Any


class AppError(Exception):
    code = "app_error"

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class AppConfigurationError(AppError):
    code = "configuration_error"


class ExternalServiceError(AppError):
    code = "external_service_error"

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.status_code = status_code
