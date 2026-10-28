"""GST tax invoice PDF for a paid platform invoice (reportlab, the font the certificates use)."""
import io

from django.conf import settings
from django.utils import timezone
from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from certificates.pdf import FONT, FONT_BOLD, _ensure_fonts
from payroll.pdf import _Text, money

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
GREY = HexColor("#64748b")
RULE = HexColor("#cbd5e1")
CYCLE = {"monthly": "Monthly", "yearly": "Yearly", "one_time": "One-time"}


def _date(value):
    return timezone.localtime(value).strftime("%d %b %Y") if value else "-"


def render_invoice_pdf(invoice):
    _ensure_fonts()
    text = _Text()
    seller = getattr(settings, "PLATFORM_LEGAL_NAME", "") or getattr(settings, "PLATFORM_NAME", "EduSekai")
    gstin = getattr(settings, "PLATFORM_GSTIN", "")
    address = getattr(settings, "PLATFORM_ADDRESS", "")
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Invoice {invoice.number}")

    y = PAGE_H - MARGIN
    c.setFont(FONT_BOLD, 18)
    c.drawString(MARGIN, y, "Tax Invoice" if gstin else "Invoice")
    c.setFont(FONT, 10)
    c.drawRightString(PAGE_W - MARGIN, y, f"No. {invoice.number}")
    y -= 6 * mm
    c.setFillColor(GREY)
    c.drawRightString(PAGE_W - MARGIN, y, f"Date {_date(invoice.paid_at)}")

    y -= 12 * mm
    c.setFillColor(black)
    c.setFont(FONT_BOLD, 11)
    c.drawString(MARGIN, y, "From")
    c.drawString(PAGE_W / 2, y, "Billed to")
    c.setFont(FONT, 10)
    left = [seller] + [line for line in address.splitlines() if line] + ([f"GSTIN {gstin}"] if gstin else [])
    right = [invoice.billed_name] + [line for line in invoice.billed_address.splitlines() if line]
    right += [invoice.billed_email] if invoice.billed_email else []
    right += [f"GSTIN {invoice.billed_gstin}"] if invoice.billed_gstin else []
    for i in range(max(len(left), len(right))):
        y -= 5.5 * mm
        if i < len(left):
            c.drawString(MARGIN, y, text.clean(left[i])[:60])
        if i < len(right):
            c.drawString(PAGE_W / 2, y, text.clean(right[i])[:60])

    y -= 14 * mm
    c.setStrokeColor(RULE)
    c.line(MARGIN, y + 4 * mm, PAGE_W - MARGIN, y + 4 * mm)
    c.setFont(FONT_BOLD, 10)
    c.drawString(MARGIN, y, "Description")
    c.drawRightString(PAGE_W - MARGIN, y, "Amount (INR)")
    c.line(MARGIN, y - 2.5 * mm, PAGE_W - MARGIN, y - 2.5 * mm)
    c.setFont(FONT, 10)
    period = f"{_date(invoice.period_start)} to {_date(invoice.period_end)}" if invoice.period_end else f"from {_date(invoice.period_start)}, no end date"
    y -= 9 * mm
    c.drawString(MARGIN, y, text.clean(f"EduSekai {invoice.plan_name} plan ({CYCLE.get(invoice.cycle, invoice.cycle)})")[:80])
    c.drawRightString(PAGE_W - MARGIN, y, money(invoice.amount))
    y -= 5.5 * mm
    c.setFillColor(GREY)
    c.drawString(MARGIN, y, f"Service period: {period}")
    c.drawString(MARGIN, y - 5.5 * mm, "SAC 998431 - online software / SaaS")
    c.setFillColor(black)

    if invoice.place_of_supply:
        from .gst import STATES

        y -= 11 * mm
        c.drawString(MARGIN, y, f"Place of supply: {STATES.get(invoice.place_of_supply, '')} ({invoice.place_of_supply})")
        c.setFillColor(black)
    y -= 16 * mm
    half = invoice.gst_percent / 2
    if invoice.igst_amount:
        tax_rows = [(f"IGST @ {invoice.gst_percent:g}%", invoice.igst_amount)]
    elif invoice.cgst_amount or invoice.sgst_amount:
        tax_rows = [(f"CGST @ {half:g}%", invoice.cgst_amount), (f"SGST @ {half:g}%", invoice.sgst_amount)]
    else:
        tax_rows = [(f"GST @ {invoice.gst_percent:g}%", invoice.gst_amount)]
    rows = [("Taxable value", money(invoice.amount))] + [(label, money(value)) for label, value in tax_rows]
    rows.append(("Total paid", money(invoice.total)))
    for label, value in rows:
        c.setFont(FONT_BOLD if label == "Total paid" else FONT, 11 if label == "Total paid" else 10)
        c.drawRightString(PAGE_W - MARGIN - 45 * mm, y, label)
        c.drawRightString(PAGE_W - MARGIN, y, value)
        y -= 7 * mm

    c.setFont(FONT, 9)
    c.setFillColor(GREY)
    c.drawString(MARGIN, y - 6 * mm, f"Paid online. Payment reference {invoice.razorpay_payment_id or '-'}.")
    footer = "This is a computer-generated invoice and needs no signature."
    if text.altered:
        footer += " Characters the font cannot show are printed as '?'."
    c.drawString(MARGIN, MARGIN, footer)
    c.showPage()
    c.save()
    return buffer.getvalue()
