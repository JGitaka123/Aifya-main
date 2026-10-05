"""The queue state machine.

Permanent ticket states and the transitional events that move them are
deliberately different vocabularies. A ticket is WAITING or CALLED; TICKET_CREATED
or RECALLED is something that happened to it. Keeping the two apart stops a
status column from slowly filling up with event names.

TRANSITIONS is the single source of truth. Every write goes through
assert_transition(), and the API refuses an illegal move with a 409 instead of
quietly corrupting the ticket. The database - not the browser - is the
authority: the frontend may hide a button, but this table is what enforces it.
"""

from __future__ import annotations

from enum import StrEnum


class QueueTicketStatus(StrEnum):
    """Where a ticket permanently is."""

    WAITING = "WAITING"
    CALLED = "CALLED"
    IN_SERVICE = "IN_SERVICE"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"
    TRANSFERRED = "TRANSFERRED"


class QueueEventType(StrEnum):
    """What just happened to a ticket."""

    TICKET_CREATED = "TICKET_CREATED"
    CALLED = "CALLED"
    RECALLED = "RECALLED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    ROOM_ASSIGNED = "ROOM_ASSIGNED"
    SERVICE_STARTED = "SERVICE_STARTED"
    SERVICE_COMPLETED = "SERVICE_COMPLETED"
    TRANSFERRED = "TRANSFERRED"
    NO_SHOW = "NO_SHOW"
    CANCELLED = "CANCELLED"


class IllegalTransition(ValueError):
    """Raised when an event cannot move a ticket from its current state."""

    def __init__(self, current: str, event: str) -> None:
        self.current = current
        self.event = event
        super().__init__(
            f"Cannot apply {event} to a ticket that is {current}"
        )


#: current status -> event -> the status the ticket ends up in.
TRANSITIONS: dict[str, dict[str, str]] = {
    QueueTicketStatus.WAITING: {
        # A call claims the ticket. A recall is only meaningful once called,
        # so from WAITING it behaves as a first call.
        QueueEventType.CALLED: QueueTicketStatus.CALLED,
        QueueEventType.RECALLED: QueueTicketStatus.CALLED,
        QueueEventType.ROOM_ASSIGNED: QueueTicketStatus.WAITING,
        QueueEventType.PRIORITY_CHANGED: QueueTicketStatus.WAITING,
        QueueEventType.CANCELLED: QueueTicketStatus.CANCELLED,
        QueueEventType.TRANSFERRED: QueueTicketStatus.TRANSFERRED,
    },
    QueueTicketStatus.CALLED: {
        QueueEventType.RECALLED: QueueTicketStatus.CALLED,
        QueueEventType.CALLED: QueueTicketStatus.CALLED,
        QueueEventType.SERVICE_STARTED: QueueTicketStatus.IN_SERVICE,
        QueueEventType.ROOM_ASSIGNED: QueueTicketStatus.CALLED,
        QueueEventType.PRIORITY_CHANGED: QueueTicketStatus.CALLED,
        QueueEventType.NO_SHOW: QueueTicketStatus.NO_SHOW,
        QueueEventType.CANCELLED: QueueTicketStatus.CANCELLED,
        QueueEventType.TRANSFERRED: QueueTicketStatus.TRANSFERRED,
    },
    QueueTicketStatus.IN_SERVICE: {
        QueueEventType.SERVICE_COMPLETED: QueueTicketStatus.COMPLETED,
        QueueEventType.TRANSFERRED: QueueTicketStatus.TRANSFERRED,
        QueueEventType.CANCELLED: QueueTicketStatus.CANCELLED,
    },
    # Terminal states. Nothing moves a ticket out of them, so a late or
    # duplicated call from the browser can never resurrect it.
    QueueTicketStatus.COMPLETED: {},
    QueueTicketStatus.NO_SHOW: {},
    QueueTicketStatus.CANCELLED: {},
    QueueTicketStatus.TRANSFERRED: {},
}

#: Events that only annotate a ticket without moving it on.
NON_MUTATING_EVENTS = frozenset(
    {
        QueueEventType.ROOM_ASSIGNED,
        QueueEventType.PRIORITY_CHANGED,
    }
)


def next_status(current: str, event: str) -> str:
    """Return the status an event moves a ticket to.

    @param current: The ticket's current permanent status
    @param event: The event being applied
    @returns The resulting permanent status
    @raises IllegalTransition: When the event cannot apply to that status
    """

    row = TRANSITIONS.get(str(current))
    if row is None:
        raise IllegalTransition(str(current), str(event))
    target = row.get(str(event))
    if target is None:
        raise IllegalTransition(str(current), str(event))
    return target


def assert_transition(current: str, event: str) -> str:
    """Validate a transition, raising IllegalTransition when it is not allowed."""

    return next_status(current, event)


def is_terminal(status: str) -> bool:
    """Whether no event can move a ticket out of this state."""

    return not TRANSITIONS.get(str(status))
