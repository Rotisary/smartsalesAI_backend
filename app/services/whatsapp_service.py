from dataclasses import dataclass
from typing import Any

import httpx

from app.config import settings


# a placeholder WhatsAppConnection class
@dataclass(frozen=True)
class WhatsAppConnection:
    phone_number_id: str
    access_token: str


class WhatsAppConfigurationError(ValueError):
    pass


class WhatsAppAPIError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        meta_error: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.meta_error = meta_error


class WhatsAppService:
    BASE_URL = "https://graph.facebook.com/{version}/{phone_id}/messages"

    def __init__(self, connection: WhatsAppConnection, *, timeout: float = 15.0):
        self._validate_connection(connection)
        self.connection = connection
        self.timeout = timeout
        self.url = self.BASE_URL.format(
            version=settings.WHATSAPP_API_VERSION,
            phone_id=connection.phone_number_id,
        )
        self.headers = {
            "Authorization": f"Bearer {connection.access_token}",
            "Content-Type": "application/json",
        }

    async def send_text(
        self,
        to: str,
        message: str,
        preview_url: bool = False,
    ) -> dict[str, Any]:
        if not to or not to.strip():
            raise WhatsAppConfigurationError("Recipient phone number is required")
        if not message or not message.strip():
            raise WhatsAppConfigurationError("Message body is required")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": preview_url, "body": message},
        }
        return await self._post(payload)

    async def send_interactive_buttons(
        self,
        to: str,
        body: str,
        buttons: list[str],
    ) -> dict[str, Any]:
        if not to or not to.strip():
            raise WhatsAppConfigurationError("Recipient phone number is required")
        if not body or not body.strip():
            raise WhatsAppConfigurationError("Interactive message body is required")

        cleaned_buttons = [button.strip() for button in buttons if button and button.strip()]
        if not cleaned_buttons:
            raise WhatsAppConfigurationError("At least one button is required")

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {"id": f"btn_{index}", "title": button},
                        }
                        for index, button in enumerate(cleaned_buttons[:3])
                    ]
                },
            },
        }
        return await self._post(payload)

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.url,
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                try:
                    return response.json()
                except ValueError:
                    return {}
        except httpx.HTTPStatusError as exc:
            raise self._build_api_error(exc) from exc
        except httpx.RequestError as exc:
            raise WhatsAppAPIError(
                "WhatsApp API request failed due to a network error"
            ) from exc

    @staticmethod
    def _validate_connection(connection: WhatsAppConnection) -> None:
        if not connection.phone_number_id or not connection.phone_number_id.strip():
            raise WhatsAppConfigurationError("WhatsApp phone number ID is required")
        if not connection.access_token or not connection.access_token.strip():
            raise WhatsAppConfigurationError("WhatsApp access token is required")

    @staticmethod
    def _build_api_error(exc: httpx.HTTPStatusError) -> WhatsAppAPIError:
        response = exc.response
        status_code = response.status_code
        meta_error: dict[str, Any] | None = None
        message = "Meta Graph API returned an error"

        try:
            body = response.json()
        except ValueError:
            body = None

        if isinstance(body, dict):
            error = body.get("error")
            if isinstance(error, dict):
                meta_error = error
                message = str(error.get("message") or message)

        return WhatsAppAPIError(
            f"WhatsApp API request failed with status {status_code}: {message}",
            status_code=status_code,
            meta_error=meta_error,
        )
