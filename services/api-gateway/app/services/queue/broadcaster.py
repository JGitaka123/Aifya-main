"""Fan-out of queue events to live boards and speakers.

The board and the speaker are read-only projections of the database, so a
dropped connection is never a data problem: on reconnect the client fetches a
full snapshot and then resumes listening. That is why this is a plain
in-process pub/sub with no delivery guarantees.

Single worker: this fan-out lives in the process that accepted the request. A
multi-worker deployment should bridge it through Redis pub/sub so every worker
sees every event; the publish/subscribe surface below is the seam for that.
"""

from __future__ import annotations

import asyncio
from typing import Any


class QueueBroadcaster:
    """Tracks connected subscribers and pushes events to each of them."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self, maxsize: int = 100) -> asyncio.Queue:
        """Register a subscriber and return its inbox."""

        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Stop sending to a subscriber."""

        self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        """How many boards or speakers are connected right now."""

        return len(self._subscribers)

    async def publish(self, event: dict[str, Any]) -> None:
        """Deliver an event to every subscriber, dropping slow consumers' backlog."""

        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # A board that cannot keep up loses intermediate events but
                # still receives the next one; the snapshot on reconnect
                # repairs anything it missed.
                continue


#: Process-wide broadcaster shared by the queue router and the SSE endpoint.
broadcaster = QueueBroadcaster()
