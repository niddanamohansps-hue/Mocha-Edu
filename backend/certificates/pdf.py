"""PDF rendering for certificates and ID cards (reportlab) and QR codes (segno).

Fonts: reportlab's bundled Bitstream Vera (Latin, Latin-1/Extended, common
punctuation). It has no Devanagari or other non-Latin glyphs. Rather than
print blanks, text that the font cannot draw is rejected at issue time via
unsupported_characters(). Supporting more scripts needs a licensed font file
to be shipped with the project (a product decision, see the report).
"""

import io
import os

import reportlab
import segno
from PIL import Image
from reportlab.lib.colors import Color, black, HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .models import Certificate

_FONT_DIR = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
FONT = "EduVera"
FONT_BOLD = "EduVera-Bold"
_registered = False


def _ensure_fonts():
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont(FONT, os.path.join(_FONT_DIR, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, os.path.join(_FONT_DIR, "VeraBd.ttf")))
        _registered = True


def unsupported_characters(text):
    """Characters in `text` that the PDF font cannot draw (empty if all fine)."""
    _ensure_fonts()
    glyphs = pdfmetrics.getFont(FONT).face.charToGlyph
    return sorted({ch for ch in str(text) if ch not in "\n\t" and ord(ch) not in glyphs})


# --- helpers -----------------------------------------------------------------------

def load_image(field):
    """ImageReader for an ImageField file, or None when absent/missing/corrupt."""
    try:
        if not field or not field.name:
            return None
        with field.open("rb") as fh:
            data = fh.read()
        Image.open(io.BytesIO(data)).verify()
        return ImageReader(io.BytesIO(data))
    except Exception:
        return None


def qr_png_bytes(payload, scale=6):
    buf = io.BytesIO()
    segno.make(payload, error="m", micro=False).save(buf, kind="png", scale=scale, border=2)
    return buf.getvalue()


def qr_svg_data_uri(payload):
    return segno.make(payload, error="m", micro=False).svg_data_uri(scale=4, border=2)


def _draw_qr(c, payload, x, y, size):
    """Vector QR (crisp at any print size)."""
    qr = segno.make(payload, error="m", micro=False)
    matrix = [list(row) for row in qr.matrix]
    n = len(matrix)
    border = 2
    cell = size / (n + 2 * border)
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(x, y, size, size, stroke=0, fill=1)
    c.setFillColor(black)
    for r, row in enumerate(matrix):
        for col, dark in enumerate(row):
            if dark:
                c.rect(x + (col + border) * cell, y + size - (r + border + 1) * cell, cell, cell, stroke=0, fill=1)


def _fmt_date(value):
    if not value:
        return ""
    if isinstance(value, str):
        import datetime

        value = datetime.date.fromisoformat(value)
    return f"{value.day} {value.strftime('%B %Y')}"


def _clean(text):
    """Trailing punctuation is stripped so templates that add their own full
    stop never print a doubled one ("returned. .")."""
    return str(text or "").strip().rstrip(".,;: ").strip()


def fit_lines(text, font, max_width, max_lines, size, min_size):
    """Wraps `text` and shrinks the font until it fits in `max_lines`, never
    dropping words. Only if it still does not fit at `min_size` is the last
    line ellipsized, so nothing is silently cut off. Returns (lines, size)."""
    text = str(text or "")
    while True:
        lines = simpleSplit(text, font, size, max_width)
        if len(lines) <= max_lines:
            return lines, size
        if size - 0.5 >= min_size:
            size -= 0.5
            continue
        lines = lines[:max_lines]
        last = lines[-1]
        while last and pdfmetrics.stringWidth(last + "...", font, size) > max_width:
            last = last[:-1]
        lines[-1] = last.rstrip() + "..."
        return lines, size


def _wrapped(c, text, x, y, width, font=FONT, size=12, leading=19):
    lines = simpleSplit(text, font, size, width)
    c.setFont(font, size)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


# --- certificate -----------------------------------------------------------------------

