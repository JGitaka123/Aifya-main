"""Speak text aloud through a pluggable text-to-speech provider.

A provider does exactly two things: it turns text into audio bytes, and it
raises TTSError instead of hanging when it cannot. Nothing here decides who is
called next - the queue engine owns that. The voice layer only says what the
queue has already decided.

Five providers are supported. OpenAI-compatible endpoints, ElevenLabs and
Azure Speech are called over plain httpx, so the gateway keeps no vendor SDK
dependency. Azure, and the free keyless Edge Read Aloud endpoint, are what
supply the African neural voices (the Kenyan English voice the other vendors
do not offer). The local provider drives pyttsx3 on the host and needs
neither a key nor the network, which is what a clinic with no internet or no
vendor contract uses.
"""

from __future__ import annotations

import asyncio
import os
import re
import tempfile
from dataclasses import dataclass
from typing import Protocol
from xml.sax.saxutils import escape

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


#: Azure voice names are "<locale>-<Name>Neural", so the SSML language can be
#: read straight off the voice instead of needing a second setting.
_AZURE_VOICE_PATTERN = re.compile(r"^([a-z]{2}-[A-Z]{2})-")

#: Our audio_format values mapped to the X-Microsoft-OutputFormat Azure wants.
_AZURE_OUTPUT_FORMATS = {
    "mp3": "audio-24khz-48kbitrate-mono-mp3",
    "wav": "riff-24khz-16bit-mono-pcm",
    "pcm": "raw-24khz-16bit-mono-pcm",
    "opus": "ogg-24khz-16bit-mono-opus",
}
_AZURE_FALLBACK_FORMAT = "mp3"

#: The voice used when TTS_VOICE is blank or still holds an OpenAI voice name.
#: Azure and Edge both serve this Kenyan voice, so an untouched
#: TTS_VOICE=alloy still gets an African accent instead of a 400 from Azure.
DEFAULT_NEURAL_VOICE = "en-KE-AsiliaNeural"

#: Voice names that belong to the OpenAI provider and mean nothing to Azure.
_OPENAI_VOICE_NAMES = frozenset(
    {
        "alloy",
        "ash",
        "ballad",
        "coral",
        "echo",
        "fable",
        "nova",
        "onyx",
        "sage",
        "shimmer",
        "verse",
    }
)


def _voice_locale(voice: str) -> str | None:
    """Return the locale embedded in an Azure voice name, if there is one.

    @param voice: An Azure voice name, e.g. ``en-KE-AsiliaNeural``
    @returns The locale (``en-KE``), or None when the name carries none
    """

    match = _AZURE_VOICE_PATTERN.match(voice or "")
    return match.group(1) if match else None


def _neural_voice(requested: str, default: str) -> str:
    """Pick the Azure voice name, ignoring blanks and OpenAI voice names.

    @param requested: The configured TTS_VOICE value
    @param default: The voice to use when ``requested`` is not an Azure name
    @returns The voice name to send in the SSML
    """

    candidate = (requested or "").strip()
    if not candidate or candidate.lower() in _OPENAI_VOICE_NAMES:
        return default
    return candidate


def _build_ssml(text: str, voice: str, language: str) -> str:
    """Wrap the text in the single-voice SSML Azure expects.

    @param text: The words to speak
    @param voice: The Azure voice name
    @param language: Fallback locale when the voice name carries none
    @returns The SSML document
    """

    locale = _voice_locale(voice) or (language or "").strip() or "en-KE"
    return (
        f"<speak version='1.0' xml:lang='{locale}'>"
        f"<voice xml:lang='{locale}' name='{voice}'>{escape(text)}</voice>"
        "</speak>"
    )


class AzureTTSProvider:
    """Azure Speech text-to-speech, for its African neural voices.

    Azure is the only provider here with a genuine Kenyan English female voice
    (``en-KE-AsiliaNeural``, or ``sw-KE-ZuriNeural`` for Kiswahili). It speaks
    a different protocol from the OpenAI-compatible endpoint: SSML in the body,
    the subscription key in ``Ocp-Apim-Subscription-Key``, and the container
    format chosen with ``X-Microsoft-OutputFormat``.
    """

    name = "azure"

    def __init__(
        self,
        api_key: str,
        *,
        region: str = "",
        endpoint: str = "",
        default_voice: str = DEFAULT_NEURAL_VOICE,
        timeout: float = 45.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.region = (region or "").strip()
        self.endpoint = (endpoint or "").strip().rstrip("/")
        self.default_voice = default_voice
        self.timeout = timeout
        # Injectable so tests can answer from a mock transport instead of the
        # network; production leaves it None and httpx picks its default.
        self._transport = transport

    def _url(self) -> str:
        """The configured endpoint, or the one built from the region.

        @returns The Azure Speech synthesis URL
        """

        if self.endpoint:
            return self.endpoint
        if not self.region:
            raise TTSError(
                "Azure text-to-speech needs TTS_AZURE_REGION (or TTS_AZURE_ENDPOINT)"
            )
        return f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        chosen_voice = _neural_voice(voice, self.default_voice)
        fmt = (audio_format or "").strip().lower()
        if fmt not in _AZURE_OUTPUT_FORMATS:
            fmt = _AZURE_FALLBACK_FORMAT
        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": _AZURE_OUTPUT_FORMATS[fmt],
            "User-Agent": "aifya-api-gateway",
        }
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    self._url(),
                    content=_build_ssml(text, chosen_voice, language),
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
            content_type=CONTENT_TYPES.get(fmt, "audio/mpeg"),
            provider=self.name,
            voice=chosen_voice,
        )


