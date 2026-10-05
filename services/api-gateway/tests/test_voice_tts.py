"""Voice/TTS provider integration and announcement caching.

The vendor adapters are exercised through ``httpx.MockTransport`` so the tests
prove the exact request each provider sends (URL, auth header, payload) and how
each failure becomes a ``TTSError`` - no network, no API key, no flakiness.

The caching tests drive ``AnnouncementService`` with a counting provider: the
same call twice must synthesise once, and a provider failure must be recorded
on the row instead of raised, because the queue must never block on a speaker.
"""

from __future__ import annotations

import json
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
    ElevenLabsTTSProvider,
    OpenAITTSProvider,
    SpeechAudio,
    TTSError,
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
    monkeypatch.setattr(settings, "tts_api_key", "")
    assert provider_from_settings() is None


def test_provider_selection_follows_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "voice_enabled", True)
    monkeypatch.setattr(settings, "tts_api_key", "k")
    monkeypatch.setattr(settings, "tts_provider", "elevenlabs")
    assert isinstance(provider_from_settings(), ElevenLabsTTSProvider)

    monkeypatch.setattr(settings, "tts_provider", "openai")
    assert isinstance(provider_from_settings(), OpenAITTSProvider)


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
    client, db_session
) -> None:
    clear_clip_cache()
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


