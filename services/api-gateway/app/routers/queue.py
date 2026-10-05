"""Queue management and patient calling API.

Everything here is facility-scoped: the caller's facility comes from the JWT
and every query filters on it, so a made-up ticket id from another hospital
reads as 404 rather than as someone else's patient.

The board and the speaker are read-only projections. Live updates are pushed
over SSE, and the client is expected to fetch a snapshot first and then apply
deltas - which is why the stream itself needs no database session and a
dropped connection is never a data problem.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser, get_current_user, require_roles
from app.auth.permissions import Permission, require_permission
from app.config import settings
from app.database import get_db
from app.models.queue import QueueTicket
from app.schemas.queue import (
    QueueBoardResponse,
    QueueCallNextRequest,
    QueueCallRequest,
    QueueCancelRequest,
    QueueEventResponse,
    QueuePriorityRequest,
    QueueServicePointCreate,
    QueueServicePointResponse,
    QueueStartRequest,
    QueueStatsResponse,
    QueueTicketCreate,
    QueueTicketResponse,
    QueueTransferRequest,
)
from app.services.queue.broadcaster import broadcaster
from app.services.queue.queue_service import QueueService
from app.services.queue.state_machine import IllegalTransition
from app.services.voice.announcement_service import AnnouncementService

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _sse(payload: dict) -> str:
    """Encode one server-sent event."""

    return "data: " + json.dumps(payload, default=str) + "\n\n"


def _ticket_payload(ticket: QueueTicket, context: dict, public: bool = False) -> dict:
    """The JSON for one ticket, optionally stripped to what a public wall may show."""

    row = {
        "id": str(ticket.id),
        "ticket_number": ticket.ticket_number,
        "status": ticket.status,
        "priority": ticket.priority,
        "service_point_id": str(ticket.service_point_id) if ticket.service_point_id else None,
        "service_point_label": context.get("service_point_label"),
        "called_at": ticket.called_at,
        "issued_at": ticket.issued_at,
        "waiting_minutes": context.get("waiting_minutes"),
    }
    if public:
        # Privacy rule: a public wall shows a ticket number and a destination
        # and nothing else - no internal id, no station id, no timing, and no
        # clinical field, so a corridor screen can never become a record leak.
        return {
            "ticket_number": row["ticket_number"],
            "service_point_label": row["service_point_label"],
        }
    row.update(
        {
            "facility_id": str(ticket.facility_id),
            "patient_id": str(ticket.patient_id),
            "patient_name": context.get("patient_name"),
            "patient_mrn": context.get("patient_mrn"),
            "department_id": str(ticket.department_id) if ticket.department_id else None,
            "department_name": context.get("department_name"),
            "triage_category": ticket.triage_category,
            "recall_count": ticket.recall_count,
            "waiting_position": context.get("waiting_position"),
        }
    )
    return row


#: On a corridor wall the fresh call matters most, so called patients lead.
_PUBLIC_STATUS_RANK = {"CALLED": 0, "IN_SERVICE": 1, "WAITING": 2}


def _public_order(tickets: list[QueueTicket]) -> list[QueueTicket]:
    """Order the wall so the most recent call is the first thing patients see.

    Staff keep the call order (priority, then arrival); the wall is a display,
    not a worklist, so it puts whoever was just called at the front and lets
    the waiting list follow in arrival order.
    """

    def key(ticket: QueueTicket) -> tuple:
        called = ticket.called_at.timestamp() if ticket.called_at else 0.0
        return (_PUBLIC_STATUS_RANK.get(ticket.status, 9), -called)

    return sorted(tickets, key=key)


async def _publish(
    ticket: QueueTicket,
    service: QueueService,
    action: str,
    public: bool = False,
    speech: dict | None = None,
) -> dict:
    """Push one ticket change to every connected board and speaker."""

    context = await service.display_context(facility_id=ticket.facility_id, tickets=[ticket])
    ctx = context.get(str(ticket.id), {})
    payload = {
        "type": "ticket",
        "action": action,
        "facility_id": str(ticket.facility_id),
        "ticket": _ticket_payload(ticket, ctx, public=public),
        "occurred_at": datetime.now(timezone.utc).isoformat(),
    }
    if speech is not None:
        payload["speech"] = speech
    await broadcaster.publish(payload)
    return payload


def _respond(ticket: QueueTicket, context: dict) -> QueueTicketResponse:
    """Build a ticket response with its display fields."""

    base = QueueTicketResponse.model_validate(ticket)
    return base.model_copy(update=context.get(str(ticket.id), {}))


async def _load_ticket(
    *, service: QueueService, facility_id: uuid.UUID, ticket_id: uuid.UUID
) -> QueueTicket:
    """Fetch a ticket or fail with a 404 that does not leak existence."""

    ticket = await service.get_ticket(facility_id=facility_id, ticket_id=ticket_id)
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Queue ticket not found"
        )
    return ticket


@router.get("/service-points", response_model=list[QueueServicePointResponse])
async def list_service_points(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
) -> list[QueueServicePointResponse]:
    """Rooms and counters a patient can be called into."""

    service = QueueService(db)
    points = await service.list_service_points(facility_id=current_user.facility_id)
    return [QueueServicePointResponse.model_validate(point) for point in points]


@router.post(
    "/service-points",
    response_model=QueueServicePointResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_service_point(
    data: QueueServicePointCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles("admin", "facility_admin")),
) -> QueueServicePointResponse:
    """Register a room or counter. Only administrators configure the estate."""

    service = QueueService(db)
    point = await service.create_service_point(
        facility_id=current_user.facility_id, data=data, created_by=current_user.user_id
    )
    return QueueServicePointResponse.model_validate(point)


@router.post(
    "/tickets", response_model=QueueTicketResponse, status_code=status.HTTP_201_CREATED
)
async def issue_ticket(
    data: QueueTicketCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Put a patient in the queue and return their ticket number."""

    service = QueueService(db)
    ticket = await service.issue_ticket(
        facility_id=current_user.facility_id,
        data=data,
        created_by=current_user.user_id,
        idempotency_key=data.idempotency_key,
    )
    context = await service.display_context(
        facility_id=current_user.facility_id, tickets=[ticket]
    )
    await _publish(ticket, service, "TICKET_CREATED")
    return _respond(ticket, context)


