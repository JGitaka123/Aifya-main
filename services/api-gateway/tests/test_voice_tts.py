"""Voice/TTS provider integration and announcement caching.

The vendor adapters are exercised through ``httpx.MockTransport`` so the tests
prove the exact request each provider sends (URL, auth header, payload) and how
each failure becomes a ``TTSError`` - no network, no API key, no flakiness.

The local provider is driven with a fake ``pyttsx3`` module injected into
``sys.modules``, so the suite never needs a host speech driver.

The caching tests drive ``AnnouncementService`` with a counting provider: the
same call twice must synthesise once, and a provider failure must be recorded
on the row instead of raised, because the queue must never block on a speaker.
"""

from __future__ import annotations

import json
import os
import sys
import types
import uuid

import httpx
import pytest

from app.config import settings
from app.services.queue.queue_service import QueueService
from app.services.voice.announcement_service import (
    AnnouncementService,
    clear_clip_cache,
)
from app.services.voice.text import cache_key, normalise_for_speech
from app.services.voice.tts_provider import (
    DEFAULT_NEURAL_VOICE,
    AzureTTSProvider,
    EdgeTTSProvider,
    ElevenLabsTTSProvider,
    LocalTTSProvider,
    OpenAITTSProvider,
    SpeechAudio,
    TTSError,
    _match_voice,
    _neural_voice,
    _voice_locale,
    provider_from_settings,
)

#: The facility the test client's JWT is scoped to (see tests/conftest.py).
FACILITY_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _as_json(request: httpx.Request) -> dict:
    return json.loads(request.content.decode("utf-8"))


@pytest.mark.asyncio
async def test_openai_provider_sends_expected_request() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = _as_json(request)
        return httpx.Response(
            200, content=b"ID3-audio", headers={"content-type": "audio/mpeg"}
        )

    provider = OpenAITTSProvider(
        api_key="secret-key",
        base_url="https://tts.example/v1",
        transport=httpx.MockTransport(handler),
    )
    audio = await provider.synthesise(
        "Ticket O P D zero zero one",
        voice="nova",
        model="gpt-4o-mini-tts",
        audio_format="mp3",
        language="en",
    )

    assert seen["url"] == "https://tts.example/v1/audio/speech"
    assert seen["auth"] == "Bearer secret-key"
    assert seen["body"] == {
        "model": "gpt-4o-mini-tts",
        "voice": "nova",
        "input": "Ticket O P D zero zero one",
        "response_format": "mp3",
    }
    assert audio.data == b"ID3-audio"
    assert audio.content_type == "audio/mpeg"
    assert audio.provider == "openai"


@pytest.mark.asyncio
async def test_openai_provider_wraps_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    provider = OpenAITTSProvider(
        api_key="k", base_url="https://tts.example/v1",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(TTSError):
        await provider.synthesise(
            "hello", voice="alloy", model="m", audio_format="mp3", language="en"
        )


@pytest.mark.asyncio
async def test_openai_provider_raises_on_error_status() -> None:
    provider = OpenAITTSProvider(
        api_key="k",
        base_url="https://tts.example/v1",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(429, text="rate limited")
        ),
    )
    with pytest.raises(TTSError) as exc:
        await provider.synthesise(
            "hello", voice="alloy", model="m", audio_format="mp3", language="en"
        )
    assert "429" in str(exc.value)


@pytest.mark.asyncio
async def test_elevenlabs_provider_uses_voice_id_in_path() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("xi-api-key")
        seen["body"] = _as_json(request)
        return httpx.Response(200, content=b"mp3-bytes")

    provider = ElevenLabsTTSProvider(
        api_key="eleven-key",
        base_url="https://api.elevenlabs.io",
        transport=httpx.MockTransport(handler),
    )
    audio = await provider.synthesise(
        "Ticket one two three",
        voice="voice-id-42",
        model="eleven_multilingual_v2",
        audio_format="mp3",
        language="en",
    )

    assert seen["url"] == "https://api.elevenlabs.io/v1/text-to-speech/voice-id-42"
    assert seen["key"] == "eleven-key"
    assert seen["body"]["model_id"] == "eleven_multilingual_v2"
    assert audio.data == b"mp3-bytes"
    assert audio.provider == "elevenlabs"


