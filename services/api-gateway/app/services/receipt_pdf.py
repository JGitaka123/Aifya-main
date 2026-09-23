"""
Server-side receipt/invoice PDF rendering (A4, ReportLab).

Per CLAUDE.md printing rules: facility name in the header, QR code on the
document, "Powered by Aifya" in the footer only.
"""

import uuid
from datetime import datetime
from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _kes(cents: int) -> str:
    """Format integer KES cents for print.

    @param cents: Amount in KES cents
    @returns Formatted amount, e.g. "KES 1,234.50"
    """
    return f"KES {cents / 100:,.2f}"


def render_receipt_pdf(
    facility_name: str,
    invoice: dict,
    items: list[dict],
    payments: list[dict],
    patient_name: str | None,
    patient_mrn: str | None,
    title: str = "OFFICIAL RECEIPT",
) -> bytes:
    """
    Render an A4 receipt for an invoice with its payments.

    @param facility_name: Facility display name for the header
    @param invoice: Invoice fields (invoice_number, status, totals, created_at)
    @param items: Line items (description, quantity, unit_price_cents, total_cents)
    @param payments: Payments (paid_at, payment_method, reference_number, amount_cents)
    @param patient_name: Patient display name
    @param patient_mrn: Patient MRN
    @param title: Document heading (invoice receipt vs service receipt)
    @returns PDF bytes
    """
    buf = BytesIO()
    page_w, page_h = A4
    pdf = canvas.Canvas(buf, pagesize=A4)
    margin = 20 * mm
    y = page_h - margin

    # Header
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(margin, y, facility_name)
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawRightString(page_w - margin, y, title)
    y -= 8 * mm
    pdf.setFont("Helvetica", 9)
    pdf.drawString(margin, y, f"Receipt for invoice {invoice['invoice_number']}")
    pdf.drawRightString(
        page_w - margin,
        y,
        datetime.now().strftime("Printed %Y-%m-%d %H:%M"),
    )
    y -= 4 * mm
    pdf.line(margin, y, page_w - margin, y)
    y -= 8 * mm

    # Patient / invoice block
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, y, f"Patient: {patient_name or '—'}")
    pdf.drawRightString(page_w - margin, y, f"MRN: {patient_mrn or '—'}")
    y -= 5 * mm
    pdf.drawString(margin, y, f"Invoice status: {invoice['status']}")
    y -= 10 * mm

    # Items table
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(margin, y, "Description")
    pdf.drawRightString(page_w - margin - 60 * mm, y, "Qty")
    pdf.drawRightString(page_w - margin - 30 * mm, y, "Unit")
    pdf.drawRightString(page_w - margin, y, "Total")
    y -= 2 * mm
    pdf.line(margin, y, page_w - margin, y)
    y -= 5 * mm
    pdf.setFont("Helvetica", 9)
    for item in items:
        pdf.drawString(margin, y, str(item["description"])[:70])
        pdf.drawRightString(page_w - margin - 60 * mm, y, str(item["quantity"]))
        pdf.drawRightString(
            page_w - margin - 30 * mm, y, _kes(item["unit_price_cents"])
        )
        pdf.drawRightString(page_w - margin, y, _kes(item["total_cents"]))
        y -= 5 * mm
        if y < 60 * mm:
            pdf.showPage()
            y = page_h - margin
            pdf.setFont("Helvetica", 9)

    y -= 2 * mm
    pdf.line(margin, y, page_w - margin, y)
    y -= 6 * mm

    # Totals
    pdf.setFont("Helvetica-Bold", 10)
    for label, cents in (
        ("Subtotal", invoice["subtotal_cents"]),
        ("Discount", invoice["discount_cents"]),
        ("Total", invoice["total_cents"]),
        ("Paid", invoice["paid_cents"]),
        ("Balance", invoice["balance_cents"]),
    ):
        pdf.drawRightString(page_w - margin - 30 * mm, y, label)
        pdf.drawRightString(page_w - margin, y, _kes(cents))
        y -= 5 * mm

    # Payments
    if payments:
        y -= 5 * mm
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(margin, y, "Payments")
        y -= 5 * mm
        pdf.setFont("Helvetica", 9)
        for p in payments:
            ref = p.get("reference_number") or "—"
            pdf.drawString(
                margin, y, f"{p['paid_at']}  {p['payment_method']}  ref {ref}"
            )
            pdf.drawRightString(page_w - margin, y, _kes(p["amount_cents"]))
            y -= 5 * mm

    # QR code: invoice number + id for verification at the desk
    qr_code = qr.QrCodeWidget(f"AIFYA:{invoice['invoice_number']}:{invoice['id']}")
    bounds = qr_code.getBounds()
    size = 25 * mm
    drawing = Drawing(
        size,
        size,
        transform=[
            size / (bounds[2] - bounds[0]), 0, 0,
            size / (bounds[3] - bounds[1]), 0, 0,
        ],
    )
    drawing.add(qr_code)
    renderPDF.draw(drawing, pdf, margin, 25 * mm)

    # Footer
    pdf.setFont("Helvetica", 7)
    pdf.drawCentredString(page_w / 2, 15 * mm, "Powered by Aifya")

    pdf.showPage()
    pdf.save()
    return buf.getvalue()


def receipt_filename(invoice_number: str) -> str:
    """Build a safe download filename for a receipt.

    @param invoice_number: Invoice number
    @returns Filename like receipt-INV-20260707-0001.pdf
    """
    safe = "".join(c for c in invoice_number if c.isalnum() or c in "-_")
    return f"receipt-{safe or uuid.uuid4().hex}.pdf"
