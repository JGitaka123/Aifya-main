"""SMS provider abstraction and Africa's Talking integration."""

from __future__ import annotations

import abc
from typing import Final, Literal

import httpx
import structlog

from app.config import settings
from app.services.comms.provider_config import is_set

logger = structlog.get_logger(__name__)

# Africa's Talking API endpoint
_AT_SMS_URL: Final[str] = "https://api.africastalking.com/version1/messaging"
_AT_SANDBOX_URL: Final[str] = (
    "https://api.sandbox.africastalking.com/version1/messaging"
)


class SMSProvider(abc.ABC):
    """Abstract base class for SMS delivery providers."""

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
    async def send_sms(self, phone: str, message: str) -> bool:
        """
        Send an SMS message to the given phone number.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: Message body (max 160 chars for single SMS)
        @returns True if the SMS was accepted for delivery
        """


class AfricasTalkingProvider(SMSProvider):
    """
    Africa's Talking SMS provider — the most popular SMS gateway in Kenya.

    Requires environment variables:
    - AT_API_KEY: Africa's Talking API key
    - AT_USERNAME: Africa's Talking username
    - AT_SENDER_ID: Optional sender ID (alphanumeric, registered with AT)
    - AT_SANDBOX: Set to "true" for sandbox mode
    """

    def __init__(self) -> None:
        self._api_key: str = settings.at_api_key
        self._username: str = settings.at_username
        self._sender_id: str | None = settings.at_sender_id or None
        self._sandbox: bool = settings.at_sandbox
        self._base_url: str = _AT_SANDBOX_URL if self._sandbox else _AT_SMS_URL

    @property
    def is_configured(self) -> bool:
        """Whether an API key and username are both present."""
        return is_set(self._api_key) and is_set(self._username)

    async def send_sms(self, phone: str, message: str) -> bool:
        """
        Send SMS via Africa's Talking HTTP API.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: SMS body text
        @returns True if the API accepted the message for delivery
        """
        if not self.is_configured:
            logger.error(
                "africas_talking_not_configured",
                hint="Set AT_API_KEY and a real AT_USERNAME (not the .env.example placeholder)",
            )
            return False

        outcome = await self._attempt(phone, message, self._sender_id)
        if outcome is None:
            return True

        # An alphanumeric sender ID has to be registered and approved on the
        # Africa's Talking account. Until it is, every send is refused because
        # of that ID, so retry once from the account's default shortcode
        # rather than losing the message. A refused send is never delivered,
        # so this cannot produce a duplicate.
        if outcome != "rejected" or not self._sender_id:
            return False

        logger.warning(
            "africas_talking_sender_id_fallback",
            phone=phone,
            sender_id=self._sender_id,
        )
        return await self._attempt(phone, message, "") is None

    async def _attempt(
        self, phone: str, message: str, sender_id: str
    ) -> Literal["rejected", "api_error", "network_error"] | None:
        """
        Perform a single Africa's Talking send.

        @param phone: E.164 phone number (e.g., +254712345678)
        @param message: SMS body text
        @param sender_id: Alphanumeric sender ID, or "" for the default shortcode
        @returns None when accepted, otherwise why the gateway refused it
        """
        headers = {
            "apiKey": self._api_key,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }

        payload: dict[str, str] = {
            "username": self._username,
            "to": phone,
            "message": message,
        }
        if sender_id:
            payload["from"] = sender_id

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._base_url,
                    headers=headers,
                    data=payload,
                )

            if response.status_code == 201:
                data = response.json()
                recipients = (
                    data.get("SMSMessageData", {}).get("Recipients", [])
                )
                if recipients:
                    status_code = recipients[0].get("statusCode", 0)
                    if status_code in (100, 101):
                        logger.info(
                            "sms_sent",
                            phone=phone,
                            provider="africas_talking",
                            at_status=status_code,
                            sender_id=sender_id or "default",
                        )
                        return None

                    at_status = recipients[0].get("status", "unknown")
                else:
                    status_code = 0
                    at_status = "no recipients in the response"
                self._last_error = f"{at_status} (statusCode {status_code})"

                logger.warning(
                    "sms_rejected",
                    phone=phone,
                    provider="africas_talking",
                    sender_id=sender_id or "default",
                    response=data,
                )
                return "rejected"

            self._last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            logger.error(
                "sms_api_error",
                phone=phone,
                provider="africas_talking",
                status_code=response.status_code,
                body=response.text[:500],
            )
            return "api_error"

        except httpx.HTTPError as exc:
            self._last_error = f"network error: {exc}"
            logger.error(
                "sms_network_error",
                phone=phone,
                provider="africas_talking",
                error=str(exc),
            )
            return "network_error"


class MockSMSProvider(SMSProvider):
    """
    Mock SMS provider for development and testing.
    Logs messages via structlog instead of sending them.
    """

    @property
    def is_configured(self) -> bool:
        """Always False — this provider never delivers."""
        return False

    async def send_sms(self, phone: str, message: str) -> bool:
        """
        Log the SMS message instead of sending it.

        @param phone: Target phone number
        @param message: Message body
        @returns Always True
        """
        logger.info(
            "mock_sms_sent",
            phone=phone,
            message=message[:100],
            provider="mock",
        )
        return True


def get_sms_provider() -> SMSProvider:
    """
    Factory: return the configured SMS provider based on environment.

    @returns SMSProvider instance (Africa's Talking or Mock)
    """
    if is_set(settings.at_api_key):
        return AfricasTalkingProvider()
    logger.warning("sms_provider_fallback_to_mock", reason="AT_API_KEY not set")
    return MockSMSProvider()
