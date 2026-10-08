"""HR switches an account on and Aifya tells the employee.

Activation is the moment a worker can finally sign in, so it is the moment the
employee is emailed. These tests pin the delivery rules: only the off->on
transition sends, only when there is a login to sign in with, and the message
carries what the sign-in form demands - the hospital name and the state of duty.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.auth_account import AuthAccount
from app.models.facility import Facility
from app.models.staff import Staff
from app.services import staff_notifications
from app.utils.passwords import hash_password
from tests.conftest import FACILITY_ID, USER_ID, session_factory

pytestmark = pytest.mark.asyncio

FACILITY_NAME = "Aifya Test Hospital"


class _RecordingEmailProvider:
    """A stand-in mail provider that remembers what Aifya tried to send."""

    def __init__(self) -> None:
        """Start with an empty outbox."""
        self.sent: list[dict[str, str]] = []
        self.last_error: str | None = None

    @property
    def is_configured(self) -> bool:
        """Behave like a live SMTP provider."""
        return True

    async def send_email(self, address: str, subject: str, body: str) -> bool:
        """
        Record one message instead of delivering it.

        @param address: Recipient email address
        @param subject: Subject line
        @param body: Plain-text message body
        @returns Always True, as a healthy server would
        """
        self.sent.append({"address": address, "subject": subject, "body": body})
        return True


class _UnconfiguredEmailProvider:
    """A provider with no mail server behind it, as in local development."""

    last_error: str | None = None

    @property
    def is_configured(self) -> bool:
        """Report that nothing can be delivered."""
        return False

    async def send_email(self, address: str, subject: str, body: str) -> bool:
        """Fail the test if delivery is attempted without configuration."""
        raise AssertionError("delivery must not be attempted when unconfigured")


@pytest.fixture
async def facility(setup_database: None) -> None:
    """Seed the hospital an employee's sign-in would bind to."""
    async with session_factory() as db:
        db.add(
            Facility(
                id=FACILITY_ID,
                name=FACILITY_NAME,
                code="AIFYA-TEST",
                facility_type="hospital",
                timezone="Africa/Nairobi",
                currency="KES",
                onboarding_status="approved",
                is_active=True,
            )
        )
        await db.commit()


@pytest.fixture
def mailbox(monkeypatch: pytest.MonkeyPatch) -> _RecordingEmailProvider:
    """Capture activation emails instead of sending them."""
    provider = _RecordingEmailProvider()
    monkeypatch.setattr(
        staff_notifications, "get_email_provider", lambda: provider
    )
    return provider


async def _make_staff(
    *, active: bool, with_login: bool, role: str = "dentist"
) -> Staff:
    """
    Insert a staff row, optionally with a sign-in.

    @param active: Whether the staff record starts switched on
    @param with_login: Whether to create the matching auth account
    @param role: Role HR recorded on the staff row
    @returns The persisted staff row
    """
    suffix = uuid.uuid4().hex[:8]
    async with session_factory() as db:
        staff = Staff(
            facility_id=FACILITY_ID,
            keycloak_user_id=uuid.uuid4(),
            employee_number=f"EMP-{suffix}",
            first_name="Mary",
            last_name=f"Wanjiku{suffix}",
            role=role,
            email=f"mary-{suffix}@example.com",
            is_active=active,
            created_by=USER_ID,
            updated_by=USER_ID,
        )
        db.add(staff)
        await db.flush()
        if with_login:
            db.add(
                AuthAccount(
                    staff_id=staff.id,
                    facility_id=FACILITY_ID,
                    email=staff.email,
                    password_hash=hash_password("InitialPass1"),
                    is_active=active,
                )
            )
        await db.commit()
        await db.refresh(staff)
        return staff


async def _set_active(client: AsyncClient, staff_id: object, is_active: bool):
    """Call the HR activation endpoint."""
    return await client.patch(
        f"/api/v1/hr/staff/{staff_id}/active", json={"is_active": is_active}
    )