def test_provider_is_none_when_voice_is_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "voice_enabled", False)
    monkeypatch.setattr(settings, "tts_api_key", "still-a-key")
    assert provider_from_settings() is None


def test_provider_is_none_without_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "tts_provider", "openai")
    monkeypatch.setattr(settings, "tts_api_key", "")
    assert provider_from_settings() is None


def test_provider_selection_follows_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "tts_api_key", "k")
    monkeypatch.setattr(settings, "tts_provider", "elevenlabs")
    assert isinstance(provider_from_settings(), ElevenLabsTTSProvider)

    monkeypatch.setattr(settings, "tts_provider", "openai")
    assert isinstance(provider_from_settings(), OpenAITTSProvider)


def test_local_provider_is_selected_without_an_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "tts_provider", "local")
    monkeypatch.setattr(settings, "tts_api_key", "")
    assert isinstance(provider_from_settings(), LocalTTSProvider)


class _FakeVoice:
    def __init__(self, voice_id: str, label: str) -> None:
        self.id = voice_id
        self.name = label


class _FakeEngine:
    """A stand-in for pyttsx3's engine that records what it was told."""

    def __init__(self) -> None:
        self.properties: dict = {}
        self.voices = [
            _FakeVoice("voice-a", "Microsoft Zira Desktop"),
            _FakeVoice("voice-b", "Microsoft David Desktop"),
        ]
        self.said: tuple[str, str] | None = None

    def getProperty(self, key: str):
        if key == "voices":
            return self.voices
        return self.properties.get(key)

    def setProperty(self, key: str, value) -> None:
        self.properties[key] = value

    def save_to_file(self, text: str, path: str) -> None:
        self.said = (text, path)
        with open(path, "wb") as handle:
            handle.write(b"RIFF-local-wav")

    def runAndWait(self) -> None:
        return None

    def stop(self) -> None:
        return None


@pytest.mark.asyncio
async def test_local_provider_renders_wav_on_the_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _FakeEngine()
    fake_module = types.SimpleNamespace(init=lambda: engine)
    monkeypatch.setitem(sys.modules, "pyttsx3", fake_module)

    provider = LocalTTSProvider(rate=200, volume=0.5)
    audio = await provider.synthesise(
        "Ticket O P D zero zero one",
        voice="zira",
        model="",
        audio_format="mp3",
        language="en",
    )

    assert audio.data == b"RIFF-local-wav"
    assert audio.content_type == "audio/wav"
    assert audio.provider == "local"
    assert engine.properties["rate"] == 200
    assert engine.properties["volume"] == 0.5
    assert engine.properties["voice"] == "voice-a"
    assert engine.said is not None
    assert engine.said[0] == "Ticket O P D zero zero one"
    assert not os.path.exists(engine.said[1])


@pytest.mark.asyncio
async def test_local_provider_reports_a_missing_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pyttsx3", None)
    provider = LocalTTSProvider()
    with pytest.raises(TTSError, match="pyttsx3"):
        await provider.synthesise(
            "hello", voice="", model="", audio_format="wav", language="en"
        )


def test_match_voice_by_name_index_and_default() -> None:
    voices = [
        _FakeVoice("voice-a", "Microsoft Zira"),
        _FakeVoice("voice-b", "Microsoft David"),
    ]
    assert _match_voice(voices, "zira") == "voice-a"
    assert _match_voice(voices, "1") == "voice-b"
    assert _match_voice(voices, "") is None
    assert _match_voice(voices, "alloy") is None
    assert _match_voice(voices, "9") is None


def _ssml_body(request: httpx.Request) -> str:
    return request.content.decode("utf-8")