@router.get("", response_model=QueueBoardResponse)
async def get_board(
    department_id: uuid.UUID | None = Query(None, description="Only this department's queue"),
    service_point_id: uuid.UUID | None = Query(None, description="Only this room's queue"),
    include_completed: bool = Query(False, description="Include today's completed visits"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
) -> QueueBoardResponse:
    """The live queue in call order: priority first, then longest waiting."""

    service = QueueService(db)
    tickets = await service.list_board(
        facility_id=current_user.facility_id,
        department_id=department_id,
        service_point_id=service_point_id,
        include_completed=include_completed,
    )
    context = await service.display_context(
        facility_id=current_user.facility_id, tickets=tickets
    )
    items = [_respond(ticket, context) for ticket in tickets]
    return QueueBoardResponse(
        items=items,
        total=len(items),
        waiting=sum(1 for t in tickets if t.status == "WAITING"),
        called=sum(1 for t in tickets if t.status == "CALLED"),
        in_service=sum(1 for t in tickets if t.status == "IN_SERVICE"),
    )


@router.get("/stats", response_model=QueueStatsResponse)
async def get_stats(
    department_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
) -> QueueStatsResponse:
    """Operational counters for the staff dashboard."""

    service = QueueService(db)
    stats = await service.stats(
        facility_id=current_user.facility_id, department_id=department_id
    )
    return QueueStatsResponse(**stats)


@router.post("/call-next", response_model=QueueTicketResponse)
async def call_next_patient(
    data: QueueCallNextRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Call the highest priority waiting patient.

    Two nurses pressing at the same moment each receive a different patient:
    the row is claimed with SELECT ... FOR UPDATE SKIP LOCKED.
    """

    service = QueueService(db)
    ticket = await service.call_next(
        facility_id=current_user.facility_id,
        actor_id=current_user.user_id,
        department_id=data.department_id,
        service_point_id=data.service_point_id,
        triage_category=data.triage_category,
    )
    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No patients are waiting in this queue",
        )
    context = await service.display_context(
        facility_id=current_user.facility_id, tickets=[ticket]
    )
    ctx = context.get(str(ticket.id), {})
    speech = None
    if data.announce:
        announcement = AnnouncementService(db)
        text, normalized = announcement.script_for(ticket, ctx.get("service_point_label"))
        speech = {
            "text": text,
            "normalised": normalized,
            "language": announcement.language,
            "recalled": False,
        }
    await _publish(ticket, service, "CALLED", speech=speech)
    return _respond(ticket, context)


async def _act(
    *,
    action: str,
    ticket: QueueTicket,
    db: AsyncSession,
    current_user: CurrentUser,
    announced: bool = False,
    destination: str | None = None,
) -> QueueTicketResponse:
    """Run one transition, publish it, and return the updated ticket."""

    service = QueueService(db)
    context = await service.display_context(
        facility_id=ticket.facility_id, tickets=[ticket]
    )
    speech = None
    if announced:
        announcement = AnnouncementService(db)
        text, normalized = announcement.script_for(
            ticket, destination or context.get(str(ticket.id), {}).get("service_point_label")
        )
        speech = {
            "text": text,
            "normalised": normalized,
            "language": announcement.language,
            "recalled": action == "RECALLED",
        }
    await _publish(ticket, service, action, speech=speech)
    context = await service.display_context(
        facility_id=ticket.facility_id, tickets=[ticket]
    )
    return _respond(ticket, context)


@router.post("/tickets/{ticket_id}/call", response_model=QueueTicketResponse)
async def call_ticket(
    ticket_id: uuid.UUID,
    data: QueueCallRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Call one chosen ticket into a room."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        await service.call_ticket(
            ticket=ticket,
            actor_id=current_user.user_id,
            service_point_id=data.service_point_id,
        )
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _act(
        action="CALLED", ticket=ticket, db=db, current_user=current_user, announced=data.announce
    )


@router.post("/tickets/{ticket_id}/recall", response_model=QueueTicketResponse)
async def recall_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Say the ticket number again."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        await service.call_ticket(
            ticket=ticket, actor_id=current_user.user_id, recalled=True
        )
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _act(
        action="RECALLED", ticket=ticket, db=db, current_user=current_user, announced=True
    )


@router.post("/tickets/{ticket_id}/start", response_model=QueueTicketResponse)
async def start_service(
    ticket_id: uuid.UUID,
    data: QueueStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """The patient walked in: service has started."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        await service.start_service(
            ticket=ticket,
            actor_id=current_user.user_id,
            service_point_id=data.service_point_id,
        )
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _act(action="SERVICE_STARTED", ticket=ticket, db=db, current_user=current_user)


@router.post("/tickets/{ticket_id}/complete", response_model=QueueTicketResponse)
async def complete_service(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Close the visit."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        await service.complete(ticket=ticket, actor_id=current_user.user_id)
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _act(action="SERVICE_COMPLETED", ticket=ticket, db=db, current_user=current_user)


@router.post("/tickets/{ticket_id}/no-show", response_model=QueueTicketResponse)
async def mark_no_show(
    ticket_id: uuid.UUID,
    data: QueueCancelRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """The patient did not come when called."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        await service.mark_no_show(
            ticket=ticket,
            actor_id=current_user.user_id,
            reason=data.reason if data else None,
        )
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _act(action="NO_SHOW", ticket=ticket, db=db, current_user=current_user)


@router.post("/tickets/{ticket_id}/cancel", response_model=QueueTicketResponse)
async def cancel_ticket(
    ticket_id: uuid.UUID,
    data: QueueCancelRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Drop a ticket that will not be served."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        await service.cancel(
            ticket=ticket,
            actor_id=current_user.user_id,
            reason=data.reason if data else None,
        )
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _act(action="CANCELLED", ticket=ticket, db=db, current_user=current_user)


@router.post("/tickets/{ticket_id}/priority", response_model=QueueTicketResponse)
async def change_priority(
    ticket_id: uuid.UUID,
    data: QueuePriorityRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Re-rank a waiting ticket after triage changed."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        await service.change_priority(
            ticket=ticket,
            actor_id=current_user.user_id,
            priority=data.priority,
            triage_category=data.triage_category,
        )
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return await _act(action="PRIORITY_CHANGED", ticket=ticket, db=db, current_user=current_user)


@router.post("/tickets/{ticket_id}/transfer", response_model=QueueTicketResponse)
async def transfer_ticket(
    ticket_id: uuid.UUID,
    data: QueueTransferRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_CONSULT)),
) -> QueueTicketResponse:
    """Send the patient to another department and issue them a new ticket."""

    service = QueueService(db)
    ticket = await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    try:
        _, new_ticket = await service.transfer(
            ticket=ticket,
            actor_id=current_user.user_id,
            department_id=data.department_id,
            service_point_id=data.service_point_id,
            reason=data.reason,
        )
    except IllegalTransition as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await _publish(ticket, service, "TRANSFERRED")
    return await _act(action="TICKET_CREATED", ticket=new_ticket, db=db, current_user=current_user)


@router.get("/tickets/{ticket_id}/events", response_model=list[QueueEventResponse])
async def ticket_events(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
) -> list[QueueEventResponse]:
    """The ticket's immutable history, oldest first."""

    service = QueueService(db)
    await _load_ticket(
        service=service, facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    events = await service.events_for(
        facility_id=current_user.facility_id, ticket_id=ticket_id
    )
    return [QueueEventResponse.model_validate(event) for event in events]


async def _event_stream(request: Request, facility_id: uuid.UUID, public: bool) -> StreamingResponse:
    """Stream queue deltas to one subscriber."""

    inbox = broadcaster.subscribe()

    async def generate():
        try:
            yield _sse(
                {
                    "type": "hello",
                    "facility_id": str(facility_id),
                    "public": public,
                    "server_time": datetime.now(timezone.utc).isoformat(),
                }
            )
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(inbox.get(), timeout=20)
                except asyncio.TimeoutError:
                    # Keep proxies and load balancers from closing an idle stream.
                    yield ": ping\n\n"
                    continue
                if str(event.get("facility_id")) != str(facility_id):
                    continue
                if public:
                    # Strip the staff payload down to what a corridor screen
                    # may hold: a number and a room, never a patient. The HTTP
                    # board does the same; the stream must not be the hole.
                    raw_ticket = event.get("ticket") or {}
                    event = {
                        "type": event.get("type"),
                        "action": event.get("action"),
                        "occurred_at": event.get("occurred_at"),
                        "facility_id": str(facility_id),
                        "ticket": {
                            "ticket_number": raw_ticket.get("ticket_number"),
                            "service_point_label": raw_ticket.get("service_point_label"),
                        },
                        "speech": event.get("speech"),
                    }
                yield _sse(event)
        finally:
            broadcaster.unsubscribe(inbox)

    return StreamingResponse(generate(), media_type="text/event-stream", headers=_SSE_HEADERS)


@router.get("/stream")
async def stream_queue(
    request: Request,
    current_user: CurrentUser = Depends(require_permission(Permission.CLINICAL_VIEW)),
) -> StreamingResponse:
    """Staff board: every ticket change for this facility."""

    return await _event_stream(request, current_user.facility_id, public=False)


def _display_facility(token: str | None) -> uuid.UUID:
    """Validate the wall/speaker token and return the facility it unlocks."""

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


@router.get("/public/board")
async def public_board(
    token: str = Query(..., description="The display token for this deployment"),
    include_completed: bool = Query(False),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The anonymised wall board: ticket number and room only."""

    facility_id = _display_facility(token)
    service = QueueService(db)
    tickets = await service.list_board(
        facility_id=facility_id, include_completed=include_completed
    )
    context = await service.display_context(facility_id=facility_id, tickets=tickets)
    # A public row is stripped to a number and a room, so the counters are
    # taken from the tickets themselves - the payload no longer carries a
    # status to count.
    items = [
        _ticket_payload(ticket, context.get(str(ticket.id), {}), public=True)
        for ticket in _public_order(tickets)
    ]
    return {
        "items": items,
        "total": len(items),
        "waiting": sum(1 for t in tickets if t.status == "WAITING"),
        "called": sum(1 for t in tickets if t.status == "CALLED"),
        "in_service": sum(1 for t in tickets if t.status == "IN_SERVICE"),
    }


@router.get("/public/stream")
async def public_stream(
    request: Request,
    token: str = Query(..., description="The display token for this deployment"),
) -> StreamingResponse:
    """Wall board and speaker stream, stripped of all patient detail."""

    facility_id = _display_facility(token)
    return await _event_stream(request, facility_id, public=True)
