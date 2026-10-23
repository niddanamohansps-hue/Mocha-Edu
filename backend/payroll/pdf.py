"""Payslip PDF (reportlab, the same bundled Latin font the certificates use).

The font has no Devanagari or other non-Latin glyphs. Rather than print blanks, anything it cannot draw
is replaced by "?" and the payslip says so in its footer, so nobody mistakes a gap for missing data.
"""
import io

from reportlab.lib.colors import HexColor, black
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from certificates.pdf import FONT, FONT_BOLD, _ensure_fonts, unsupported_characters

MONTH_NAMES = ["", "January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]
PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
GREY = HexColor("#64748b")
RULE = HexColor("#cbd5e1")
BAND = HexColor("#f1f5f9")


def money(value):
    """12345.5 -> '12,345.50' (grouped in thousands, always two decimals)."""
    return f"{value:,.2f}"


class _Text:
    """Collects whether any text had to be altered, so the footer can say so."""

    def __init__(self):
        self.altered = False

    def clean(self, value):
        value = str(value or "")
        bad = set(unsupported_characters(value))
        if not bad:
            return value
        self.altered = True
        return "".join("?" if ch in bad else ch for ch in value)


def render_payslip_pdf(payslip, lines, *, school_name):
    """Return the PDF bytes of one payslip. ``lines`` are the payslip's PayslipLine rows in order."""
    _ensure_fonts()
    text = _Text()
    run = payslip.run
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f"Payslip {payslip.employee_id} {MONTH_NAMES[run.month]} {run.year}")
    c.setAuthor(text.clean(school_name))

    y = PAGE_H - MARGIN
    c.setFont(FONT_BOLD, 17)
    c.setFillColor(black)
    c.drawString(MARGIN, y, text.clean(school_name)[:70])
    y -= 8 * mm
    c.setFont(FONT, 11)
    c.setFillColor(GREY)
    c.drawString(MARGIN, y, f"Payslip for {MONTH_NAMES[run.month]} {run.year}")
    y -= 4 * mm
    c.setStrokeColor(RULE)
    c.line(MARGIN, y, PAGE_W - MARGIN, y)
    y -= 9 * mm

    def pair(label, value, x, y_):
        c.setFont(FONT, 9)
        c.setFillColor(GREY)
        c.drawString(x, y_, label)
        c.setFont(FONT_BOLD, 11)
        c.setFillColor(black)
        c.drawString(x, y_ - 5 * mm, text.clean(value)[:38] or "-")

    mid = PAGE_W / 2
    pair("Employee", payslip.staff_name, MARGIN, y)
    pair("Employee ID", payslip.employee_id, mid, y)
    y -= 13 * mm
    pair("Designation", payslip.designation, MARGIN, y)
    pair("Department", payslip.department, mid, y)
    y -= 13 * mm
    pair("Working days in the month", str(payslip.working_days), MARGIN, y)
    unpaid = payslip.unpaid_days.normalize()
    pair("Unpaid days", f"{unpaid:f}", mid, y)
    y -= 14 * mm

    def section(title, rows, y_):
        c.setFillColor(BAND)
        c.rect(MARGIN, y_ - 2 * mm, PAGE_W - 2 * MARGIN, 7 * mm, stroke=0, fill=1)
        c.setFillColor(black)
        c.setFont(FONT_BOLD, 10)
        c.drawString(MARGIN + 2 * mm, y_, title)
        y_ -= 8 * mm
        for name, detail, amount in rows:
            c.setFont(FONT, 10)
            c.drawString(MARGIN + 2 * mm, y_, text.clean(name)[:46])
            if detail:
                c.setFont(FONT, 8)
                c.setFillColor(GREY)
                c.drawString(MARGIN + 2 * mm, y_ - 3.6 * mm, text.clean(detail)[:80])
                c.setFillColor(black)
                y_ -= 3.6 * mm
            c.setFont(FONT, 10)
            c.drawRightString(PAGE_W - MARGIN - 2 * mm, y_, money(amount))
            y_ -= 6 * mm
        return y_

    earnings = [(l.name, l.detail if l.kind != "basic" else "", l.amount) for l in lines if l.kind in ("basic", "earning")]
    deductions = [(l.name, l.detail, l.amount) for l in lines if l.kind == "deduction"]
    y = section("Earnings", earnings, y)
    c.setFont(FONT_BOLD, 10)
    c.drawString(MARGIN + 2 * mm, y, "Total earnings")
    c.drawRightString(PAGE_W - MARGIN - 2 * mm, y, money(payslip.gross_amount))
    y -= 11 * mm
    y = section("Deductions", deductions or [("None", "", payslip.deductions_amount)], y)
    c.setFont(FONT_BOLD, 10)
    c.drawString(MARGIN + 2 * mm, y, "Total deductions")
    c.drawRightString(PAGE_W - MARGIN - 2 * mm, y, money(payslip.deductions_amount))
    y -= 14 * mm

    c.setFillColor(HexColor("#0f172a"))
    c.rect(MARGIN, y - 3 * mm, PAGE_W - 2 * MARGIN, 11 * mm, stroke=0, fill=1)
    c.setFillColor(HexColor("#ffffff"))
    c.setFont(FONT_BOLD, 12)
    c.drawString(MARGIN + 3 * mm, y + 0.5 * mm, "Net pay (NPR)")
    c.drawRightString(PAGE_W - MARGIN - 3 * mm, y + 0.5 * mm, money(payslip.net_amount))

    c.setFillColor(GREY)
    c.setFont(FONT, 8)
    footer = "This payslip was produced by the school's payroll system and needs no signature."
    if run.status == "paid" and run.paid_on:
        footer += f" Paid on {run.paid_on.day} {MONTH_NAMES[run.paid_on.month]} {run.paid_on.year}."
    c.drawString(MARGIN, MARGIN, footer)
    if text.altered:
        c.drawString(MARGIN, MARGIN - 4 * mm, "Some characters could not be printed in this PDF and appear as '?'.")
    c.showPage()
    c.save()
    return buffer.getvalue()