def certificate_body(cert):
    s = cert.snapshot
    name = s.get("holder_name", "")
    t = cert.certificate_type
    klass = " ".join(p for p in (s.get("level_name"), s.get("section_name")) if p)
    year = s.get("academic_year", "")
    where = f" in {klass}" if klass else ""
    if t == Certificate.Type.TRANSFER:
        parts = [
            f"This is to certify that {name} (Admission No. {s.get('enrollment_id', '')})"
            + (f", born on {_fmt_date(s['date_of_birth'])}," if s.get("date_of_birth") else "")
            + f" was a student of this school{where} during the academic year {year}.",
            f"The student left the school on {_fmt_date(s.get('leaving_date'))}.",
            f"Reason for leaving: {_clean(s.get('reason'))}.",
        ]
        if _clean(s.get("conduct")):
            parts.append(f"Conduct and character: {_clean(s.get('conduct'))}.")
        parts.append("This Transfer Certificate is issued on request for admission elsewhere.")
        return parts
    if t == Certificate.Type.BONAFIDE:
        parts = [
            f"This is to certify that {name} (Admission No. {s.get('enrollment_id', '')}) is a bonafide "
            f"student of this school{', studying in ' + klass if klass else ''} during the academic year {year}."
        ]
        if _clean(s.get("purpose")):
            parts.append(f"This certificate is issued for the purpose of: {_clean(s.get('purpose'))}.")
        return parts
    if t == Certificate.Type.CHARACTER:
        return [
            f"This is to certify that {name} (Admission No. {s.get('enrollment_id', '')}) studied in this "
            f"school{where} during the academic year {year}.",
            f"During this period the student's conduct and character have been {_clean(s.get('conduct'))}.",
        ]
    dept = f" in the {s['department']} department" if s.get("department") else ""
    parts = [
        f"This is to certify that {name} (Employee ID {s.get('employee_id', '')}) worked at this school as "
        f"{s.get('designation', '')}{dept} from {_fmt_date(s.get('period_start'))} to {_fmt_date(s.get('period_end'))}."
    ]
    if _clean(s.get("conduct")):
        parts.append(f"Conduct and performance: {_clean(s.get('conduct'))}.")
    return parts


def render_certificate_pdf(cert, verify_url, institution_logo=None, signature=None, signatory_name="", signatory_title=""):
    """Returns PDF bytes. Only fields from cert.snapshot / public-safe columns
    are drawn - never internal_notes, ids of people, or filesystem paths."""
    _ensure_fonts()
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"{cert.get_certificate_type_display()} {cert.certificate_number}")
    c.setAuthor(cert.snapshot.get("school_name", ""))
    c.setCreator("EduSekai")
    width, height = A4
    margin = 18 * mm

    c.setStrokeColor(HexColor("#0369A1"))
    c.setLineWidth(2)
    c.rect(margin / 2, margin / 2, width - margin, height - margin)
    c.setLineWidth(0.5)
    c.rect(margin / 2 + 2.5 * mm, margin / 2 + 2.5 * mm, width - margin - 5 * mm, height - margin - 5 * mm)

    y = height - margin - 8 * mm
    if institution_logo is not None:
        c.drawImage(institution_logo, width / 2 - 14 * mm, y - 28 * mm, 28 * mm, 28 * mm, preserveAspectRatio=True, mask="auto")
        y -= 33 * mm
    c.setFillColor(black)
    name_lines, name_size = fit_lines(
        cert.snapshot.get("school_name", ""), FONT_BOLD, width - 2 * margin - 12 * mm, 3, 20, 13
    )
    c.setFont(FONT_BOLD, name_size)
    line_gap = name_size * 1.25
    for i, line in enumerate(name_lines):
        c.drawCentredString(width / 2, y - 6 * mm - i * line_gap, line)
    y -= 22 * mm + (len(name_lines) - 1) * line_gap
    c.setFont(FONT_BOLD, 17)
    c.drawCentredString(width / 2, y, cert.get_certificate_type_display().upper())
    c.setLineWidth(0.8)
    c.line(width / 2 - 45 * mm, y - 3 * mm, width / 2 + 45 * mm, y - 3 * mm)
    y -= 16 * mm

    c.setFont(FONT, 10)
    c.drawString(margin + 4 * mm, y, f"Certificate No.: {cert.certificate_number}")
    c.drawRightString(width - margin - 4 * mm, y, f"Date of issue: {_fmt_date(cert.issue_date)}")
    y -= 14 * mm

    text_width = width - 2 * margin - 8 * mm
    paragraphs = certificate_body(cert)
    floor_y = margin + 32 * mm + 22 * mm  # stay clear of the signature image and QR
    body_size = 12
    while body_size > 9:
        leading = body_size * 1.6
        needed = sum(len(simpleSplit(t, FONT, body_size, text_width)) * leading + 5 * mm for t in paragraphs)
        if y - needed >= floor_y:
            break
        body_size -= 0.5
    for paragraph in paragraphs:
        y = _wrapped(c, paragraph, margin + 4 * mm, y, text_width, size=body_size, leading=body_size * 1.6) - 5 * mm

    # Signature block (bottom right) and QR (bottom left)
    sig_y = margin + 32 * mm
    if signature is not None:
        c.drawImage(signature, width - margin - 62 * mm, sig_y, 48 * mm, 18 * mm, preserveAspectRatio=True, mask="auto")
    c.setLineWidth(0.6)
    c.line(width - margin - 64 * mm, sig_y - 1 * mm, width - margin - 8 * mm, sig_y - 1 * mm)
    c.setFont(FONT_BOLD, 10)
    c.drawRightString(width - margin - 8 * mm, sig_y - 6 * mm, signatory_name or "Authorized Signatory")
    c.setFont(FONT, 9)
    if signatory_title:
        c.drawRightString(width - margin - 8 * mm, sig_y - 11 * mm, signatory_title)

    qr_size = 28 * mm
    _draw_qr(c, verify_url, margin + 4 * mm, margin + 6 * mm, qr_size)
    c.setFont(FONT, 7.5)
    c.drawString(margin + 4 * mm + qr_size + 3 * mm, margin + 20 * mm, "Scan to verify this certificate")
    c.drawString(margin + 4 * mm + qr_size + 3 * mm, margin + 15 * mm, f"No. {cert.certificate_number}")

    if cert.status != Certificate.Status.ISSUED:
        label = "CANCELLED" if cert.status == Certificate.Status.CANCELLED else "SUPERSEDED"
        c.saveState()
        c.setFillColor(Color(0.8, 0.1, 0.1, alpha=0.22))
        c.setFont(FONT_BOLD, 80)
        c.translate(width / 2, height / 2)
        c.rotate(35)
        c.drawCentredString(0, 0, label)
        c.restoreState()

    c.showPage()
    c.save()
    return buf.getvalue()


