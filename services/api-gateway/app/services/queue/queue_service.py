"""The queue engine: issue, call, serve, complete - safely.

Every state change goes through apply_event(), which asks the state machine
whether the move is legal and then writes an immutable queue_events row in the
same transaction. If the event or the audit row cannot be written, neither is.

CALL NEXT is the interesting one. Two nurses pressing the button at the same
moment must never be handed the same patient, so the candidate row is claimed
with SELECT ... FOR UPDATE SKIP LOCKED: the second caller skips the locked row
and takes the next patient instead of blocking or double-booking. The row lock
is held until the request's transaction commits, which is what makes the claim
atomic. On SQLite (tests) the clause is a no-op, which is why the tests also
assert the behaviour rather than relying on the database.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.patient import Patient
from app.models.queue import QueueEvent, QueueServicePoint, QueueTicket
from app.models.staff import Department
from app.services.queue.state_machine import (
    QueueEventType,
    QueueTicketStatus,
    assert_transition,
)
from app.services.voice.text import build_call_text

#: How many times to retry a ticket number that lost a collision race.
_NUMBER_RETRIES = 6


def _is_ticket_number_collision(exc: IntegrityError) -> bool:
    """Is this IntegrityError the ticket-number unique violation?

    Only a number collision is worth retrying. Any other integrity error - a
    patient, encounter or department that does not exist - is a real failure
    and must surface as itself rather than as a number-allocation problem.

    @param exc: The IntegrityError raised by the flush.
    @returns True when the violated constraint is the ticket number.
    """
    original = getattr(exc, "orig", exc)
    constraint = getattr(original, "constraint_name", None)
    if constraint == "uq_queue_tickets_facility_number":
        return True
    message = str(original).lower()
    return "uq_queue_tickets_facility_number" in message or (
        "duplicate key" in message and "ticket_number" in message
    )


class QueueService:
    """Reads and writes the queue for one facility-scoped session."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -- Service points -------------------------------------------------

    async def create_service_point(
        self, *, facility_id: uuid.UUID, data: Any, created_by: uuid.UUID | None
    ) -> QueueServicePoint:
        """Register a room or counter that patients can be called into."""

        point = QueueServicePoint(
            facility_id=facility_id,
            department_id=data.department_id,
            name=data.name,
            kind=data.kind,
            display_label=data.display_label,
            created_by=created_by,
            updated_by=created_by,
        )
        self.db.add(point)
        await self.db.flush()
        await self.db.refresh(point)
        return point

    async def list_service_points(
        self, *, facility_id: uuid.UUID, active_only: bool = True
    ) -> list[QueueServicePoint]:
        """List the facility's rooms and counters."""

        stmt = select(QueueServicePoint).where(
            QueueServicePoint.facility_id == facility_id,
            QueueServicePoint.is_deleted.is_(False),
        )
        if active_only:
            stmt = stmt.where(QueueServicePoint.is_active.is_(True))
        stmt = stmt.order_by(QueueServicePoint.name.asc())
        return list((await self.db.execute(stmt)).scalars().all())

    # -- Tickets --------------------------------------------------------

    async def _next_ticket_number(
        self, *, facility_id: uuid.UUID, prefix: str
    ) -> str:
        """Build the next ticket number for a prefix within this facility.

        The number is a per-day, per-prefix sequence. It is not the source of
        truth for uniqueness - the unique constraint is - but it keeps the
        numbers small and predictable so the speaker reads them cleanly.
        """

        today = datetime.now(timezone.utc).date()
        stmt = (
            select(func.count())
            .select_from(QueueTicket)
            .where(
                QueueTicket.facility_id == facility_id,
                QueueTicket.ticket_number.like(prefix + "-%"),
                QueueTicket.issued_on == today,
            )
        )
        used = (await self.db.execute(stmt)).scalar_one()
        return f"{prefix}-{used + 1:03d}"

    async def _prefix_for(
        self, *, facility_id: uuid.UUID, department_id: uuid.UUID | None, requested: str | None
    ) -> str:
        """Derive the human prefix (OPD, LAB, ...) for a ticket number."""

        if requested:
            return requested.strip().upper()[:6] or "Q"
        if department_id is not None:
            code = (
                await self.db.execute(
                    select(Department.code).where(
                        Department.id == department_id,
                        Department.facility_id == facility_id,
                    )
                )
            ).scalar_one_or_none()
            if code:
                cleaned = "".join(ch for ch in code.upper() if ch.isalnum())[:5]
                if cleaned:
                    return cleaned
        return "Q"

    async def issue_ticket(
        self,
        *,
        facility_id: uuid.UUID,
        data: Any,
        created_by: uuid.UUID | None,
        prefix: str | None = None,
        idempotency_key: str | None = None,
    ) -> QueueTicket:
        """Create a WAITING ticket, recording TICKET_CREATED.

        A duplicate ticket for an encounter that is already waiting is reused
        rather than duplicated, so a double-click at registration does not put
        the same patient in the queue twice.
        """

        if data.encounter_id is not None:
            existing = (
                await self.db.execute(
                    select(QueueTicket).where(
                        QueueTicket.facility_id == facility_id,
                        QueueTicket.encounter_id == data.encounter_id,
                        QueueTicket.status == QueueTicketStatus.WAITING,
                        QueueTicket.is_deleted.is_(False),
                    )
                )
            ).scalars().first()
            if existing is not None:
                return existing

        if idempotency_key is None:
            idempotency_key = getattr(data, "idempotency_key", None)
        if idempotency_key is not None:
            replayed = (
                await self.db.execute(
                    select(QueueTicket).where(
                        QueueTicket.facility_id == facility_id,
                        QueueTicket.idempotency_key == idempotency_key,
                        QueueTicket.is_deleted.is_(False),
                    )
                )
            ).scalars().first()
            if replayed is not None:
                return replayed

        resolved_prefix = await self._prefix_for(
            facility_id=facility_id,
            department_id=data.department_id,
            requested=prefix,
        )

        last_error: Exception | None = None
        for _ in range(_NUMBER_RETRIES):
            number = await self._next_ticket_number(
                facility_id=facility_id, prefix=resolved_prefix
            )
            savepoint = await self.db.begin_nested()
            ticket = QueueTicket(
                facility_id=facility_id,
                patient_id=data.patient_id,
                encounter_id=data.encounter_id,
                department_id=data.department_id,
                service_point_id=data.service_point_id,
                ticket_number=number,
                priority=int(data.priority or 0),
                triage_category=data.triage_category,
                status=QueueTicketStatus.WAITING,
                issued_at=datetime.now(timezone.utc),
                issued_on=datetime.now(timezone.utc).date(),
                notes=data.notes,
                idempotency_key=idempotency_key,
                created_by=created_by,
                updated_by=created_by,
            )
            self.db.add(ticket)
            try:
                await self.db.flush()
                await savepoint.commit()
            except IntegrityError as exc:
                await savepoint.rollback()
                if not _is_ticket_number_collision(exc):
                    raise
                last_error = exc
                continue
            await self.db.refresh(ticket)
            await self.record_event(
                ticket=ticket,
                event=QueueEventType.TICKET_CREATED,
                actor_id=created_by,
                detail={"ticket_number": ticket.ticket_number},
                to_status=QueueTicketStatus.WAITING,
            )
            return ticket
        raise RuntimeError(
            "Could not allocate a queue ticket number"
        ) from last_error

    async def get_ticket_by_number(
        self, *, facility_id: uuid.UUID, ticket_number: str
    ) -> QueueTicket | None:
        """Fetch the newest ticket carrying a printed number, facility-scoped.

        A public speaker knows the number it just announced and never the
        ticket id, so the audio route resolves it through this lookup.

        @param facility_id: Facility the caller is scoped to
        @param ticket_number: The short number on the ticket, e.g. OPD-023
        @returns The ticket, or None when the facility never issued it
        """
        return (
            await self.db.execute(
                select(QueueTicket)
                .where(
                    QueueTicket.facility_id == facility_id,
                    QueueTicket.ticket_number == ticket_number,
                    QueueTicket.is_deleted.is_(False),
                )
                .order_by(QueueTicket.issued_on.desc(), QueueTicket.issued_at.desc())
                .limit(1)
            )
        ).scalars().first()

    async def get_ticket(
        self, *, facility_id: uuid.UUID, ticket_id: uuid.UUID
    ) -> QueueTicket | None:
        """Fetch one ticket, scoped to the facility."""

        return (
            await self.db.execute(
                select(QueueTicket).where(
                    QueueTicket.id == ticket_id,
                    QueueTicket.facility_id == facility_id,
                    QueueTicket.is_deleted.is_(False),
                )
            )
        ).scalars().first()

    async def list_board(
        self,
        *,
        facility_id: uuid.UUID,
        department_id: uuid.UUID | None = None,
        service_point_id: uuid.UUID | None = None,
        include_completed: bool = False,
        limit: int = 300,
    ) -> list[QueueTicket]:
        """Everything the board is showing, in call order."""

        statuses = [
            QueueTicketStatus.WAITING,
            QueueTicketStatus.CALLED,
            QueueTicketStatus.IN_SERVICE,
        ]
        if include_completed:
            statuses.append(QueueTicketStatus.COMPLETED)

        stmt = select(QueueTicket).where(
            QueueTicket.facility_id == facility_id,
            QueueTicket.is_deleted.is_(False),
            QueueTicket.status.in_(statuses),
        )
        if department_id is not None:
            stmt = stmt.where(QueueTicket.department_id == department_id)
        if service_point_id is not None:
            stmt = stmt.where(QueueTicket.service_point_id == service_point_id)
        stmt = stmt.order_by(
            QueueTicket.priority.desc(),
            QueueTicket.issued_at.asc(),
            QueueTicket.id.asc(),
        ).limit(limit)
        return list((await self.db.execute(stmt)).scalars().all())

    async def display_context(
        self, *, facility_id: uuid.UUID, tickets: list[QueueTicket]
    ) -> dict[str, dict]:
        """Resolve the names a board row needs, in a batch per lookup table.

        The board itself only ever renders the ticket number and the room, so
        this deliberately returns no clinical detail - just enough to label a
        row and to say how long someone has been waiting.
        """

        if not tickets:
            return {}

        patient_ids = {t.patient_id for t in tickets if t.patient_id}
        department_ids = {t.department_id for t in tickets if t.department_id}
        point_ids = {t.service_point_id for t in tickets if t.service_point_id}

        patients: dict[uuid.UUID, tuple[str, str]] = {}
        if patient_ids:
            rows = await self.db.execute(
                select(Patient.id, Patient.first_name, Patient.last_name, Patient.mrn).where(
                    Patient.id.in_(patient_ids), Patient.facility_id == facility_id
                )
            )
            for pid, first, last, mrn in rows.all():
                patients[pid] = (f"{first} {last}".strip(), mrn)

        departments: dict[uuid.UUID, str] = {}
        if department_ids:
            rows = await self.db.execute(
                select(Department.id, Department.name).where(
                    Department.id.in_(department_ids), Department.facility_id == facility_id
                )
            )
            departments = {did: name for did, name in rows.all()}

        points: dict[uuid.UUID, tuple[str, str | None]] = {}
        if point_ids:
            rows = await self.db.execute(
                select(
                    QueueServicePoint.id,
                    QueueServicePoint.name,
                    QueueServicePoint.display_label,
                ).where(
                    QueueServicePoint.id.in_(point_ids),
                    QueueServicePoint.facility_id == facility_id,
                )
            )
            points = {pid: (name, label) for pid, name, label in rows.all()}

        now = _now()
        waits = {
            status: [
                t
                for t in tickets
                if t.status == status
            ]
            for status in (QueueTicketStatus.WAITING,)
        }
        positions: dict[uuid.UUID, int] = {}
        for index, ticket in enumerate(waits[QueueTicketStatus.WAITING], start=1):
            positions[ticket.id] = index

        context: dict[str, dict] = {}
        for ticket in tickets:
            name, mrn = patients.get(ticket.patient_id, (None, None))
            point_name, point_label = points.get(ticket.service_point_id, (None, None))
            issued = _as_aware(ticket.issued_at)
            waited = int((now - issued).total_seconds() // 60) if issued else None
            context[str(ticket.id)] = {
                "patient_name": name,
                "patient_mrn": mrn,
                "department_name": departments.get(ticket.department_id),
                "service_point_name": point_name,
                "service_point_label": point_label or point_name,
                "waiting_position": positions.get(ticket.id),
                "waiting_minutes": waited,
            }
        return context

    # -- Transitions ----------------------------------------------------

    async def record_event(
        self,
        *,
        ticket: QueueTicket,
        event: str,
        actor_id: uuid.UUID | None = None,
        service_point_id: uuid.UUID | None = None,
        detail: dict | None = None,
        from_status: str | None = None,
        to_status: str | None = None,
    ) -> QueueEvent:
        """Append one immutable row to the ticket's history."""

        row = QueueEvent(
            facility_id=ticket.facility_id,
            ticket_id=ticket.id,
            event_type=str(event),
            from_status=from_status,
            to_status=to_status,
            actor_id=actor_id,
            service_point_id=service_point_id,
            detail=detail,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def apply_event(
        self,
        *,
        ticket: QueueTicket,
        event: str,
        actor_id: uuid.UUID | None = None,
        service_point_id: uuid.UUID | None = None,
        detail: dict | None = None,
    ) -> QueueTicket:
        """Move a ticket, refusing the move if the state machine says no."""

        previous = ticket.status
        target = assert_transition(previous, event)
        now = _now()

        ticket.status = target
        if event in (QueueEventType.CALLED, QueueEventType.RECALLED):
            ticket.called_at = now
            ticket.called_by = actor_id
            if event == QueueEventType.RECALLED:
                ticket.recall_count = (ticket.recall_count or 0) + 1
        elif event == QueueEventType.SERVICE_STARTED:
            ticket.started_at = now
        elif event == QueueEventType.SERVICE_COMPLETED:
            ticket.completed_at = now

        if service_point_id is not None:
            ticket.service_point_id = service_point_id
        if event == QueueEventType.PRIORITY_CHANGED and detail:
            if detail.get("priority") is not None:
                ticket.priority = int(detail["priority"])
            if detail.get("triage_category") is not None:
                ticket.triage_category = detail["triage_category"]

        ticket.updated_by = actor_id
        await self.record_event(
            ticket=ticket,
            event=event,
            actor_id=actor_id,
            service_point_id=service_point_id or ticket.service_point_id,
            detail=detail,
            from_status=previous,
            to_status=target,
        )
        await self.db.flush()
        await self.db.refresh(ticket)
        return ticket

    async def call_next(
        self,
        *,
        facility_id: uuid.UUID,
        actor_id: uuid.UUID | None,
        department_id: uuid.UUID | None = None,
        service_point_id: uuid.UUID | None = None,
        triage_category: str | None = None,
    ) -> QueueTicket | None:
        """Claim the highest priority waiting ticket, atomically.

        ORDER BY is the whole selection policy: priority first, then who has
        waited longest. No model decides who is called next - that keeps the
        queue auditable and identical whatever the AI layer says.
        """

        filters = [
            QueueTicket.facility_id == facility_id,
            QueueTicket.is_deleted.is_(False),
            QueueTicket.status == QueueTicketStatus.WAITING,
        ]
        if department_id is not None:
            filters.append(QueueTicket.department_id == department_id)
        if service_point_id is not None:
            filters.append(QueueTicket.service_point_id == service_point_id)
        if triage_category is not None:
            filters.append(QueueTicket.triage_category == triage_category)

        stmt = (
            select(QueueTicket)
            .where(*filters)
            .order_by(
                QueueTicket.priority.desc(),
                QueueTicket.issued_at.asc(),
                QueueTicket.id.asc(),
            )
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        ticket = (await self.db.execute(stmt)).scalars().first()
        if ticket is None:
            return None
        return await self.apply_event(
            ticket=ticket,
            event=QueueEventType.CALLED,
            actor_id=actor_id,
            service_point_id=service_point_id,
        )

    async def call_ticket(
        self,
        *,
        ticket: QueueTicket,
        actor_id: uuid.UUID | None,
        service_point_id: uuid.UUID | None = None,
        recalled: bool = False,
    ) -> QueueTicket:
        """Call one chosen ticket, optionally as a recall."""

        return await self.apply_event(
            ticket=ticket,
            event=QueueEventType.RECALLED if recalled else QueueEventType.CALLED,
            actor_id=actor_id,
            service_point_id=service_point_id,
        )

    async def start_service(
        self, *, ticket: QueueTicket, actor_id: uuid.UUID | None, service_point_id: uuid.UUID | None = None
    ) -> QueueTicket:
        """The patient has arrived: they are now being served."""

        return await self.apply_event(
            ticket=ticket,
            event=QueueEventType.SERVICE_STARTED,
            actor_id=actor_id,
            service_point_id=service_point_id,
        )

    async def complete(
        self, *, ticket: QueueTicket, actor_id: uuid.UUID | None
    ) -> QueueTicket:
        """Close the visit."""

        return await self.apply_event(
            ticket=ticket, event=QueueEventType.SERVICE_COMPLETED, actor_id=actor_id
        )

    async def mark_no_show(
        self, *, ticket: QueueTicket, actor_id: uuid.UUID | None, reason: str | None = None
    ) -> QueueTicket:
        """The patient did not come when called."""

        return await self.apply_event(
            ticket=ticket,
            event=QueueEventType.NO_SHOW,
            actor_id=actor_id,
            detail={"reason": reason} if reason else None,
        )

    async def cancel(
        self, *, ticket: QueueTicket, actor_id: uuid.UUID | None, reason: str | None = None
    ) -> QueueTicket:
        """Drop the ticket without it being served."""

        return await self.apply_event(
            ticket=ticket,
            event=QueueEventType.CANCELLED,
            actor_id=actor_id,
            detail={"reason": reason} if reason else None,
        )

    async def change_priority(
        self,
        *,
        ticket: QueueTicket,
        actor_id: uuid.UUID | None,
        priority: int,
        triage_category: str | None = None,
    ) -> QueueTicket:
        """Re-rank a waiting ticket without moving it on."""

        return await self.apply_event(
            ticket=ticket,
            event=QueueEventType.PRIORITY_CHANGED,
            actor_id=actor_id,
            detail={"priority": priority, "triage_category": triage_category},
        )

    async def transfer(
        self,
        *,
        ticket: QueueTicket,
        actor_id: uuid.UUID | None,
        department_id: uuid.UUID,
        service_point_id: uuid.UUID | None = None,
        reason: str | None = None,
    ) -> tuple[QueueTicket, QueueTicket]:
        """Hand the patient to another department's queue.

        The old ticket becomes TRANSFERRED and a fresh WAITING ticket is
        issued for the target department, so the two departments each see a
        clean queue and the history stays on one ticket.
        """

        await self.apply_event(
            ticket=ticket,
            event=QueueEventType.TRANSFERRED,
            actor_id=actor_id,
            service_point_id=service_point_id,
            detail={"department_id": str(department_id), "reason": reason},
        )

        class _Target:
            pass

        target = _Target()
        target.patient_id = ticket.patient_id
        target.encounter_id = ticket.encounter_id
        target.department_id = department_id
        target.service_point_id = service_point_id
        target.priority = ticket.priority
        target.triage_category = ticket.triage_category
        target.notes = ticket.notes

        new_ticket = await self.issue_ticket(
            facility_id=ticket.facility_id, data=target, created_by=actor_id
        )
        await self.record_event(
            ticket=new_ticket,
            event=QueueEventType.TRANSFERRED,
            actor_id=actor_id,
            detail={"from_ticket_id": str(ticket.id), "reason": reason},
        )
        return ticket, new_ticket

    async def events_for(
        self, *, facility_id: uuid.UUID, ticket_id: uuid.UUID
    ) -> list[QueueEvent]:
        """The ticket's history, oldest first."""

        stmt = (
            select(QueueEvent)
            .where(
                QueueEvent.facility_id == facility_id,
                QueueEvent.ticket_id == ticket_id,
            )
            .order_by(QueueEvent.created_at.asc())
        )
        return list((await self.db.execute(stmt)).scalars().all())

    async def stats(
        self, *, facility_id: uuid.UUID, department_id: uuid.UUID | None = None
    ) -> dict:
        """Operational counters for the staff dashboard."""

        base = [
            QueueTicket.facility_id == facility_id,
            QueueTicket.is_deleted.is_(False),
        ]
        if department_id is not None:
            base.append(QueueTicket.department_id == department_id)

        async def count(status: str) -> int:
            stmt = select(func.count()).select_from(QueueTicket).where(
                *base, QueueTicket.status == status
            )
            return int((await self.db.execute(stmt)).scalar_one())

        today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
        completed_today = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(QueueTicket)
                    .where(
                        *base,
                        QueueTicket.status == QueueTicketStatus.COMPLETED,
                        QueueTicket.completed_at >= today,
                    )
                )
            ).scalar_one()
        )
        no_show_today = int(
            (
                await self.db.execute(
                    select(func.count())
                    .select_from(QueueTicket)
                    .where(
                        *base,
                        QueueTicket.status == QueueTicketStatus.NO_SHOW,
                        QueueTicket.updated_at >= today,
                    )
                )
            ).scalar_one()
        )

        waiting_rows = (
            await self.db.execute(
                select(QueueTicket.issued_at, QueueTicket.department_id).where(
                    *base, QueueTicket.status == QueueTicketStatus.WAITING
                )
            )
        ).all()
        now = _now()
        waits = [
            int((now - _as_aware(issued)).total_seconds() // 60)
            for issued, _ in waiting_rows
            if issued is not None
        ]

        by_department: dict[str, int] = {}
        for _, dept in waiting_rows:
            key = str(dept) if dept else "unassigned"
            by_department[key] = by_department.get(key, 0) + 1

        return {
            "waiting": await count(QueueTicketStatus.WAITING),
            "called": await count(QueueTicketStatus.CALLED),
            "in_service": await count(QueueTicketStatus.IN_SERVICE),
            "completed_today": completed_today,
            "no_show_today": no_show_today,
            "average_wait_minutes": round(sum(waits) / len(waits), 1) if waits else None,
            "longest_wait_minutes": max(waits) if waits else None,
            "by_department": [
                {"department_id": key, "waiting": value}
                for key, value in sorted(by_department.items())
            ],
        }

    def announcement_text(self, ticket: QueueTicket, destination: str | None) -> str:
        """The words the speaker says for this ticket."""

        return build_call_text(ticket.ticket_number, destination)


def _now() -> datetime:
    """Timezone-aware now, so comparisons match the tz-aware columns."""

    return datetime.now(timezone.utc)


def _as_aware(value: datetime | None) -> datetime | None:
    """SQLite may hand back naive datetimes; treat them as UTC."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