@pytest.mark.asyncio
async def test_azure_provider_sends_ssml_with_the_kenyan_voice() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("ocp-apim-subscription-key")
        seen["content_type"] = request.headers.get("content-type")
        seen["output_format"] = request.headers.get("x-microsoft-outputformat")
        seen["user_agent"] = request.headers.get("user-agent")
        seen["body"] = _ssml_body(request)
        return httpx.Response(200, content=b"ID3-azure")

    provider = AzureTTSProvider(
        api_key="azure-key",
        region="southafricanorth",
        transport=httpx.MockTransport(handler),
    )
    audio = await provider.synthesise(
        "Ticket O P D zero zero one",
        voice="en-KE-AsiliaNeural",
        model="",
        audio_format="mp3",
        language="en",
    )

    assert seen["url"] == (
        "https://southafricanorth.tts.speech.microsoft.com/cognitiveservices/v1"
    )
    assert seen["key"] == "azure-key"
    assert seen["content_type"] == "application/ssml+xml"
    assert seen["output_format"] == "audio-24khz-48kbitrate-mono-mp3"
    assert seen["user_agent"] == "aifya-api-gateway"
    assert "name='en-KE-AsiliaNeural'" in seen["body"]
    assert "xml:lang='en-KE'" in seen["body"]
    assert "Ticket O P D zero zero one" in seen["body"]
    assert audio.data == b"ID3-azure"
    assert audio.content_type == "audio/mpeg"
    assert audio.provider == "azure"
    assert audio.voice == "en-KE-AsiliaNeural"


@pytest.mark.asyncio
async def test_azure_provider_uses_the_kiswahili_voice_locale() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _ssml_body(request)
        return httpx.Response(200, content=b"mp3-bytes")

    provider = AzureTTSProvider(
        api_key="k", region="eastus", transport=httpx.MockTransport(handler)
    )
    await provider.synthesise(
        "Tikiti namba moja",
        voice="sw-KE-ZuriNeural",
        model="",
        audio_format="mp3",
        language="en",
    )

    assert "name='sw-KE-ZuriNeural'" in seen["body"]
    assert "xml:lang='sw-KE'" in seen["body"]


@pytest.mark.asyncio
async def test_azure_provider_ignores_the_openai_default_voice() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _ssml_body(request)
        return httpx.Response(200, content=b"mp3-bytes")

    provider = AzureTTSProvider(
        api_key="k", region="eastus", transport=httpx.MockTransport(handler)
    )
    audio = await provider.synthesise(
        "hello", voice="alloy", model="", audio_format="mp3", language="en"
    )

    assert "name='%s'" % DEFAULT_NEURAL_VOICE in seen["body"]
    assert audio.voice == DEFAULT_NEURAL_VOICE


@pytest.mark.asyncio
async def test_azure_provider_escapes_ssml_and_maps_wav() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = _ssml_body(request)
        seen["output_format"] = request.headers.get("x-microsoft-outputformat")
        return httpx.Response(200, content=b"RIFF")

    provider = AzureTTSProvider(
        api_key="k", region="eastus", transport=httpx.MockTransport(handler)
    )
    audio = await provider.synthesise(
        "Beds & Beyond <2>",
        voice="en-KE-AsiliaNeural",
        model="",
        audio_format="wav",
        language="en",
    )

    assert "Beds &amp; Beyond &lt;2&gt;" in seen["body"]
    assert seen["output_format"] == "riff-24khz-16bit-mono-pcm"
    assert audio.content_type == "audio/wav"


@pytest.mark.asyncio
async def test_azure_provider_falls_back_to_mp3_for_an_unknown_format() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["output_format"] = request.headers.get("x-microsoft-outputformat")
        return httpx.Response(200, content=b"mp3-bytes")

    provider = AzureTTSProvider(
        api_key="k", region="eastus", transport=httpx.MockTransport(handler)
    )
    audio = await provider.synthesise(
        "hello",
        voice="en-KE-AsiliaNeural",
        model="",
        audio_format="flac",
        language="en",
    )

    assert seen["output_format"] == "audio-24khz-48kbitrate-mono-mp3"
    assert audio.content_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_azure_provider_accepts_an_explicit_endpoint() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        return httpx.Response(200, content=b"mp3-bytes")

    provider = AzureTTSProvider(
        api_key="k",
        endpoint="https://speech.example.cloud/tts/",
        transport=httpx.MockTransport(handler),
    )
    await provider.synthesise(
        "hello",
        voice="en-KE-AsiliaNeural",
        model="",
        audio_format="mp3",
        language="en",
    )

    assert seen["url"] == "https://speech.example.cloud/tts"


