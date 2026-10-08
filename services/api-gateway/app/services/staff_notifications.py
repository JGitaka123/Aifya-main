"""Tell a staff member their Aifya access is on.

Registering an employee and switching their account on are two separate acts in
HR: an employee row can exist with no login, and a login can exist with the
account switched off. Activation is the moment that matters to the employee, so
that is when Aifya writes to them: where to sign in, the hospital to name, the
state of duty HR recorded, and - only when HR set one on the form - the initial
password they start with.

Delivery is best effort. A mail server that is slow, down or unconfigured must
not undo an activation HR has already made, so a failed send is logged and
reported back in the response rather than raised.
"""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.permissions import duty_label
from app.config import settings
from app.models.facility import Facility
from app.models.staff import Staff
from app.services.comms.email_provider import get_email_provider

logger = structlog.get_logger(__name__)

#: ``sync_employee_to_staff`` invents ``<employee_number>@aifya.co.ke`` for an
#: employee registered without an address, so the staff row always has
#: something to show. Nobody reads that mailbox, so an activation email must
#: not be aimed at it.
_PLACEHOLDER_DOMAIN = "aifya.co.ke"


def _is_placeholder_address(staff: Staff) -> bool:
    """
    Whether the staff email is the generated, undeliverable fallback.

    @param staff: The staff row whose address is being checked
    @returns True when the address was invented rather than supplied by HR
    """
    address = (staff.email or "").strip().lower()
    return address == f"{staff.employee_number}@{_PLACEHOLDER_DOMAIN}".lower()


def build_staff_activation_email(
    *,
    facility_name: str,
    staff: Staff,
    password: str | None = None,
) -> tuple[str, str]:
    """
    Compose the subject and body of a staff activation email.

    Kept separate from delivery so the wording can be tested without a mail
    server and reused if a second channel is added later.

    @param facility_name: Hospital name, shown to the employee and typed at sign-in
    @param staff: The staff row whose login was switched on
    @param password: Initial password HR set, when there is one to share
    @returns (subject, body) ready to hand to an email provider
    """
    name = f"{staff.first_name} {staff.last_name}".strip() or staff.email
    duty = duty_label(staff.role)
    lines = [
        f"Hello {name},",
        "",
        (
            f"Your Aifya account at {facility_name} has been activated by HR. "
            "You can now sign in."
        ),
        "",
        f"Sign in at: {settings.web_base_url}/login",
        f"Sign-in email: {staff.email}",
        f"Employee number: {staff.employee_number}",
    ]
    if duty:
        lines.append(f"State of duty: {duty}")
    if password:
        lines += [
            "",
            f"Your initial password is: {password}",
            "Change it after your first sign-in.",
        ]
    else:
        lines += [
            "",
            (
                "Use the password HR gave you. If you do not have one, ask HR "
                "to reset it."
            ),
        ]
    lines += [
        "",
        (
            "At sign-in you choose your state of duty and type the hospital "
            "name exactly as it appears above."
        ),
        "",
        f"- {facility_name} on Aifya",
    ]
    return (
        f"Your Aifya account at {facility_name} is active",
        "\n".join(lines),
    )


async def send_staff_activation_email(
    *,
    facility_name: str,
    staff: Staff,
    password: str | None = None,
) -> bool:
    """
    Email a staff member that their account is active.

    Never raises: activation has already happened by the time this runs, and a
    failed message must not roll it back. The caller reports the boolean so the
    HR screen can tell whether the email went out.

    @param facility_name: Hospital name, shown to the employee and typed at sign-in
    @param staff: The staff row whose login was switched on
    @param password: Initial password HR set, when there is one to share
    @returns True when the provider accepted the message for delivery
    """
    address = (staff.email or "").strip()
    if not address or _is_placeholder_address(staff):
        logger.warning("staff_activation_email_skipped", staff_id=str(staff.id))
        return False

    subject, body = build_staff_activation_email(
        facility_name=facility_name,
        staff=staff,
        password=password,
    )
    provider = get_email_provider()
    if not provider.is_configured:
        logger.warning(
            "staff_activation_email_unconfigured",
            staff_id=str(staff.id),
            address=address,
        )
        return False
    sent = await provider.send_email(address, subject, body)
    if not sent:
        logger.warning(
            "staff_activation_email_failed",
            staff_id=str(staff.id),
            address=address,
            reason=provider.last_error,
        )
    return sent


async def notify_staff_activated(
    db: AsyncSession,
    *,
    facility_id: uuid.UUID,
    staff: Staff,
    password: str | None = None,
) -> bool:
    """
    Look up the hospital and email a staff member their activation details.

    Wraps ``send_staff_activation_email`` with the facility lookup and the
    fallback name, so the routers that activate or grant access do not each
    repeat it. The hospital name has to be right: the sign-in form matches it
    against the employee's record, so a wrong name turns a welcome into a
    refused sign-in.

    @param db: Database session
    @param facility_id: Facility the staff member was activated at
    @param staff: The staff row whose login was switched on
    @param password: Initial password HR set, when there is one to share
    @returns True when the provider accepted the message for delivery
    """
    facility = await db.get(Facility, facility_id)
    return await send_staff_activation_email(
        facility_name=facility.name if facility else "your facility",
        staff=staff,
        password=password,
    )
