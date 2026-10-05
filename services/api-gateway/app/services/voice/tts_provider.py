"""Speak text aloud through a pluggable text-to-speech provider.

A provider does exactly two things: it turns text into audio bytes, and it
raises TTSError instead of hanging when it cannot. Nothing here decides who is
called next - the queue engine owns that. The voice layer only says what the
queue has already decided.

Two vendors are supported because Kenyan facilities buy keys differently:
OpenAI-compatible endpoints and ElevenLabs. Both are called over plain httpx,
so the AI service keeps no vendor SDK dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from app.config import settings

CONTENT_TYPES = {
    "mp3": "audio/mpeg",
    "opus": "audio/ogg",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/wav",
}


class TTSError(RuntimeError):
    """Raised when a provider cannot produce audio for a request."""


@dataclass(frozen=True)
class SpeechAudio:
    """Audio ready to be streamed to a speaker."""

    data: bytes
    content_type: str
    provider: str
    voice: str


class TTSProvider(Protocol):
    """The seam every vendor adapter implements."""

    name: str

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        """Return spoken audio for the text."""


class OpenAITTSProvider:
    """Any OpenAI-compatible /audio/speech endpoint."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout: float = 45.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or "https://api.openai.com/v1").rstrip("/")
        self.timeout = timeout
        # Injectable so tests can answer from a mock transport instead of the
        # network; production leaves it None and httpx picks its default.
        self._transport = transport

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        payload = {
            "model": model,
            "voice": voice,
            "input": text,
            "response_format": audio_format,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self.base_url}/audio/speech", json=payload, headers=headers
                )
        except httpx.HTTPError as exc:
            raise TTSError(f"Text-to-speech request failed: {exc}") from exc

        if response.status_code >= 400:
            raise TTSError(
                f"Text-to-speech provider returned {response.status_code}: "
                f"{response.text[:300]}"
            )
        return SpeechAudio(
            data=response.content,
            content_type=CONTENT_TYPES.get(audio_format, "audio/mpeg"),
            provider=self.name,
            voice=voice,
        )


class ElevenLabsTTSProvider:
    """ElevenLabs text-to-speech.

    The voice is configured as a voice id rather than a name, which is what
    the ElevenLabs API expects.
    """

    name = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.elevenlabs.io",
        timeout: float = 45.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = (base_url or "https://api.elevenlabs.io").rstrip("/")
        self.timeout = timeout
        self._transport = transport

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        headers = {"xi-api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "text": text,
            "model_id": model or "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    f"{self.base_url}/v1/text-to-speech/{voice}",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise TTSError(f"Text-to-speech request failed: {exc}") from exc

        if response.status_code >= 400:
            raise TTSError(
                f"Text-to-speech provider returned {response.status_code}: "
                f"{response.text[:300]}"
            )
        return SpeechAudio(
            data=response.content,
            content_type=response.headers.get("content-type", "audio/mpeg"),
            provider=self.name,
            voice=voice,
        )


def provider_from_settings() -> TTSProvider | None:
    """Build the configured provider, or None when voice is switched off.

    A missing key is not an error: the queue still runs, the board still
    updates, and the speaker simply has nothing to play. That is the graceful
    degradation the queue rules ask for.
    """

    if not settings.voice_enabled or not settings.tts_api_key:
        return None
    provider = (settings.tts_provider or "openai").strip().lower()
    if provider == "elevenlabs":
        return ElevenLabsTTSProvider(
            api_key=settings.tts_api_key, base_url=settings.tts_base_url
        )
    return OpenAITTSProvider(
        api_key=settings.tts_api_key, base_url=settings.tts_base_url
    )