@pytest.mark.asyncio
async def test_azure_provider_wraps_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host", request=request)

    provider = AzureTTSProvider(
        api_key="k", region="eastus", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(TTSError):
        await provider.synthesise(
            "hello",
            voice="en-KE-AsiliaNeural",
            model="",
            audio_format="mp3",
            language="en",
        )


@pytest.mark.asyncio
async def test_azure_provider_raises_on_error_status() -> None:
    provider = AzureTTSProvider(
        api_key="bad",
        region="eastus",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(401, text="access denied")
        ),
    )
    with pytest.raises(TTSError) as exc:
        await provider.synthesise(
            "hello",
            voice="en-KE-AsiliaNeural",
            model="",
            audio_format="mp3",
            language="en",
        )
    assert "401" in str(exc.value)


@pytest.mark.asyncio
async def test_azure_provider_needs_a_region_or_endpoint() -> None:
    provider = AzureTTSProvider(api_key="k")
    with pytest.raises(TTSError, match="TTS_AZURE_REGION"):
        await provider.synthesise(
            "hello",
            voice="en-KE-AsiliaNeural",
            model="",
            audio_format="mp3",
            language="en",
        )


def test_neural_voice_helpers() -> None:
    assert _voice_locale("en-KE-AsiliaNeural") == "en-KE"
    assert _voice_locale("sw-KE-ZuriNeural") == "sw-KE"
    assert _voice_locale("alloy") is None
    assert _voice_locale("") is None
    assert _neural_voice("", DEFAULT_NEURAL_VOICE) == DEFAULT_NEURAL_VOICE
    assert _neural_voice("alloy", DEFAULT_NEURAL_VOICE) == DEFAULT_NEURAL_VOICE
    assert _neural_voice("sw-KE-ZuriNeural", DEFAULT_NEURAL_VOICE) == "sw-KE-ZuriNeural"


def test_provider_selection_includes_azure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "tts_api_key", "k")
    monkeypatch.setattr(settings, "tts_provider", "azure")
    monkeypatch.setattr(settings, "tts_azure_region", "eastus")
    provider = provider_from_settings()
    assert isinstance(provider, AzureTTSProvider)
    assert provider.region == "eastus"


class _FakeCommunicate:
    """Records the (text, voice) it was asked for and yields decoded chunks."""

    last: "_FakeCommunicate | None" = None

    def __init__(self, text: str, voice: str) -> None:
        self.text = text
        self.voice = voice
        self.chunks = [
            {"type": "audio", "data": b"EDGE-part-1"},
            {"type": "WordBoundary", "offset": 7},
            {"type": "audio", "data": b"-part-2"},
        ]
        _FakeCommunicate.last = self

    async def stream(self):
        for chunk in self.chunks:
            yield chunk


def _fake_edge_module():
    return types.SimpleNamespace(Communicate=_FakeCommunicate)


@pytest.mark.asyncio
async def test_edge_provider_streams_the_kenyan_voice_without_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "edge_tts", _fake_edge_module())

    provider = EdgeTTSProvider()
    audio = await provider.synthesise(
        "Ticket O P D zero zero one",
        voice="en-KE-AsiliaNeural",
        model="",
        audio_format="mp3",
        language="en",
    )

    assert audio.data == b"EDGE-part-1-part-2"
    assert audio.content_type == "audio/mpeg"
    assert audio.provider == "edge"
    assert audio.voice == "en-KE-AsiliaNeural"
    assert _FakeCommunicate.last is not None
    assert _FakeCommunicate.last.voice == "en-KE-AsiliaNeural"
    assert _FakeCommunicate.last.text == "Ticket O P D zero zero one"


