"""The school's calendar day.

The server keeps time in UTC (``TIME_ZONE = "UTC"``), so ``timezone.localdate()`` is the UTC date, which is the
previous day in South Asia until 05:30 or 05:45 in the morning. Anything a person reads as "today" (a due date, a
loan date, the month to bill, the day on a receipt) uses the school's own day instead, from ``ALERT_TIME_ZONE``.
"""
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone


def school_zone():
    return ZoneInfo(getattr(settings, "ALERT_TIME_ZONE", "Asia/Kathmandu"))


def school_today():
    """Today's date on the school calendar."""
    return timezone.now().astimezone(school_zone()).date()


def school_date(moment):
    """The school-calendar date of an aware datetime, such as a ``created_at``."""
    return moment.astimezone(school_zone()).date()