async def test_activating_a_worker_emails_them(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """Switching an account on sends the employee their sign-in details."""
    staff = await _make_staff(active=False, with_login=True)

    response = await _set_active(client, staff.id, True)

    assert response.status_code == 200
    body = response.json()
    assert body["is_active"] is True
    assert body["activation_email_sent"] is True
    assert len(mailbox.sent) == 1
    message = mailbox.sent[0]
    assert message["address"] == staff.email
    assert FACILITY_NAME in message["subject"]
    # Both facts the sign-in form demands are in the message: the hospital by
    # name, and the state of duty HR recorded.
    assert FACILITY_NAME in message["body"]
    assert "Dentist" in message["body"]


async def test_deactivating_a_worker_is_silent(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """Switching access off never emails the employee."""
    staff = await _make_staff(active=True, with_login=True)

    response = await _set_active(client, staff.id, False)

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert response.json()["activation_email_sent"] is False
    assert mailbox.sent == []


async def test_activating_without_a_login_sends_nothing(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """An activated record with no login has nothing to sign in with."""
    staff = await _make_staff(active=False, with_login=False)

    response = await _set_active(client, staff.id, True)

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert response.json()["activation_email_sent"] is False
    assert mailbox.sent == []


async def test_reactivation_emails_again(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """Off then on is an activation, so the employee hears about it."""
    staff = await _make_staff(active=True, with_login=True)

    await _set_active(client, staff.id, False)
    assert mailbox.sent == []

    response = await _set_active(client, staff.id, True)

    assert response.json()["activation_email_sent"] is True
    assert len(mailbox.sent) == 1


async def test_activation_succeeds_when_mail_is_unconfigured(
    client: AsyncClient,
    facility: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing mail server must not block the activation HR just made."""
    monkeypatch.setattr(
        staff_notifications,
        "get_email_provider",
        _UnconfiguredEmailProvider,
    )
    staff = await _make_staff(active=False, with_login=True)

    response = await _set_active(client, staff.id, True)

    assert response.status_code == 200
    assert response.json()["is_active"] is True
    assert response.json()["activation_email_sent"] is False


async def test_registering_a_worker_with_a_password_emails_them(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """Registering with a first password hands the worker their login by email."""
    email = f"grace.{uuid.uuid4().hex[:6]}@example.com"

    response = await client.post(
        "/api/v1/payroll/employees",
        json={
            "staff_id": f"EMP-{uuid.uuid4().hex[:8].upper()}",
            "full_name": "Grace Achieng",
            "job_title": "Dental Officer",
            "employment_type": "permanent",
            "hire_date": "2026-02-01",
            "email": email,
            "role": "dentist",
            "login_password": "DentalPass1",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["has_login"] is True
    assert body["activation_email_sent"] is True
    assert len(mailbox.sent) == 1
    message = mailbox.sent[0]
    assert message["address"] == email
    # The password HR set on the form travels with the welcome message, so the
    # employee can sign in without HR relaying it by hand.
    assert "DentalPass1" in message["body"]


async def test_registering_without_a_password_does_not_email(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """A record-only employee gets no login, so no activation email."""
    response = await client.post(
        "/api/v1/payroll/employees",
        json={
            "staff_id": f"EMP-{uuid.uuid4().hex[:8].upper()}",
            "full_name": "Peter Otieno",
            "employment_type": "permanent",
            "hire_date": "2026-02-01",
            "email": f"peter.{uuid.uuid4().hex[:6]}@example.com",
            "role": "nurse",
        },
    )

    assert response.status_code == 201
    assert response.json()["has_login"] is False
    assert response.json()["activation_email_sent"] is False
    assert mailbox.sent == []


async def test_setting_a_first_password_grants_access_and_emails(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """HR can grant access to a record-only employee without re-registering."""
    staff = await _make_staff(active=True, with_login=False)

    response = await client.post(
        f"/api/v1/hr/staff/{staff.id}/password",
        json={"password": "FirstPass123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_login"] is True
    assert body["activation_email_sent"] is True
    assert len(mailbox.sent) == 1
    assert "FirstPass123" in mailbox.sent[0]["body"]

    async with session_factory() as db:
        account = (
            await db.execute(
                select(AuthAccount).where(AuthAccount.staff_id == staff.id)
            )
        ).scalar_one()
    assert account.is_active is True


async def test_setting_a_password_while_deactivated_does_not_email(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """A switched-off employee is not told they can sign in."""
    staff = await _make_staff(active=False, with_login=False)

    response = await client.post(
        f"/api/v1/hr/staff/{staff.id}/password",
        json={"password": "HiddenPass1"},
    )

    assert response.status_code == 200
    assert response.json()["has_login"] is True
    assert response.json()["activation_email_sent"] is False
    assert mailbox.sent == []


async def test_activation_email_skips_the_generated_placeholder(
    client: AsyncClient,
    facility: None,
    mailbox: _RecordingEmailProvider,
) -> None:
    """An employee registered without an address has no mailbox to write to."""
    staff = await _make_staff(active=False, with_login=True)
    async with session_factory() as db:
        row = await db.get(Staff, staff.id)
        assert row is not None
        row.email = f"{row.employee_number}@aifya.co.ke"
        await db.commit()

    response = await _set_active(client, staff.id, True)

    assert response.status_code == 200
    assert response.json()["activation_email_sent"] is False
    assert mailbox.sent == []
