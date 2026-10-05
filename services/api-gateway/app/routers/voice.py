"""Server-proxied text-to-speech for patient calling.

The browser never sees the TTS API key. It asks this router for audio, this
router asks the provider, and the bytes are streamed back with the right
content type. If voice is switched off - or the provider is having a bad day -
the caller gets a clear error and the frontend falls back to the device's own
speech synthesis using the text the queue already published. The queue itself
never blocks on any of this.
"""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.auth.permissions import Permission, require_permission
from app.config import settings
from app.database import get_db
from app.middleware.facility_context import set_facility_context
from app.schemas.queue import QueueAnnouncementResponse
from app.services.queue.queue_service import QueueService
from app.services.voice.announcement_service import AnnouncementService
from app.services.voice.tts_provider import TTSError

router = APIRouter()


async def _ticket_for_announcement(
    *, db: AsyncSession, facility_id: uuid.UUID, ticket_id: uuid.UUID
):
    """Load a ticket and the human-readable room it is being called into."""

    service = QueueService(db)
    ticket = await service.get_ticket(facility_id=facility_id, ticket_id=ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Queue ticket not found"
        )
    context = await service.display_context(facility_id=facility_id, tickets=[ticket])
    return ticket, context.get(str(ticket.id), {})


async def _render(
    *,
    db: AsyncSession,
    facility_id: uuid.UUID,
    ticket_id: uuid.UUID,
    recalled: bool,
    with_audio: bool,
    audio_prefix: str,
):
    """Build the announcement for a ticket, optionally rendering the audio."""

    ticket, context = await _ticket_for_announcement(
        db=db, facility_id=facility_id, ticket_id=ticket_id
    )
    announcement = AnnouncementService(db)
    row, audio, error = await announcement.speak(
        ticket=ticket,
        destination=announcement.destination_for(ticket, context.get("service_point_label")),
        recalled=recalled,
    )
    payload = QueueAnnouncementResponse(
        ticket_id=ticket.id,
        ticket_number=ticket.ticket_number,
        text=row.text,
        normalized_text=row.normalized_text,
        language=row.language,
        voice_enabled=announcement.enabled,
        audio_url=f"{audio_prefix}/announcements/{ticket.id}/audio" if announcement.enabled else None,
        content_type=row.content_type,
        cached=row.storage_key is not None and row.storage_key.startswith("cache:"),
    )
    if with_audio:
        if not announcement.enabled:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Voice announcements are switched off on this deployment",
            )
        if audio is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=error or "The text-to-speech provider could not be reached",
            )
        return Response(
            content=audio,
            media_type=row.content_type or "audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )
    return payload


@router.get("/announcements/{ticket_id}", response_model=QueueAnnouncementResponse)
async def get_announcement(
    ticket_id: uuid.UUID,
    recalled: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
) -> QueueAnnouncementResponse:
    """What the speaker should say for this ticket."""

    return await _render(
        db=db,
        facility_id=current_user.facility_id,
        ticket_id=ticket_id,
        recalled=recalled,
        with_audio=False,
        audio_prefix="/api/v1/voice",
    )


@router.get("/announcements/{ticket_id}/audio")
async def get_announcement_audio(
    ticket_id: uuid.UUID,
    recalled: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
):
    """The rendered audio for a ticket, streamed from the server."""

    return await _render(
        db=db,
        facility_id=current_user.facility_id,
        ticket_id=ticket_id,
        recalled=recalled,
        with_audio=True,
        audio_prefix="/api/v1/voice",
    )


def _public_facility(token: str | None) -> uuid.UUID:
    """Validate the speaker token and return the facility it unlocks."""

    configured = (settings.queue_display_token or "").strip()
    facility = (settings.queue_display_facility_id or "").strip()
    if not configured or not facility:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The public queue board is not configured on this deployment",
        )
    if not token or not secrets.compare_digest(token, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid display token"
        )
    return uuid.UUID(facility)


@router.get("/public/announcements/{ticket_id}", response_model=QueueAnnouncementResponse)
async def get_public_announcement(
    ticket_id: uuid.UUID,
    token: str = Query(...),
    recalled: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> QueueAnnouncementResponse:
    """What the corridor speaker should say, for an unauthenticated device."""

    facility_id = _public_facility(token)
    await set_facility_context(db, str(facility_id))
    return await _render(
        db=db,
        facility_id=facility_id,
        ticket_id=ticket_id,
        recalled=recalled,
        with_audio=False,
        audio_prefix="/api/v1/voice/public",
    )


@router.get("/public/announcements/{ticket_id}/audio")
async def get_public_announcement_audio(
    ticket_id: uuid.UUID,
    token: str = Query(...),
    recalled: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Audio for the corridor speaker. The token is the only credential."""

    facility_id = _public_facility(token)
    await set_facility_context(db, str(facility_id))
    return await _render(
        db=db,
        facility_id=facility_id,
        ticket_id=ticket_id,
        recalled=recalled,
        with_audio=True,
        audio_prefix="/api/v1/voice/public",
    )


@router.get(
    "/public/announcements/by-number/{ticket_number}",
    response_model=QueueAnnouncementResponse,
)
async def get_public_announcement_by_number(
    ticket_number: str,
    token: str = Query(...),
    recalled: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> QueueAnnouncementResponse:
    """What the corridor speaker should say, addressed by printed number.

    A wall board hears a ticket number and never a ticket id, so this route
    resolves the number inside the unlocked facility before building the line.

    @param ticket_number: The number read out, e.g. OPD-023
    @param token: The display token that unlocks this facility
    @param recalled: True for a repeat call
    @param db: Async database session
    @returns The announcement the speaker should make
    """
    facility_id = _public_facility(token)
    await set_facility_context(db, str(facility_id))
    ticket = await QueueService(db).get_ticket_by_number(
        facility_id=facility_id, ticket_number=ticket_number
    )
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Queue ticket not found"
        )
    return await _render(
        db=db,
        facility_id=facility_id,
        ticket_id=ticket.id,
        recalled=recalled,
        with_audio=False,
        audio_prefix="/api/v1/voice/public",
    )


@router.get("/public/announcements/by-number/{ticket_number}/audio")
async def get_public_announcement_audio_by_number(
    ticket_number: str,
    token: str = Query(...),
    recalled: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """The rendered voice line for a printed number, streamed from the server.

    Keeps the TTS API key on the server: the kiosk asks for audio and receives
    bytes, and falls back to the browser voice only when this fails.

    @param ticket_number: The number read out, e.g. OPD-023
    @param token: The display token that unlocks this facility
    @param recalled: True for a repeat call
    @param db: Async database session
    @returns Audio bytes with the provider's content type
    """
    facility_id = _public_facility(token)
    await set_facility_context(db, str(facility_id))
    ticket = await QueueService(db).get_ticket_by_number(
        facility_id=facility_id, ticket_number=ticket_number
    )
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Queue ticket not found"
        )
    return await _render(
        db=db,
        facility_id=facility_id,
        ticket_id=ticket.id,
        recalled=recalled,
        with_audio=True,
        audio_prefix="/api/v1/voice/public",
    )
