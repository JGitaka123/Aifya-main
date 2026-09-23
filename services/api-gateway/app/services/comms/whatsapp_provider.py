"""WhatsApp provider abstraction.

Two delivery backends are supported, chosen by which credentials are present:

* Green API - send from an existing WhatsApp number linked by QR code.
  Needs WA_INSTANCE_ID and WA_ACCESS_TOKEN.
* Meta WhatsApp Business Cloud API - the official Graph API. Needs
  WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID.
"""

from __future__ import annotations

import abc
from typing import Any, Final

import httpx
import structlog

from app.config import settings
from app.services.comms.provider_config import is_set

logger = structlog.get_logger(__name__)

_WA_API_VERSION: Final[str] = "v20.0"


class WhatsAppProvider(abc.ABC):
    """Abstract base class for WhatsApp message delivery."""

    # The provider's own explanation for the most recent failure, so the API
    # can say why a message was refused instead of a generic error.
    _last_error: str | None = None

    @property
    def last_error(self) -> str | None:
        """
        The provider's own reason for the most recent failure.

        @returns Provider error text when the last attempt failed, else None
        """
        return self._last_error

    @property
    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Whether real delivery is possible with the current settings."""

    @abc.abstractmethod
    async def send_message(
        self,
        phone: str,
        message: str,
        template_name: str | None = None,
    ) -> bool:
        """
        Send a WhatsApp message to the given phone number.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: Message text (used for free-form or as template fallback)
        @param template_name: Optional WhatsApp-approved template name
        @returns True if the message was accepted for delivery
        """


class GreenAPIWhatsAppProvider(WhatsAppProvider):
    """
    Green API provider (green-api.com).

    Sends through a WhatsApp number already linked to the instance, so no
    Meta Business verification is required.

    Requires environment variables:
    - WA_INSTANCE_ID: e.g. 710722733508
    - WA_ACCESS_TOKEN: the instance API token

    The API host is derived from the instance id: Green API serves instance
    7107... from https://7107.api.green-api.com, and instances in the
    1100... range from https://api.green-api.com.
    """

    def __init__(self) -> None:
        self._instance_id: str = settings.wa_instance_id
        self._api_token: str = settings.wa_access_token
        self._base_url: str = (
            f"{self._host()}/waInstance{self._instance_id}"
            f"/sendMessage/{self._api_token}"
        )

    def _host(self) -> str:
        """
        Resolve the Green API host for this instance.

        @returns Base URL without a trailing slash
        """
        if self._instance_id.startswith("1100"):
            return "https://api.green-api.com"
        return f"https://{self._instance_id[:4]}.api.green-api.com"

    @property
    def is_configured(self) -> bool:
        """Whether an instance id and API token are both present."""
        return is_set(self._instance_id) and is_set(self._api_token)

    async def send_message(
        self,
        phone: str,
        message: str,
        template_name: str | None = None,
    ) -> bool:
        """
        Send a WhatsApp message through Green API.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: Message text
        @param template_name: Ignored - Green API sends plain text
        @returns True if Green API accepted the message
        """
        if not self.is_configured:
            logger.error(
                "green_api_not_configured",
                hint="Set WA_INSTANCE_ID and WA_ACCESS_TOKEN",
            )
            return False

        # Green API addresses a chat as <international number>@c.us
        chat_id = phone.lstrip("+") + "@c.us"

        payload: dict[str, Any] = {
            "chatId": chat_id,
            "message": message,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self._base_url, json=payload)

            if response.status_code == 200:
                data: dict[str, Any] = response.json()
                id_message = data.get("idMessage")
                if id_message:
                    logger.info(
                        "whatsapp_sent",
                        phone=phone,
                        provider="green_api",
                        id_message=id_message,
                    )
                    return True
                self._last_error = (
                    f"Green API replied HTTP 200 without an idMessage: "
                    f"{str(data)[:200]}"
                )
                logger.warning(
                    "whatsapp_no_message_id",
                    phone=phone,
                    provider="green_api",
                    response=data,
                )
                return False

            self._last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.error(
                "whatsapp_api_error",
                phone=phone,
                provider="green_api",
                status_code=response.status_code,
                body=response.text[:500],
            )
            return False

        except (httpx.HTTPError, ValueError) as exc:
            self._last_error = f"network error: {exc}"
            logger.error(
                "whatsapp_network_error",
                phone=phone,
                provider="green_api",
                error=str(exc),
            )
            return False


class WhatsAppCloudProvider(WhatsAppProvider):
    """
    Meta WhatsApp Business Cloud API provider.

    Requires environment variables:
    - WA_ACCESS_TOKEN: Meta Graph API access token
    - WA_PHONE_NUMBER_ID: WhatsApp Business phone number ID
    - WA_BUSINESS_ACCOUNT_ID: WhatsApp Business Account ID (optional)
    """

    def __init__(self) -> None:
        self._access_token: str = settings.wa_access_token
        self._phone_number_id: str = settings.wa_phone_number_id
        self._base_url: str = (
            f"https://graph.facebook.com/{_WA_API_VERSION}"
            f"/{self._phone_number_id}/messages"
        )

    @property
    def is_configured(self) -> bool:
        """Whether an access token and phone number ID are both present."""
        return is_set(self._access_token) and is_set(self._phone_number_id)

    async def send_message(
        self,
        phone: str,
        message: str,
        template_name: str | None = None,
    ) -> bool:
        """
        Send a WhatsApp message via the Meta Cloud API.

        If template_name is provided, sends a template message; otherwise
        sends a free-form text message (requires 24-hour conversation window).

        @param phone: E.164 phone number
        @param message: Text message body
        @param template_name: Optional approved template name
        @returns True if the API accepted the message
        """
        if not self._access_token or not self._phone_number_id:
            logger.error(
                "whatsapp_not_configured",
                hint="Set WA_ACCESS_TOKEN and WA_PHONE_NUMBER_ID",
            )
            return False

        # Strip the leading '+' — WhatsApp Cloud API expects digits only
        clean_phone = phone.lstrip("+")

        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any]
        if template_name:
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "template",
                "template": {
                    "name": template_name,
                    "language": {"code": "en"},
                },
            }
        else:
            payload = {
                "messaging_product": "whatsapp",
                "to": clean_phone,
                "type": "text",
                "text": {"body": message},
            }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._base_url,
                    headers=headers,
                    json=payload,
                )

            if response.status_code in (200, 201):
                data = response.json()
                wa_message_id = (
                    data.get("messages", [{}])[0].get("id")
                    if data.get("messages")
                    else None
                )
                logger.info(
                    "whatsapp_sent",
                    phone=phone,
                    provider="meta_cloud",
                    wa_message_id=wa_message_id,
                    template=template_name,
                )
                return True

            self._last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.error(
                "whatsapp_api_error",
                phone=phone,
                provider="meta_cloud",
                status_code=response.status_code,
                body=response.text[:500],
            )
            return False

        except httpx.HTTPError as exc:
            self._last_error = f"network error: {exc}"
            logger.error(
                "whatsapp_network_error",
                phone=phone,
                provider="meta_cloud",
                error=str(exc),
            )
            return False


class MockWhatsAppProvider(WhatsAppProvider):
    """
    Mock WhatsApp provider for development and testing.
    Logs messages via structlog instead of sending them.
    """

    @property
    def is_configured(self) -> bool:
        """Always False — this provider never delivers."""
        return False

    async def send_message(
        self,
        phone: str,
        message: str,
        template_name: str | None = None,
    ) -> bool:
        """
        Log the WhatsApp message instead of sending it.

        @param phone: Target phone number
        @param message: Message body
        @param template_name: Optional template name
        @returns Always True
        """
        logger.info(
            "mock_whatsapp_sent",
            phone=phone,
            message=message[:100],
            template=template_name,
            provider="mock",
        )
        return True


def get_whatsapp_provider() -> WhatsAppProvider:
    """
    Factory: return the configured WhatsApp provider based on environment.

    @returns WhatsAppProvider instance (Green API, Meta Cloud, or Mock)
    """
    if is_set(settings.wa_instance_id) and is_set(settings.wa_access_token):
        return GreenAPIWhatsAppProvider()
    if is_set(settings.wa_access_token) and is_set(settings.wa_phone_number_id):
        return WhatsAppCloudProvider()
    logger.warning(
        "whatsapp_provider_fallback_to_mock",
        reason="neither Green API nor Meta Cloud credentials are set",
    )
    return MockWhatsAppProvider()
