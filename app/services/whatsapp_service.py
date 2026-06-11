from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.exceptions.whatsapp import (
    WhatsAppAPIError,
    WhatsAppConfigurationError,
)
from app.models.business import Business
from app.models.whatsapp_connection import WhatsAppConnection
from app.schemas.whatsapp import ConnectWhatsAppRequest, ConnectWhatsAppResponse
from app.utils.encryption import decrypt_token, encrypt_token


class WhatsAppService:
    GRAPH_BASE_URL = "https://graph.facebook.com/{version}"
    MESSAGES_PATH = "/{phone_id}/messages"

    def __init__(self, *, timeout: float = 15.0):
        self.timeout = timeout
        self.base_url = self.GRAPH_BASE_URL.format(version=settings.WHATSAPP_API_VERSION)

    async def exchange_authorization_code(self, authorization_code: str) -> str:
        if not authorization_code or not authorization_code.strip():
            raise WhatsAppConfigurationError("Authorization code is required")
        if not settings.META_APP_ID or not settings.META_APP_SECRET:
            raise WhatsAppConfigurationError("Meta app credentials are not configured")

        payload = await self._get(
            f"{self.base_url}/oauth/access_token",
            params={
                "client_id": settings.META_APP_ID,
                "client_secret": settings.META_APP_SECRET,
                "code": authorization_code,
            },
        )
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise WhatsAppAPIError("Meta OAuth response did not include an access token")
        return access_token

    async def verify_phone_number(
        self,
        phone_number_id: str,
        access_token: str,
    ) -> dict[str, Any]:
        if not phone_number_id or not phone_number_id.strip():
            raise WhatsAppConfigurationError("WhatsApp phone number ID is required")
        if not access_token or not access_token.strip():
            raise WhatsAppConfigurationError("WhatsApp access token is required")

        payload = await self._get(
            f"{self.base_url}/{phone_number_id}",
            headers=self._build_headers(access_token),
            params={"fields": "id,display_phone_number,verified_name"},
        )

        if str(payload.get("id")) != phone_number_id:
            raise WhatsAppConfigurationError(
                "Verified phone number does not match the submitted phone number ID"
            )
        if not payload.get("display_phone_number"):
            raise WhatsAppConfigurationError(
                "Verified phone number response is missing display_phone_number"
            )
        return payload

    async def connect_embedded_signup(
        self,
        db: AsyncSession,
        business: Business,
        payload: ConnectWhatsAppRequest,
    ) -> ConnectWhatsAppResponse:
        access_token = await self.exchange_authorization_code(payload.authorization_code)
        phone_number = await self.verify_phone_number(
            payload.phone_number_id,
            access_token,
        )

        try:
            encrypted_access_token = encrypt_token(access_token)
        except ValueError as exc:
            raise WhatsAppConfigurationError(str(exc)) from exc

        existing_by_phone = await db.get(WhatsAppConnection, payload.phone_number_id)
        if existing_by_phone and existing_by_phone.business_id != business.id:
            raise WhatsAppConfigurationError(
                "This WhatsApp phone number is already connected to another business"
            )

        existing_for_business_result = await db.execute(
            select(WhatsAppConnection).where(
                WhatsAppConnection.business_id == business.id
            )
        )
        existing_for_business = existing_for_business_result.scalar_one_or_none()
        if (
            existing_for_business
            and existing_for_business.phone_number_id != payload.phone_number_id
        ):
            await db.delete(existing_for_business)
            await db.flush()

        connection = existing_by_phone or WhatsAppConnection(
            phone_number_id=payload.phone_number_id,
            business_id=business.id,
        )
        connection.whatsapp_business_account_id = payload.whatsapp_business_account_id
        connection.display_phone_number = str(phone_number["display_phone_number"])
        connection.verified_name = phone_number.get("verified_name")
        connection.encrypted_access_token = encrypted_access_token
        connection.status = "connected"

        db.add(connection)

        business.whatsapp_phone_number_id = payload.phone_number_id
        business.whatsapp_connected = True
        business.connected_at = datetime.now(timezone.utc)
        await db.flush()

        return ConnectWhatsAppResponse(
            connected=True,
            phone_number=connection.display_phone_number,
            business_name=connection.verified_name or business.business_name,
            phone_number_id=connection.phone_number_id,
            whatsapp_business_account_id=connection.whatsapp_business_account_id,
            status=connection.status,
        )

    async def send_text(
        self,
        connection: WhatsAppConnection,
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
        return await self._post_message(connection, payload)

    async def send_interactive_buttons(
        self,
        connection: WhatsAppConnection,
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
        return await self._post_message(connection, payload)

    async def _post_message(
        self,
        connection: WhatsAppConnection,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        access_token = self._get_connection_access_token(connection)
        return await self._post(
            self._message_url(connection.phone_number_id),
            payload,
            headers=self._build_headers(access_token),
        )

    def _get_connection_access_token(self, connection: WhatsAppConnection) -> str:
        if not connection.phone_number_id or not connection.phone_number_id.strip():
            raise WhatsAppConfigurationError("WhatsApp phone number ID is required")
        if not connection.encrypted_access_token:
            raise WhatsAppConfigurationError("WhatsApp access token is required")

        try:
            return decrypt_token(connection.encrypted_access_token)
        except ValueError as exc:
            raise WhatsAppConfigurationError(str(exc)) from exc

    def _message_url(self, phone_number_id: str) -> str:
        return f"{self.base_url}{self.MESSAGES_PATH.format(phone_id=phone_number_id)}"

    async def _get(
        self,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                return self._response_json(response)
        except httpx.HTTPStatusError as exc:
            raise self._build_api_error(exc) from exc
        except httpx.RequestError as exc:
            raise WhatsAppAPIError(
                "WhatsApp API request failed due to a network error"
            ) from exc

    async def _post(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                return self._response_json(response)
        except httpx.HTTPStatusError as exc:
            raise self._build_api_error(exc) from exc
        except httpx.RequestError as exc:
            raise WhatsAppAPIError(
                "WhatsApp API request failed due to a network error"
            ) from exc

    @staticmethod
    def _build_headers(access_token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _response_json(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

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
