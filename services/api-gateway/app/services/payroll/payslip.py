"""Per-employee payslip PDF generator.

Uses ReportLab if available; falls back to a minimal text-based stub
(returned as bytes) so the rest of the system still functions.

NOTE: payslips MUST NOT be generated for runs in `draft` status.
"""

from __future__ import annotations

import io
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import Employee, PayrollLineItem, PayrollRun

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


class PayslipNotAvailableError(Exception):
    """Raised when a payslip is requested for a draft / missing run."""


async def _load_payslip_data(
    db: AsyncSession,
    facility_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    employee_id: uuid.UUID,
) -> tuple[PayrollRun, PayrollLineItem, Employee]:
    """Fetch run + line + employee. Raises if missing or run is draft."""
    run = (
        await db.execute(
            select(PayrollRun).where(
                PayrollRun.id == payroll_run_id,
                PayrollRun.facility_id == facility_id,
                PayrollRun.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if run is None:
        raise PayslipNotAvailableError("Payroll run not found")
    if run.status == "draft":
        raise PayslipNotAvailableError(
            "Cannot generate payslip for a draft payroll run"
        )

    line = (
        await db.execute(
            select(PayrollLineItem).where(
                PayrollLineItem.payroll_run_id == payroll_run_id,
                PayrollLineItem.employee_id == employee_id,
                PayrollLineItem.facility_id == facility_id,
                PayrollLineItem.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if line is None:
        raise PayslipNotAvailableError("No payslip line for this employee")

    emp = (
        await db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.facility_id == facility_id,
                Employee.is_deleted.is_(False),
            )
        )
    ).scalars().first()
    if emp is None:
        raise PayslipNotAvailableError("Employee not found")

    return run, line, emp


def _format_money(value: Decimal | None) -> str:
    """Format Decimal as KES with thousand separators."""
    if value is None:
        return "0.00"
    return f"{Decimal(value):,.2f}"


def _mask_account(account: str | None) -> str:
    """
    Mask a bank account for payslip display — last four digits only.

    @param account: Decrypted account number (or None)
    @returns Masked account, e.g. "••••1234", or "-" when absent
    """
    if not account:
        return "-"
    tail = account[-4:]
    return f"{'•' * max(len(account) - 4, 0)}{tail}"


def _build_text_fallback(
    facility_name: str,
    run: PayrollRun,
    line: PayrollLineItem,
    emp: Employee,
) -> bytes:
    """Plain-text fallback when ReportLab is unavailable."""
    period = f"{_MONTHS[run.month - 1]} {run.year}"
    other_alw = "\n".join(
        f"  - {k}: {v}" for k, v in (line.other_allowances or {}).items()
    ) or "  (none)"
    other_ded = "\n".join(
        f"  - {k}: {v}" for k, v in (line.other_deductions or {}).items()
    ) or "  (none)"
    body = f"""
{facility_name}
PAYSLIP — {period}

Employee: {emp.full_name}
Staff ID: {emp.staff_id}
KRA PIN:  {emp.kra_pin or '-'}
NSSF #:   {emp.nssf_number or '-'}
SHIF #:   {emp.shif_number or '-'}
Bank:     {emp.bank_name or '-'} / {emp.bank_branch or '-'}

EARNINGS
  Basic Salary:        {_format_money(line.basic_salary)}
  House Allowance:     {_format_money(line.house_allowance)}
  Transport Allowance: {_format_money(line.transport_allowance)}
  Other Allowances:
{other_alw}
  ----------------------------------
  Gross Salary:        {_format_money(line.gross_salary)}

STATUTORY DEDUCTIONS
  PAYE:                {_format_money(line.paye)}
  NSSF (employee):     {_format_money(line.nssf_employee)}
  SHIF:                {_format_money(line.shif)}
  Housing Levy:        {_format_money(line.housing_levy)}

OTHER DEDUCTIONS
{other_ded}

  Total Deductions:    {_format_money(line.total_deductions)}

  *** NET SALARY:      {_format_money(line.net_salary)} ***
  *** NET SALARY:      {_format_money(line.net_salary)} ***

Generated: {datetime.now(UTC).isoformat(timespec='seconds')}
Powered by Aifya
""".strip()
    return body.encode("utf-8")


def _build_pdf(
    facility_name: str,
    run: PayrollRun,
    line: PayrollLineItem,
    emp: Employee,
) -> bytes:
    """Build a polished PDF payslip via ReportLab. Raises ImportError
    if reportlab is missing — caller handles fallback."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Payslip {run.year}-{run.month:02d}",
    )
    styles = getSampleStyleSheet()
    story: list = []

    # Header
    period = f"{_MONTHS[run.month - 1]} {run.year}"
    story.append(Paragraph(f"<b>{facility_name}</b>", styles["Title"]))
    story.append(Paragraph(f"<b>PAYSLIP — {period}</b>", styles["Heading2"]))
    story.append(Spacer(1, 6))

    # Employee block
    emp_data = [
        ["Employee", emp.full_name, "Staff ID", emp.staff_id],
        ["KRA PIN", emp.kra_pin or "-", "ID Number", emp.id_number or "-"],
        ["NSSF #", emp.nssf_number or "-", "SHIF #", emp.shif_number or "-"],
        [
            "Bank",
            f"{emp.bank_name or '-'} / {emp.bank_branch or '-'}",
            "Account",
            _mask_account(emp.bank_account),
        ],
    ]
    t_emp = Table(emp_data, colWidths=[28 * mm, 60 * mm, 25 * mm, 60 * mm])
    t_emp.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                ("BACKGROUND", (2, 0), (2, -1), colors.lightgrey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(t_emp)
    story.append(Spacer(1, 8))

    # Earnings
    earn_rows: list[list[str]] = [["EARNINGS", "KES"]]
    earn_rows.append(["Basic Salary", _format_money(line.basic_salary)])
    earn_rows.append(["House Allowance", _format_money(line.house_allowance)])
    earn_rows.append(["Transport Allowance", _format_money(line.transport_allowance)])
    for k, v in (line.other_allowances or {}).items():
        earn_rows.append([f"Other: {k}", _format_money(Decimal(str(v)))])
    earn_rows.append(["Gross Salary", _format_money(line.gross_salary)])
    t_earn = Table(earn_rows, colWidths=[120 * mm, 50 * mm])
    t_earn.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkblue),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(t_earn)
    story.append(Spacer(1, 8))

    # Statutory deductions
    stat_rows = [
        ["STATUTORY DEDUCTIONS", "KES"],
        [f"PAYE (KRA PIN: {emp.kra_pin or '-'})", _format_money(line.paye)],
        [f"NSSF (No: {emp.nssf_number or '-'})", _format_money(line.nssf_employee)],
        [f"SHIF (No: {emp.shif_number or '-'})", _format_money(line.shif)],
        ["Housing Levy", _format_money(line.housing_levy)],
    ]
    t_stat = Table(stat_rows, colWidths=[120 * mm, 50 * mm])
    t_stat.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.darkred),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(t_stat)
    story.append(Spacer(1, 8))

    # Other deductions
    if line.other_deductions:
        other_rows = [["OTHER DEDUCTIONS", "KES"]]
        for k, v in line.other_deductions.items():
            other_rows.append([k, _format_money(Decimal(str(v)))])
        t_other = Table(other_rows, colWidths=[120 * mm, 50 * mm])
        t_other.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(t_other)
        story.append(Spacer(1, 8))

    # Totals + NET (shown twice)
    totals = [
        ["Total Deductions", _format_money(line.total_deductions)],
        ["NET SALARY", _format_money(line.net_salary)],
        ["NET SALARY", _format_money(line.net_salary)],
    ]
    t_totals = Table(totals, colWidths=[120 * mm, 50 * mm])
    t_totals.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                ("BACKGROUND", (0, 1), (-1, 2), colors.darkgreen),
                ("TEXTCOLOR", (0, 1), (-1, 2), colors.white),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.black),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.black),
                ("FONTSIZE", (0, 0), (-1, -1), 11),
            ]
        )
    )
    story.append(t_totals)
    story.append(Spacer(1, 12))

    story.append(
        Paragraph(
            f"<font size=8>Generated {datetime.now(UTC).isoformat(timespec='seconds')} "
            "&nbsp;&nbsp;|&nbsp;&nbsp; Powered by Aifya</font>",
            styles["Normal"],
        )
    )

    doc.build(story)
    return buf.getvalue()


async def generate_payslip(
    db: AsyncSession,
    facility_id: uuid.UUID,
    payroll_run_id: uuid.UUID,
    employee_id: uuid.UUID,
    facility_name: str = "Aifya Health Facility",
) -> bytes:
    """Generate the payslip bytes (PDF if reportlab is installed, else text).

    @param db: Async session
    @param facility_id: Tenant facility
    @param payroll_run_id: Payroll run UUID (must not be `draft`)
    @param employee_id: Employee UUID
    @param facility_name: Facility name shown in header
    @returns Raw bytes (PDF or text/plain)
    @raises PayslipNotAvailableError if run is draft / missing
    """
    run, line, emp = await _load_payslip_data(
        db=db,
        facility_id=facility_id,
        payroll_run_id=payroll_run_id,
        employee_id=employee_id,
    )

    try:
        return _build_pdf(facility_name, run, line, emp)
    except ImportError:
        return _build_text_fallback(facility_name, run, line, emp)
