"""
Shared pieces for importing a school's existing data from Excel (.xlsx) or CSV.

Each importer (students, staff, opening fee balances) declares its columns and two functions: ``check`` turns
the raw rows into clean rows plus row-numbered errors, and ``save`` writes clean rows. The flow is always:
upload -> check every row -> preview (nothing saved) -> confirm -> save everything in one transaction, or
nothing if any row has a problem. Row numbers match the spreadsheet (header = row 1).
"""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime

MAX_BYTES = 5 * 1024 * 1024
MAX_ROWS = 5000
PREVIEW_ROWS = 50


class ImportFileError(Exception):
    """The file itself cannot be used (wrong type, too big, empty, missing columns)."""


@dataclass
class Column:
    name: str
    required: bool = False
    example: str = ""
    help: str = ""


@dataclass
class CheckResult:
    rows: list = field(default_factory=list)      # clean rows, each a dict, with "_row" = spreadsheet row
    errors: list = field(default_factory=list)    # {"row": n, "column": name, "message": text}

    def error(self, row, column, message):
        self.errors.append({"row": row, "column": column, "message": message})


def _header(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def read_rows(upload, columns):
    """Reads an uploaded .xlsx or .csv into a list of {column: text} dicts (blank rows skipped)."""
    name = (getattr(upload, "name", "") or "").lower()
    if getattr(upload, "size", 0) > MAX_BYTES:
        raise ImportFileError("The file is larger than 5 MB. Split it into smaller files.")
    raw = upload.read()
    if name.endswith(".xlsx"):
        from openpyxl import load_workbook

        try:
            sheet = load_workbook(io.BytesIO(raw), read_only=True, data_only=True).worksheets[0]
        except Exception:  # noqa: BLE001
            raise ImportFileError("The Excel file could not be read. Save it again as .xlsx and retry.") from None
        table = [list(r) for r in sheet.iter_rows(values_only=True)]
    elif name.endswith(".csv"):
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("cp1252", errors="replace")
        table = list(csv.reader(io.StringIO(text)))
    else:
        raise ImportFileError("Upload the filled template as .xlsx (Excel) or .csv.")

    while table and not any(str(v or "").strip() for v in table[0]):
        table.pop(0)
    if not table:
        raise ImportFileError("The file is empty.")
    headers = [_header(h) for h in table[0]]
    known = {c.name for c in columns}
    missing = [c.name for c in columns if c.required and c.name not in headers]
    if missing:
        raise ImportFileError(f"Columns missing: {', '.join(missing)}. Use the template's first row as it is.")
    rows = []
    for number, values in enumerate(table[1:], start=2):
        record = {h: values[i] if i < len(values) else None for i, h in enumerate(headers) if h in known}
        if not any(str(v).strip() for v in record.values() if v is not None):
            continue
        record["_row"] = number
        rows.append(record)
    if not rows:
        raise ImportFileError("The file has no data rows under the header.")
    if len(rows) > MAX_ROWS:
        raise ImportFileError(f"At most {MAX_ROWS:,} rows per file. Split it into smaller files.")
    return rows


def template_xlsx(title, columns, notes=()):
    """An Excel template: the header row, one example row, and a sheet explaining each column."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    book = Workbook()
    sheet = book.active
    sheet.title = title[:31]
    sheet.append([c.name for c in columns])
    sheet.append([c.example for c in columns])
    for cell in sheet[1]:
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DBEAFE")
    for i, column in enumerate(columns, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=i).column_letter].width = max(14, len(column.name) + 4)
    help_sheet = book.create_sheet("How to fill")
    help_sheet.append(["Column", "Required", "Example", "How to fill"])
    for cell in help_sheet[1]:
        cell.font = Font(bold=True)
    for column in columns:
        help_sheet.append([column.name, "Yes" if column.required else "", column.example, column.help])
    help_sheet.append([])
    help_sheet.append(["Delete the example row before importing. Keep the first row (column names) as it is."])
    for note in notes:
        help_sheet.append([note])
    help_sheet.column_dimensions["A"].width = 24
    help_sheet.column_dimensions["D"].width = 90
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


# --- value cleaners: each returns the clean value, or raises ValueError with a plain message -------------

def text(value, limit=255):
    value = "" if value is None else str(value).strip()
    if isinstance(value, str) and value.endswith(".0") and value[:-2].isdigit():
        value = value[:-2]  # Excel turns 12345 into 12345.0
    if len(value) > limit:
        raise ValueError(f"is longer than {limit} characters")
    return value


def parse_date(value):
    """Accepts Excel dates, 15-06-2012, 15/06/2012, 15.06.2012 and 2012-06-15 (day before month)."""
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%Y-%m-%d", "%d-%m-%y", "%d/%m/%y", "%d-%b-%Y", "%d %b %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError("is not a date like 15-06-2012")


def gender(value):
    raw = text(value).lower()
    mapping = {"m": "male", "male": "male", "boy": "male", "f": "female", "female": "female", "girl": "female",
               "o": "other", "other": "other"}
    if raw not in mapping:
        raise ValueError("should be Male, Female or Other")
    return mapping[raw]


def phone(value):
    raw = text(value)
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("should be a 10-digit mobile number")
    return digits


def amount(value):
    from decimal import Decimal, InvalidOperation

    raw = text(value).replace(",", "").replace("₹", "").replace("Rs.", "").replace("Rs", "").strip()
    try:
        number = Decimal(raw).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise ValueError("is not an amount like 2500 or 2500.50") from None
    if number <= 0:
        raise ValueError("must be more than 0")
    return number


def yes_no(value):
    return text(value).lower() in ("yes", "y", "true", "1")


def split_name(full):
    """'Rajesh Kumar Sharma' -> ('Rajesh', 'Kumar', 'Sharma'); a single word is a first name only."""
    parts = text(full, 150).split()
    if not parts:
        return "", "", ""
    if len(parts) == 1:
        return parts[0], "", ""
    return parts[0], " ".join(parts[1:-1]), parts[-1]