# --- ID card ---------------------------------------------------------------------------

ID_CARD_SIZE = (85.6 * mm, 54 * mm)  # CR80


def render_id_card_pdf(card, verify_url, institution_logo=None, photo=None):
    """`card` is the minimal dict from idcards.build_*_card (no DOB, address,
    contact data or guardian details)."""
    _ensure_fonts()
    buf = io.BytesIO()
    w, h = ID_CARD_SIZE
    c = canvas.Canvas(buf, pagesize=ID_CARD_SIZE)
    c.setTitle(f"ID Card {card['id_number']}")
    c.setCreator("EduSekai")

    c.setFillColor(HexColor("#0369A1"))
    c.rect(0, h - 12 * mm, w, 12 * mm, stroke=0, fill=1)
    x_text = 3 * mm
    if institution_logo is not None:
        c.drawImage(institution_logo, 2 * mm, h - 11 * mm, 10 * mm, 10 * mm, preserveAspectRatio=True, mask="auto")
        x_text = 14 * mm
    c.setFillColor(HexColor("#FFFFFF"))
    school, school_size = fit_lines(card["school_name"], FONT_BOLD, w - x_text - 2 * mm, 3, 8, 5)
    c.setFont(FONT_BOLD, school_size)
    school_gap = school_size * 1.2
    top = h - 12 * mm / 2 + (len(school) - 1) * school_gap / 2 - school_size * 0.35
    for i, line in enumerate(school):
        c.drawString(x_text, top - i * school_gap, line)

    c.setFillColor(black)
    photo_w, photo_h = 20 * mm, 25 * mm
    px, py = 3 * mm, h - 14 * mm - photo_h
    if photo is not None:
        c.drawImage(photo, px, py, photo_w, photo_h, preserveAspectRatio=True, anchor="c", mask="auto")
    else:
        c.setStrokeColor(HexColor("#94A3B8"))
        c.setDash(2, 2)
        c.rect(px, py, photo_w, photo_h)
        c.setDash()
        c.setFont(FONT, 6)
        c.setFillColor(HexColor("#64748B"))
        c.drawCentredString(px + photo_w / 2, py + photo_h / 2, "No photo")
        c.setFillColor(black)

    # The QR is 20 mm so a long signed token still prints with modules of about
    # 0.33 mm, the usual floor for reliable phone scanning. Text stays left of it.
    qr_size = 20 * mm
    qr_x = w - qr_size - 3 * mm
    tx = px + photo_w + 3 * mm
    text_width = qr_x - tx - 1.5 * mm
    ty = h - 17.5 * mm
    name_lines, name_size = fit_lines(card["holder_name"], FONT_BOLD, text_width, 4, 9, 6)
    c.setFont(FONT_BOLD, name_size)
    for line in name_lines:
        c.drawString(tx, ty, line)
        ty -= name_size * 1.2
    ty -= 0.8 * mm
    rows = [("ID", card["id_number"])] + [(label, value) for label, value in card["details"] if value]
    for label, value in rows:
        row_font = FONT_BOLD if label == "ID" else FONT
        lines, size = fit_lines(f"{label}: {value}", row_font, text_width, 1 if label == "ID" else 2, 7, 5)
        c.setFont(row_font, size)
        for line in lines:
            c.drawString(tx, ty, line)
            ty -= size * 1.25

    _draw_qr(c, verify_url, qr_x, 3 * mm, qr_size)
    c.setFont(FONT_BOLD, 7)
    c.drawString(3 * mm, 3.5 * mm, card["kind_label"].upper())
    c.showPage()
    c.save()
    return buf.getvalue()
