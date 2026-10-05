"""Concurrency races for CALL NEXT.

Two callers pressing "call next" at the same instant must never be handed the
same patient. On SQLite (the default suite) the locking clause is a no-op, so
the guarantee is asserted at the level the database can still prove: the API
hands every caller a different ticket.

The faithful race - many workers, each in its own transaction, relying on
``SELECT ... FOR UPDATE SKIP LOCKED`` - needs a real Postgres. That test is
opt-in: export ``TEST_POSTGRES_DSN`` to a database the suite may write to and
it will seed a throwaway facility, run the race and clean up after itself.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.models.patient import Patient
from app.services.queue.queue_service import QueueService

QUEUE = "/api/v1/queue"
POSTGRES_DSN = os.getenv("TEST_POSTGRES_DSN")


def _is_sqlite() -> bool:
    """True when the suite is running on SQLite, which cannot skip locked rows."""

    return settings.database_url.startswith("sqlite")


async def _register_patient(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/patients",
        json={
            "first_name": "Race",
            "last_name": "Tester",
            "date_of_birth": "1991-03-04",
            "gender": "male",
            "phone_number": "0700333444",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


@pytest.mark.asyncio
async def test_four_concurrent_calls_claim_four_distinct_tickets(
    client: AsyncClient,
) -> None:
    """A burst of CALL NEXT calls must fan out over the waiting list.

    SQLite has no ``SELECT ... FOR UPDATE SKIP LOCKED``, so on the default
    suite the calls are serialised behind a mutex: every caller still goes
    through the API and the claimed tickets must fan out exactly. The
    lock-contended race is covered by the opt-in Postgres test below.
    """

    patient_id = await _register_patient(client)
    issued = [
        (await client.post(f"{QUEUE}/tickets", json={"patient_id": patient_id})).json()
        for _ in range(4)
    ]

    if _is_sqlite():
        mutex = asyncio.Lock()

        async def call_next():
            async with mutex:
                return await client.post(f"{QUEUE}/call-next", json={})

        responses = await asyncio.gather(*(call_next() for _ in range(4)))
    else:
        responses = await asyncio.gather(
            *(client.post(f"{QUEUE}/call-next", json={}) for _ in range(4))
        )
    assert all(response.status_code == 200 for response in responses), [
        response.text for response in responses
    ]

    called_ids = [response.json()["id"] for response in responses]
    assert len(set(called_ids)) == 4, "a patient was called by two workers"
    assert set(called_ids) == {ticket["id"] for ticket in issued}
    assert all(response.json()["status"] == "CALLED" for response in responses)


@pytest.mark.skipif(not POSTGRES_DSN, reason="set TEST_POSTGRES_DSN to run")
@pytest.mark.asyncio
async def test_call_next_race_under_load_on_postgres() -> None:
    """Many processes' worth of workers race for the same waiting list.

    Each worker runs in its own session and transaction, so this exercises the
    real ``FOR UPDATE SKIP LOCKED`` path rather than a single-connection
    simulation: over-subscribe the queue and assert nobody is served twice.
    """

    facility = uuid.uuid4()
    total, workers = 20, 32
    engine = create_async_engine(POSTGRES_DSN, pool_size=25, max_overflow=10)
    maker = async_sessionmaker(engine, expire_on_commit=False)

    async def scope(session) -> None:
        await session.execute(
            text("select set_config('app.current_facility_id', :f, true)"),
            {"f": str(facility)},
        )

    class _Target:
        def __init__(self, patient_id: uuid.UUID) -> None:
            self.patient_id = patient_id
            self.encounter_id = None
            self.department_id = None
            self.service_point_id = None
            self.triage_category = None
            self.priority = 0
            self.notes = None
            self.idempotency_key = None

    try:
        async with maker() as session:
            await scope(session)
            patient = Patient(
                facility_id=facility,
                mrn="RACE-TEST-1",
                first_name="Race",
                last_name="Load",
                date_of_birth=date(1990, 1, 1),
                gender="female",
                phone_number="0700000009",
            )
            session.add(patient)
            await session.flush()
            service = QueueService(session)
            for _ in range(total):
                await service.issue_ticket(
                    facility_id=facility,
                    data=_Target(patient.id),
                    created_by=None,
                )
            await session.commit()

        async def claim() -> str | None:
            async with maker() as session:
                await scope(session)
                ticket = await QueueService(session).call_next(
                    facility_id=facility, actor_id=None
                )
                await session.commit()
                return str(ticket.id) if ticket else None

        results = await asyncio.gather(*(claim() for _ in range(workers)))
        claimed = [ticket for ticket in results if ticket is not None]

        assert len(claimed) == total, f"expected {total} claims, got {len(claimed)}"
        assert len(set(claimed)) == len(claimed), "a ticket was handed out twice"
        assert results.count(None) == workers - total
    finally:
        async with maker() as session:
            await scope(session)
            for table in (
                "queue_events",
                "queue_announcements",
                "queue_tickets",
                "patients",
            ):
                await session.execute(
                    text(f"delete from {table} where facility_id = :f"),
                    {"f": facility},
                )
            await session.commit()
        await engine.dispose()