class EdgeTTSProvider:
    """Microsoft Edge's Read Aloud voices: the Azure catalogue, minus the key.

    Edge Read Aloud reaches the same neural voices as Azure Speech - including
    the Kenyan English ``en-KE-AsiliaNeural`` and ``sw-KE-ZuriNeural`` - over
    its own websocket, with no subscription and no account. It does need
    internet, and it is an undocumented Microsoft endpoint, so a facility that
    wants a supported contract should use the Azure provider instead.
    """

    name = "edge"

    def __init__(self, *, default_voice: str = DEFAULT_NEURAL_VOICE) -> None:
        self.default_voice = default_voice

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        try:
            import edge_tts
        except ImportError as exc:
            raise TTSError(
                "Edge text-to-speech needs the edge-tts package; install it or "
                "set TTS_PROVIDER back to local or azure"
            ) from exc

        chosen_voice = _neural_voice(voice, self.default_voice)
        try:
            chunks: list[bytes] = []
            communicate = edge_tts.Communicate(text, chosen_voice)
            async for chunk in communicate.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    chunks.append(chunk["data"])
        except Exception as exc:
            raise TTSError(f"Edge text-to-speech failed: {exc}") from exc

        data = b"".join(chunks)
        if not data:
            raise TTSError("Edge text-to-speech produced no audio")
        return SpeechAudio(
            data=data,
            content_type="audio/mpeg",
            provider=self.name,
            voice=chosen_voice,
        )


def _match_voice(voices: list, wanted: str | None) -> str | None:
    """Find the host voice whose id or name matches the configured value.

    A clinic may name a voice, give its index, or leave the OpenAI default
    ("alloy") in place. Only a real match is honoured; anything else keeps the
    engine's own default rather than failing the announcement.

    @param voices: The pyttsx3 voice objects reported by the engine
    @param wanted: The configured voice name, id or zero-based index
    @returns The voice id to select, or None to keep the engine default
    """

    candidate = (wanted or "").strip()
    if not candidate:
        return None
    if candidate.isdigit():
        index = int(candidate)
        if 0 <= index < len(voices):
            return voices[index].id
        return None
    needle = candidate.lower()
    for voice in voices:
        haystack = f"{getattr(voice, 'id', '')} {getattr(voice, 'name', '')}".lower()
        if needle in haystack:
            return voice.id
    return None


class LocalTTSProvider:
    """Offline text-to-speech through the operating system's own voices.

    pyttsx3 talks to SAPI5 on Windows, NSSpeechSynthesizer on macOS and espeak
    on Linux. The engine is synchronous and keeps process-wide driver state, so
    every render runs in a worker thread and writes a temporary WAV that the
    API streams back. The requested format is ignored: pyttsx3 renders WAV only.
    """

    name = "local"

    def __init__(
        self, *, rate: int | None = None, volume: float | None = None
    ) -> None:
        self.rate = rate
        self.volume = volume

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        data = await asyncio.to_thread(self._render, text, voice)
        if not data:
            raise TTSError("Local text-to-speech produced no audio")
        return SpeechAudio(
            data=data,
            content_type="audio/wav",
            provider=self.name,
            voice=voice or "",
        )

    def _render(self, text: str, voice: str) -> bytes:
        """Render one clip on a worker thread and return its WAV bytes."""

        try:
            import pyttsx3
        except ImportError as exc:
            raise TTSError(
                "Local text-to-speech needs the pyttsx3 package; install it or "
                "set TTS_PROVIDER back to openai or elevenlabs"
            ) from exc

        try:
            engine = pyttsx3.init()
        except Exception as exc:
            # A host with no speech driver installed reaches here.
            raise TTSError(f"Could not start the local speech engine: {exc}") from exc

        path: str | None = None
        try:
            if self.rate:
                engine.setProperty("rate", int(self.rate))
            if self.volume is not None:
                engine.setProperty("volume", float(self.volume))
            selected = _match_voice(engine.getProperty("voices") or [], voice)
            if selected is not None:
                engine.setProperty("voice", selected)

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                path = handle.name
            engine.save_to_file(text, path)
            engine.runAndWait()
            with open(path, "rb") as rendered:
                return rendered.read()
        except TTSError:
            raise
        except Exception as exc:
            raise TTSError(f"Local text-to-speech failed: {exc}") from exc
        finally:
            try:
                engine.stop()
            except Exception:
                pass
            if path is not None:
                try:
                    os.unlink(path)
                except OSError:
                    pass


def provider_from_settings() -> TTSProvider | None:
    """Build the configured provider, or None when voice is switched off.

    A missing key is not an error: the queue still runs, the board still
    updates, and the speaker simply has nothing to play. That is the graceful
    degradation the queue rules ask for.
    The local provider is the exception to the key rule: it renders on the
    host, so it needs no key at all.
    """

    if not settings.voice_enabled:
        return None
    provider = (settings.tts_provider or "openai").strip().lower()
    if provider == "local":
        # The host already owns a speech engine; no key or network is involved.
        return LocalTTSProvider(
            rate=settings.tts_local_rate, volume=settings.tts_local_volume
        )
    if provider == "edge":
        # Same neural voices as Azure, but no key or account is involved.
        return EdgeTTSProvider()
    if not settings.tts_api_key:
        return None
    if provider == "azure":
        # Azure Speech, for the Kenyan voices the other vendors lack.
        return AzureTTSProvider(
            api_key=settings.tts_api_key,
            region=settings.tts_azure_region,
            endpoint=settings.tts_azure_endpoint,
        )
    if provider == "elevenlabs":
        return ElevenLabsTTSProvider(
            api_key=settings.tts_api_key, base_url=settings.tts_base_url
        )
    return OpenAITTSProvider(
        api_key=settings.tts_api_key, base_url=settings.tts_base_url
    )
