"""Email provider abstraction with SMTP (STARTTLS) delivery.

Mirrors the SMS and WhatsApp providers so the Communication Hub can treat all
three channels the same way. Delivery runs on a worker thread because the
stdlib ``smtplib`` client is blocking.
"""

from __future__ import annotations

import abc
import asyncio
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from typing import Final

import structlog

from app.config import settings
from app.services.comms.provider_config import is_set

logger = structlog.get_logger(__name__)

_SMTP_TIMEOUT_SECONDS: Final[float] = 30.0


class EmailProvider(abc.ABC):
    """Abstract base class for outbound email delivery."""

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
    async def send_email(self, address: str, subject: str, body: str) -> bool:
        """
        Send an email to the given address.

        @param address: Recipient email address
        @param subject: Subject line
        @param body: Plain-text message body
        @returns True if the SMTP server accepted the message for delivery
        """


class SMTPEmailProvider(EmailProvider):
    """
    SMTP email provider (STARTTLS on port 587 by default).

    Requires environment variables:
    - SMTP_HOST: mail server hostname
    - SMTP_PORT: mail server port (default 587)
    - SMTP_USERNAME / SMTP_PASSWORD: credentials, when the server needs auth
    - SMTP_FROM_EMAIL: envelope sender (falls back to SMTP_USERNAME)
    - SMTP_FROM_NAME: display name shown to the patient
    - SMTP_USE_TLS: set to "false" to skip STARTTLS (e.g. a local relay)
    """

    @property
    def is_configured(self) -> bool:
        """Whether a host and a sender address are both set."""
        return is_set(settings.smtp_host) and is_set(self._from_email)

    def __init__(self) -> None:
        self._host: str = settings.smtp_host
        self._port: int = settings.smtp_port
        self._username: str = settings.smtp_username
        self._password: str = settings.smtp_password
        self._from_email: str = settings.smtp_from_email or settings.smtp_username

    async def send_email(self, address: str, subject: str, body: str) -> bool:
        """
        Send an email via SMTP without blocking the event loop.

        @param address: Recipient email address
        @param subject: Subject line
        @param body: Plain-text message body
        @returns True if the server accepted the message
        """
        if not self.is_configured:
            logger.error(
                "email_not_configured",
                hint="Set SMTP_HOST and SMTP_FROM_EMAIL",
            )
            return False

        try:
            await asyncio.to_thread(self._send_sync, address, subject, body)
        except (OSError, smtplib.SMTPException) as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            logger.error(
                "email_send_failed",
                address=address,
                provider="smtp",
                error=str(exc),
            )
            return False

        logger.info(
            "email_sent",
            address=address,
            provider="smtp",
            host=self._host,
        )
        return True

    def _send_sync(self, address: str, subject: str, body: str) -> None:
        """
        Blocking SMTP conversation. Runs on a worker thread.

        @param address: Recipient email address
        @param subject: Subject line
        @param body: Plain-text message body
        @raises OSError: When the server is unreachable or rejects the message
        """
        message = EmailMessage()
        message["From"] = formataddr((settings.smtp_from_name, self._from_email))
        message["To"] = address
        message["Subject"] = subject
        message.set_content(body)

        with smtplib.SMTP(self._host, self._port, timeout=_SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.ehlo()
            if settings.smtp_use_tls:
                smtp.starttls()
                smtp.ehlo()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(message)


class MockEmailProvider(EmailProvider):
    """
    Mock email provider for development. Logs the message instead of sending it.
    Reported as unconfigured so callers can tell mock output from real delivery.
    """

    @property
    def is_configured(self) -> bool:
        """Always False — this provider never delivers."""
        return False

    async def send_email(self, address: str, subject: str, body: str) -> bool:
        """
        Log the email instead of sending it.

        @param address: Recipient email address
        @param subject: Subject line
        @param body: Plain-text message body
        @returns Always True so local flows can be exercised
        """
        logger.info(
            "mock_email_sent",
            address=address,
            subject=subject,
            body=body[:100],
            provider="mock",
        )
        return True


def get_email_provider() -> EmailProvider:
    """
    Factory: return the configured email provider based on settings.

    @returns EmailProvider instance (SMTP or Mock)
    """
    if is_set(settings.smtp_host):
        return SMTPEmailProvider()
    logger.warning("email_provider_fallback_to_mock", reason="SMTP_HOST not set")
    return MockEmailProvider()