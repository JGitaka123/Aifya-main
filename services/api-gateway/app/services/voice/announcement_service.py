"""Turn a called ticket into something the speaker can play.

The script is built deterministically (see app.services.voice.text), hashed,
and only then sent to the vendor. The hash is the cache key, so two patients
whose call differs only by ticket number are never confused, and a repeated
call of the same ticket costs nothing the second time.

Voice failure never blocks the queue. If the provider is unreachable the
announcement row is marked failed and the caller gets a clear error to surface
on the speaker, while the ticket stays exactly where the state machine put it.
"""

from __future__ import annotations

import uuid
from collections import OrderedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.queue import QueueAnnouncement, QueueTicket
from app.services.voice.text import (
    build_call_text,
    cache_key,
    normalise_for_speech,
)
from app.services.voice.tts_provider import (
    CONTENT_TYPES,
    TTSError,
    TTSProvider,
    provider_from_settings,
)

#: How many rendered clips to keep in memory per worker. Small on purpose:
#: this is a hot cache for the current board, not an archive. The durable
#: copy belongs in object storage, which is the storage_key column.
_MAX_CACHED_CLIPS = 48
_CLIP_CACHE: "OrderedDict[str, tuple[bytes, str]]" = OrderedDict()


def _remember(key: str, data: bytes, content_type: str) -> None:
    _CLIP_CACHE[key] = (data, content_type)
    _CLIP_CACHE.move_to_end(key)
    while len(_CLIP_CACHE) > _MAX_CACHED_CLIPS:
        _CLIP_CACHE.popitem(last=False)


def _recall(key: str) -> tuple[bytes, str] | None:
    found = _CLIP_CACHE.get(key)
    if found is not None:
        _CLIP_CACHE.move_to_end(key)
    return found


def clear_clip_cache() -> None:
    """Drop the in-memory clip cache so tests can start from a clean slate."""

    _CLIP_CACHE.clear()


class AnnouncementService:
    """Builds, caches and (when configured) speaks a queue announcement."""

    def __init__(self, db: AsyncSession, provider: TTSProvider | None = None) -> None:
        self.db = db
        self._provider = provider
        self._resolved = provider is not None

    @property
    def provider(self) -> TTSProvider | None:
        """The configured provider, resolved once per service instance."""

        if not self._resolved:
            self._provider = provider_from_settings()
            self._resolved = True
        return self._provider

    @property
    def enabled(self) -> bool:
        """Whether this deployment can actually speak."""

        return self.provider is not None

    @property
    def language(self) -> str:
        """The configured announcement language."""

        return settings.tts_language or "en"

    def destination_for(
        self, ticket: QueueTicket, service_point_label: str | None = None
    ) -> str | None:
        """Where the speaker tells the patient to go.

        A room label wins; without one the ticket number alone still makes a
        usable announcement.
        """

        if service_point_label:
            return service_point_label
        return None

    def script_for(
        self, ticket: QueueTicket, destination: str | None, recalled: bool = False
    ) -> tuple[str, str]:
        """Return (spoken text, normalised text) for a ticket."""

        text = build_call_text(ticket.ticket_number, destination, recalled=recalled)
        return text, normalise_for_speech(text, self.language)

    async def speak(
        self,
        *,
        ticket: QueueTicket,
        destination: str | None,
        recalled: bool = False,
        queue_event_id: uuid.UUID | None = None,
    ) -> tuple[QueueAnnouncement, bytes | None, str | None]:
        """Prepare and, when possible, render the announcement.

        @returns The audit row, the audio bytes (or None), and an error string
        """

        text, normalised = self.script_for(ticket, destination, recalled=recalled)
        key = cache_key(
            normalised,
            settings.tts_voice,
            settings.tts_model,
            settings.tts_audio_format,
        )
        content_type = CONTENT_TYPES.get(settings.tts_audio_format, "audio/mpeg")

        row = QueueAnnouncement(
            facility_id=ticket.facility_id,
            ticket_id=ticket.id,
            queue_event_id=queue_event_id,
            text=text,
            normalized_text=normalised,
            language=self.language,
            provider=self.provider.name if self.provider else None,
            voice=settings.tts_voice,
            cache_key=key,
            content_type=content_type,
            status="pending",
        )
        self.db.add(row)
        await self.db.flush()

        if self.provider is None:
            row.status = "disabled"
            await self.db.flush()
            return row, None, None

        cached = _recall(key)
        if cached is not None:
            row.status = "ready"
            row.storage_key = "cache:" + key
            await self.db.flush()
            return row, cached[0], None

        try:
            audio = await self.provider.synthesise(
                normalised,
                voice=settings.tts_voice,
                model=settings.tts_model,
                audio_format=settings.tts_audio_format,
                language=self.language,
            )
        except TTSError as exc:
            row.status = "failed"
            row.error = str(exc)[:1000]
            await self.db.flush()
            return row, None, str(exc)

        _remember(key, audio.data, audio.content_type)
        row.status = "ready"
        row.content_type = audio.content_type
        row.storage_key = "cache:" + key
        await self.db.flush()
        return row, audio.data, None