@pytest.mark.asyncio
async def test_edge_provider_ignores_the_openai_default_voice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "edge_tts", _fake_edge_module())

    provider = EdgeTTSProvider()
    audio = await provider.synthesise(
        "hello", voice="alloy", model="", audio_format="mp3", language="en"
    )

    assert audio.voice == DEFAULT_NEURAL_VOICE
    assert _FakeCommunicate.last is not None
    assert _FakeCommunicate.last.voice == DEFAULT_NEURAL_VOICE


@pytest.mark.asyncio
async def test_edge_provider_reports_a_missing_package(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "edge_tts", None)
    provider = EdgeTTSProvider()
    with pytest.raises(TTSError, match="edge-tts"):
        await provider.synthesise(
            "hello",
            voice="en-KE-AsiliaNeural",
            model="",
            audio_format="mp3",
            language="en",
        )


@pytest.mark.asyncio
async def test_edge_provider_wraps_provider_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(text: str, voice: str):
        raise RuntimeError("socket closed")

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=boom))
    provider = EdgeTTSProvider()
    with pytest.raises(TTSError, match="socket closed"):
        await provider.synthesise(
            "hello",
            voice="en-KE-AsiliaNeural",
            model="",
            audio_format="mp3",
            language="en",
        )


@pytest.mark.asyncio
async def test_edge_provider_rejects_empty_audio(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Silent:
        def __init__(self, text: str, voice: str) -> None:
            pass

        async def stream(self):
            yield {"type": "WordBoundary", "offset": 1}

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=_Silent))
    provider = EdgeTTSProvider()
    with pytest.raises(TTSError, match="produced no audio"):
        await provider.synthesise(
            "hello",
            voice="en-KE-AsiliaNeural",
            model="",
            audio_format="mp3",
            language="en",
        )


def test_provider_selection_includes_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "tts_provider", "edge")
    monkeypatch.setattr(settings, "tts_api_key", "")
    assert isinstance(provider_from_settings(), EdgeTTSProvider)


def test_cache_key_changes_with_voice_model_and_format() -> None:
    base = cache_key("Ticket O P D one", "alloy", "gpt-4o-mini-tts", "mp3")
    assert base == cache_key("Ticket O P D one", "alloy", "gpt-4o-mini-tts", "mp3")
    assert base != cache_key("Ticket O P D one", "nova", "gpt-4o-mini-tts", "mp3")
    assert base != cache_key("Ticket O P D one", "alloy", "other-model", "mp3")
    assert base != cache_key("Ticket O P D one", "alloy", "gpt-4o-mini-tts", "wav")


def test_speech_normalisation_spells_codes_and_says_small_numbers() -> None:
    assert normalise_for_speech("Ticket OPD-001, proceed to Room 2.") == (
        "Ticket O P D zero zero one proceed to Room two"
    )


class _CountingProvider:
    """A stand-in provider that records what it was asked to say."""

    name = "counting"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[str] = []
        self.fail = fail

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        self.calls.append(text)
        if self.fail:
            raise TTSError("provider is down")
        return SpeechAudio(
            data=b"RENDERED-AUDIO",
            content_type="audio/mpeg",
            provider=self.name,
            voice=voice,
        )


async def _issue_ticket(client) -> uuid.UUID:
    patient = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Voice",
            "last_name": "Tester",
            "date_of_birth": "1990-01-01",
            "gender": "female",
            "phone_number": "0700111222",
        },
    )
    assert patient.status_code == 201, patient.text
    ticket = await client.post(
        "/api/v1/queue/tickets", json={"patient_id": patient.json()["id"]}
    )
    assert ticket.status_code == 201, ticket.text
    return uuid.UUID(ticket.json()["id"])


