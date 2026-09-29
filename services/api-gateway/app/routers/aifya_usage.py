"""Aifya usage billing - the HR view of what the hospital owes Aifya.

Reads need ``hr.view``; recomputing the ledger, changing the rate, raising and
settling invoices need ``hr.manage``. Closing a month and voiding an invoice
need an administrator. The whole router sits behind the ``hr`` module gate,
matching the payroll router, because this is an HR-facing surface.

This is a hospital-facing bill. Nothing in this router touches a patient
invoice.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, require_roles
from app.auth.license_check import require_module
from app.auth.permissions import Permission, require_permission
from app.database import get_db
from app.models.aifya_usage import AifyaUsageDaily, AifyaUsageInvoice
from app.models.facility import Facility
from app.schemas.aifya_usage import (
    UsageAccrualRequest,
    UsageConfigResponse,
    UsageConfigUpdate,
    UsageDayResponse,
    UsageFinalizeRequest,
    UsageInvoiceCreate,
    UsageInvoicePayment,
    UsageInvoiceResponse,
    UsageMonthResponse,
    UsageRangeResponse,
)
from app.services.aifya_usage_service import (
    AifyaUsageService,
    month_bounds,
    period_label,
)

router = APIRouter(dependencies=[Depends(require_module("hr"))])

#: Closing a month and voiding an invoice are commercial acts, not clerical.
ADMIN_ROLES = ("admin", "facility_admin", "hospital_administrator", "hr_admin")


def _to_day(row: AifyaUsageDaily) -> UsageDayResponse:
    """
    @param row: Ledger row
    @returns The row as an API response object
    """
    return UsageDayResponse.model_validate(row, from_attributes=True)


def _to_invoice(row: AifyaUsageInvoice) -> UsageInvoiceResponse:
    """
    @param row: Invoice row
    @returns The invoice as an API response object, with derived fields filled
    """
    return UsageInvoiceResponse(
        id=str(row.id),
        invoice_number=row.invoice_number,
        period_year=row.period_year,
        period_month=row.period_month,
        period_label=period_label(row.period_year, row.period_month),
        status=row.status,
        patient_days=row.patient_days,
        registration_patient_days=row.registration_patient_days,
        emergency_patient_days=row.emergency_patient_days,
        inpatient_patient_days=row.inpatient_patient_days,
        rate_cents=row.rate_cents,
        amount_cents=row.amount_cents,
        paid_cents=row.paid_cents,
        balance_cents=max(row.amount_cents - row.paid_cents, 0),
        currency=row.currency,
        issued_at=row.issued_at,
        due_at=row.due_at,
        paid_at=row.paid_at,
        payment_reference=row.payment_reference,
        notes=row.notes,
    )


async def _facility_name(db: AsyncSession, facility_id: uuid.UUID) -> str:
    """
    @param db: Database session
    @param facility_id: Facility UUID
    @returns The facility's display name, or an empty string when unknown
    """
    name = (
        await db.execute(select(Facility.name).where(Facility.id == facility_id))
    ).scalar_one_or_none()
    return name or ""


async def _month_payload(
    db: AsyncSession, service: AifyaUsageService, facility_id: uuid.UUID,
    year: int, month: int,
) -> UsageMonthResponse:
    """
    Build the month summary, including whatever invoice exists for it.

    @param db: Database session
    @param service: Usage service
    @param facility_id: Facility UUID
    @param year: Calendar year
    @param month: Calendar month, 1-12
    @returns The month's usage and its invoice, when one has been raised
    """
    rows = await service.month_view(facility_id, year, month)
    agg = AifyaUsageService.totals(rows)
    rate_cents, currency, configured, _ = await service.get_config(facility_id)
    invoice = await service.invoice_for_month(facility_id, year, month)
    return UsageMonthResponse(
        year=year,
        month=month,
        period_label=period_label(year, month),
        facility_id=str(facility_id),
        facility_name=await _facility_name(db, facility_id),
        currency=rows[0].currency if rows else currency,
        rate_cents=rows[0].rate_cents if rows else rate_cents,
        rate_is_confirmed=configured,
        rate_changed_mid_month=len({row.rate_cents for row in rows}) > 1,
        total_patient_days=int(agg["total_patient_days"]),
        registration_patient_days=int(agg["registration_patient_days"]),
        emergency_patient_days=int(agg["emergency_patient_days"]),
        inpatient_patient_days=int(agg["inpatient_patient_days"]),
        total_amount_cents=int(agg["total_amount_cents"]),
        is_finalized=bool(agg["is_finalized"]),
        invoice=_to_invoice(invoice) if invoice is not None else None,
        days=[_to_day(row) for row in rows],
    )


# ── Rate ────────────────────────────────────────────────────────────────────


@router.get("/config", response_model=UsageConfigResponse)
async def get_usage_config(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_VIEW)),
) -> UsageConfigResponse:
    """
    Read the rate the hospital is billed at.

    ``is_configured`` is False while the built-in placeholder rate is in force:
    the figure is real enough to meter against but has not been agreed, so it
    must not be used for actual hospital billing until someone confirms it.

    @param db: Database session
    @param current_user: Authenticated user holding hr.view
    @returns The current rate
    """
    service = AifyaUsageService(db)
    rate_cents, currency, configured, notes = await service.get_config(
        current_user.facility_id
    )
    return UsageConfigResponse(
        rate_cents=rate_cents,
        currency=currency,
        notes=notes,
        is_configured=configured,
    )


@router.put("/config", response_model=UsageConfigResponse)
async def update_usage_config(
    data: UsageConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_MANAGE)),
) -> UsageConfigResponse:
    """
    Change the patient-day rate for this facility.

    Days already finalized keep the rate they were billed at, so closing a
    month is what protects it from a later change.

    @param data: New rate
    @param db: Database session
    @param current_user: Authenticated user holding hr.manage
    @returns The stored rate
    """
    service = AifyaUsageService(db)
    row = await service.set_config(
        current_user.facility_id,
        rate_cents=data.rate_cents,
        currency=data.currency,
        notes=data.notes,
        actor_id=current_user.user_id,
    )
    return UsageConfigResponse(
        rate_cents=row.rate_cents,
        currency=row.currency,
        notes=row.notes,
        is_configured=True,
    )


# ── Ledger ──────────────────────────────────────────────────────────────────


@router.post("/accrue", response_model=UsageRangeResponse)
async def accrue_usage(
    data: UsageAccrualRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_MANAGE)),
) -> UsageRangeResponse:
    """
    Compute (or refresh) the usage ledger for a range of days.

    Safe to call repeatedly: the same encounters and admissions always produce
    the same figures. Finalized days are skipped unless ``force`` is set.

    @param data: Range to compute
    @param db: Database session
    @param current_user: Authenticated user holding hr.manage
    @returns The refreshed ledger for the range, with its totals
    """
    service = AifyaUsageService(db)
    rows = await service.recompute_range(
        current_user.facility_id,
        data.start_date,
        data.end_date,
        force=data.force,
        actor_id=current_user.user_id,
    )
    agg = AifyaUsageService.totals(rows)
    rate_cents, currency, _, _ = await service.get_config(current_user.facility_id)
    return UsageRangeResponse(
        start_date=data.start_date,
        end_date=data.end_date,
        currency=rows[0].currency if rows else currency,
        rate_cents=rows[0].rate_cents if rows else rate_cents,
        total_patient_days=int(agg["total_patient_days"]),
        registration_patient_days=int(agg["registration_patient_days"]),
        emergency_patient_days=int(agg["emergency_patient_days"]),
        inpatient_patient_days=int(agg["inpatient_patient_days"]),
        total_amount_cents=int(agg["total_amount_cents"]),
        days=[_to_day(row) for row in rows],
    )


@router.get("/daily", response_model=UsageRangeResponse)
async def get_usage_daily(
    start: date = Query(..., description="First day, inclusive"),
    end: date = Query(..., description="Last day, inclusive"),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_VIEW)),
) -> UsageRangeResponse:
    """
    Read the stored usage ledger for a range. Does not recompute.

    @param start: First day
    @param end: Last day
    @param db: Database session
    @param current_user: Authenticated user holding hr.view
    @returns Stored ledger rows plus totals
    """
    if end < start:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must not be before start",
        )
    service = AifyaUsageService(db)
    rows = await service.ledger_for_range(current_user.facility_id, start, end)
    agg = AifyaUsageService.totals(rows)
    rate_cents, currency, _, _ = await service.get_config(current_user.facility_id)
    return UsageRangeResponse(
        start_date=start,
        end_date=end,
        currency=rows[0].currency if rows else currency,
        rate_cents=rows[0].rate_cents if rows else rate_cents,
        total_patient_days=int(agg["total_patient_days"]),
        registration_patient_days=int(agg["registration_patient_days"]),
        emergency_patient_days=int(agg["emergency_patient_days"]),
        inpatient_patient_days=int(agg["inpatient_patient_days"]),
        total_amount_cents=int(agg["total_amount_cents"]),
        days=[_to_day(row) for row in rows],
    )


@router.get("/summary", response_model=UsageMonthResponse)
async def get_usage_summary(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_VIEW)),
) -> UsageMonthResponse:
    """
    The hospital's Aifya bill for one calendar month.

    A month still open is metered live, so the figure is current without an
    accrual being run first. A finalized month is read from the frozen ledger,
    so the figure its invoice was raised on cannot drift. This is the same
    figure the Reports usage calculator shows.

    @param year: Calendar year
    @param month: Calendar month, 1-12
    @param db: Database session
    @param current_user: Authenticated user holding hr.view
    @returns The month's usage, and its invoice when one has been raised
    """
    service = AifyaUsageService(db)
    return await _month_payload(
        db, service, current_user.facility_id, year, month
    )


@router.post("/finalize", response_model=UsageMonthResponse)
async def finalize_usage_month(
    data: UsageFinalizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
) -> UsageMonthResponse:
    """
    Close a month and raise the draft invoice for it.

    Once closed, ``POST /accrue`` will not recompute these days unless it is
    called with ``force``. The draft invoice is refreshed if it already exists;
    an invoice that has been issued is left untouched.

    @param data: Month to close
    @param db: Database session
    @param current_user: Authenticated administrator or HR administrator
    @returns The closed month, with its draft invoice
    """
    service = AifyaUsageService(db)
    start_date, end_date = month_bounds(data.year, data.month)
    if end_date > datetime.now(UTC).date():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This month is not finished yet.",
        )
    # Meter the month first, so closing one that was never accrued still
    # freezes the days its invoice will be raised on.
    await service.recompute_range(
        current_user.facility_id,
        start_date,
        end_date,
        actor_id=current_user.user_id,
    )
    await service.finalize_month(
        current_user.facility_id,
        data.year,
        data.month,
        actor_id=current_user.user_id,
    )
    try:
        await service.generate_invoice(
            current_user.facility_id,
            data.year,
            data.month,
            actor_id=current_user.user_id,
        )
    except ValueError:
        # A month with no usage has nothing to invoice. Closing it is still a
        # legitimate act, so the absence of an invoice must not fail the call.
        pass
    return await _month_payload(
        db, service, current_user.facility_id, data.year, data.month
    )


# ── Invoices ────────────────────────────────────────────────────────────────


@router.get("/invoices", response_model=list[UsageInvoiceResponse])
async def list_usage_invoices(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_VIEW)),
) -> list[UsageInvoiceResponse]:
    """
    Every Aifya invoice raised for this hospital, newest first.

    @param db: Database session
    @param current_user: Authenticated user holding hr.view
    @returns Invoice list
    """
    service = AifyaUsageService(db)
    rows = await service.list_invoices(current_user.facility_id)
    return [_to_invoice(row) for row in rows]


@router.post(
    "/invoices",
    response_model=UsageInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_usage_invoice(
    data: UsageInvoiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_MANAGE)),
) -> UsageInvoiceResponse:
    """
    Raise, or refresh, the invoice for a calendar month.

    Idempotent while the invoice is a draft. Once issued it is returned
    unchanged, because by then it is a statement of what was billed.

    @param data: Month to invoice
    @param db: Database session
    @param current_user: Authenticated user holding hr.manage
    @returns The invoice
    """
    service = AifyaUsageService(db)
    try:
        invoice = await service.generate_invoice(
            current_user.facility_id,
            data.year,
            data.month,
            notes=data.notes,
            actor_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    return _to_invoice(invoice)


@router.get("/invoices/{invoice_id}", response_model=UsageInvoiceResponse)
async def get_usage_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_VIEW)),
) -> UsageInvoiceResponse:
    """
    One invoice, with its outstanding balance.

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated user holding hr.view
    @returns The invoice
    """
    service = AifyaUsageService(db)
    invoice = await service.get_invoice(current_user.facility_id, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return _to_invoice(invoice)


@router.post("/invoices/{invoice_id}/issue", response_model=UsageInvoiceResponse)
async def issue_usage_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_MANAGE)),
) -> UsageInvoiceResponse:
    """
    Issue a draft invoice and start its payment term.

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated user holding hr.manage
    @returns The issued invoice
    """
    service = AifyaUsageService(db)
    invoice = await service.issue_invoice(
        current_user.facility_id, invoice_id, actor_id=current_user.user_id
    )
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return _to_invoice(invoice)


@router.post(
    "/invoices/{invoice_id}/payment", response_model=UsageInvoiceResponse
)
async def pay_usage_invoice(
    invoice_id: uuid.UUID,
    data: UsageInvoicePayment,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission(Permission.HR_MANAGE)),
) -> UsageInvoiceResponse:
    """
    Record money received against an issued invoice.

    The invoice only reads ``paid`` once the payments cover it in full; a
    partial settlement leaves it outstanding with a visible balance.

    @param invoice_id: Invoice UUID
    @param data: Amount received and its reference
    @param db: Database session
    @param current_user: Authenticated user holding hr.manage
    @returns The updated invoice
    """
    service = AifyaUsageService(db)
    try:
        invoice = await service.record_invoice_payment(
            current_user.facility_id,
            invoice_id,
            amount_cents=data.amount_cents,
            reference=data.reference,
            actor_id=current_user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return _to_invoice(invoice)


@router.post("/invoices/{invoice_id}/void", response_model=UsageInvoiceResponse)
async def void_usage_invoice(
    invoice_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(*ADMIN_ROLES)),
) -> UsageInvoiceResponse:
    """
    Cancel an invoice that has taken no money.

    A voided invoice does not block a replacement for the same month.

    @param invoice_id: Invoice UUID
    @param db: Database session
    @param current_user: Authenticated administrator
    @returns The voided invoice
    """
    service = AifyaUsageService(db)
    try:
        invoice = await service.void_invoice(
            current_user.facility_id, invoice_id, actor_id=current_user.user_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found"
        )
    return _to_invoice(invoice)
