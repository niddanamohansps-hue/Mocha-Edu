"""
Indian GST on the platform's invoices.

Place of supply is the school's state (from its GSTIN when it has one, otherwise the state it chose).
Same state as the platform -> CGST + SGST (half each); another state -> IGST. When the school's state is
not known, the platform's own state is used (so CGST + SGST), as for an unregistered customer whose address
is not on record.
"""
import re
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

# GST state / union territory codes.
STATES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh", "05": "Uttarakhand",
    "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh", "10": "Bihar", "11": "Sikkim",
    "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur", "15": "Mizoram", "16": "Tripura",
    "17": "Meghalaya", "18": "Assam", "19": "West Bengal", "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh",
    "23": "Madhya Pradesh", "24": "Gujarat", "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra",
    "29": "Karnataka", "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
}

GSTIN_PATTERN = re.compile(r"^(\d{2})[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
CENT = Decimal("0.01")


def platform_state():
    code = str(getattr(settings, "PLATFORM_STATE_CODE", "") or "")
    if not code:
        gstin = str(getattr(settings, "PLATFORM_GSTIN", "") or "").upper()
        code = gstin[:2] if GSTIN_PATTERN.match(gstin) else ""
    return code if code in STATES else ""


def validate_gstin(value):
    """The normalised GSTIN, or raises ValueError with a plain message."""
    value = (value or "").strip().upper()
    if not GSTIN_PATTERN.match(value):
        raise ValueError("A GSTIN has 15 characters, like 29ABCDE1234F1Z5.")
    if value[:2] not in STATES:
        raise ValueError("The first two digits of the GSTIN are not a valid state code.")
    return value


def place_of_supply(school_state):
    return school_state if school_state in STATES else platform_state()


def split(gst_amount, school_state):
    """(cgst, sgst, igst, place_of_supply) for a GST amount."""
    gst_amount = Decimal(gst_amount)
    pos = place_of_supply(school_state)
    home = platform_state()
    if pos and home and pos != home:
        return Decimal("0.00"), Decimal("0.00"), gst_amount, pos
    cgst = (gst_amount / 2).quantize(CENT, rounding=ROUND_HALF_UP)
    return cgst, gst_amount - cgst, Decimal("0.00"), pos