@pytest.mark.asyncio
async def test_announcement_synthesises_once_and_reuses_the_clip(
    client, db_session
) -> None:
    clear_clip_cache()
    ticket_id = await _issue_ticket(client)
    ticket = await QueueService(db_session).get_ticket(
        facility_id=FACILITY_ID, ticket_id=ticket_id
    )
    assert ticket is not None

    provider = _CountingProvider()
    service = AnnouncementService(db_session, provider=provider)

    first_row, first_audio, first_error = await service.speak(
        ticket=ticket, destination="Room 2"
    )
    second_row, second_audio, second_error = await service.speak(
        ticket=ticket, destination="Room 2"
    )

    assert provider.calls == [first_row.normalized_text]
    assert first_error is None and second_error is None
    assert first_audio == second_audio == b"RENDERED-AUDIO"
    assert first_row.status == second_row.status == "ready"
    assert second_row.storage_key == "cache:" + second_row.cache_key
    clear_clip_cache()


@pytest.mark.asyncio
async def test_announcement_records_disabled_without_a_provider(
    client, db_session, monkeypatch
) -> None:
    clear_clip_cache()
    monkeypatch.setattr(settings, "voice_enabled", False)
    ticket_id = await _issue_ticket(client)
    ticket = await QueueService(db_session).get_ticket(
        facility_id=FACILITY_ID, ticket_id=ticket_id
    )

    row, audio, error = await AnnouncementService(db_session).speak(
        ticket=ticket, destination=None
    )
    assert row.status == "disabled"
    assert audio is None and error is None


@pytest.mark.asyncio
async def test_announcement_failure_is_recorded_not_raised(client, db_session) -> None:
    clear_clip_cache()
    ticket_id = await _issue_ticket(client)
    ticket = await QueueService(db_session).get_ticket(
        facility_id=FACILITY_ID, ticket_id=ticket_id
    )

    service = AnnouncementService(db_session, provider=_CountingProvider(fail=True))
    row, audio, error = await service.speak(ticket=ticket, destination="Room 1")
    assert row.status == "failed"
    assert row.error and "down" in row.error
    assert audio is None and error is not None





class _ExplodingProvider:
    """A provider whose own dependencies blow up - an unreadable import, say.

    This is the shape of a half-installed voice extra: the provider is
    configured and reachable, but importing it raises something that is not a
    ``TTSError`` at all.
    """

    name = "exploding"

    def __init__(self) -> None:
        self.calls = 0

    async def synthesise(
        self, text: str, *, voice: str, model: str, audio_format: str, language: str
    ) -> SpeechAudio:
        self.calls += 1
        raise PermissionError(
            "[Errno 13] Permission denied: 'multidict/_multidict_py.py'"
        )


@pytest.mark.asyncio
async def test_announcement_survives_a_broken_provider_import(client, db_session) -> None:
    """A broken speaker must never take the queue down with it."""

    clear_clip_cache()
    ticket_id = await _issue_ticket(client)
    ticket = await QueueService(db_session).get_ticket(
        facility_id=FACILITY_ID, ticket_id=ticket_id
    )
    assert ticket is not None

    service = AnnouncementService(db_session, provider=_ExplodingProvider())
    row, audio, error = await service.speak(ticket=ticket, destination="Room 2")

    assert row.status == "failed"
    assert row.error and "Permission denied" in row.error
    assert audio is None and error is not None
    clear_clip_cache()


@pytest.mark.asyncio
async def test_script_only_ask_never_touches_the_speaker(client, db_session) -> None:
    """'What would the speaker say?' must work with no speech engine at all."""

    clear_clip_cache()
    ticket_id = await _issue_ticket(client)
    ticket = await QueueService(db_session).get_ticket(
        facility_id=FACILITY_ID, ticket_id=ticket_id
    )
    assert ticket is not None

    provider = _ExplodingProvider()
    service = AnnouncementService(db_session, provider=provider)
    row, audio, error = await service.speak(
        ticket=ticket, destination="Room 2", with_audio=False
    )

    assert provider.calls == 0
    assert audio is None and error is None
    assert "Room 2" in row.text
    assert row.status == "pending"
