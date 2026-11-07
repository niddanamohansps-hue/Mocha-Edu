"""A link in a fee reminder that lets a parent pay without logging in.

The link carries only a signed, expiring reference to the student. It shows what is outstanding right now and
starts an ordinary online payment order through the same code as the logged-in flow, so the gateway checks, the
signed callback, the webhook and the reconciliation are all unchanged: this adds a way in, not a second way to
record money. Paying is all the link can do; it reveals only the fee names and amounts due for that one student.
"""
from decimal import Decimal

from django.conf import settings
from django.core import signing

from core.links import portal_link

from .gateways import PaymentConfigurationError, get_gateway_credentials
from .models import StudentFee
from .services import annotate_with_outstanding_balance, initiate_online_payment_order

SALT = "fees.paylink"
PAY_LINK_MAX_AGE_SECONDS = 14 * 24 * 3600


def pay_gateway():
    return getattr(settings, "FEES_PAY_LINK_GATEWAY", "razorpay")


def online_payment_available():
    """Whether this school has a working gateway for pay links. A link is only put in a reminder when it would work."""
    gateway = pay_gateway()
    if gateway == "mock":
        return True
    try:
        get_gateway_credentials(gateway)
    except PaymentConfigurationError:
        return False
    return True


def make_token(student_id):
    return signing.dumps({"s": str(student_id)}, salt=SALT)


def student_from_token(token):
    """The active student a valid, unexpired token names, or None. Tampered, expired and unknown tokens all give None."""
    from students.models import Student

    try:
        data = signing.loads(token, salt=SALT, max_age=PAY_LINK_MAX_AGE_SECONDS)
        student_id = data["s"]
    except (signing.BadSignature, KeyError, TypeError):
        return None
    return Student.objects.filter(pk=student_id, status="active").select_related("profile").first()


def pay_path(student):
    return f"/pay/{make_token(student.id)}"


def pay_url(student):
    """The full link to put in an email or WhatsApp message."""
    return portal_link(pay_path(student))


def outstanding_fees(student):
    """The student's active fees with something left to pay, soonest due first, each with ``_outstanding``."""
    qs = StudentFee.objects.filter(student=student, status="active").select_related("fee_head")
    return list(annotate_with_outstanding_balance(qs).filter(_outstanding__gt=0).order_by("due_date", "created_at"))


def start_payment(student, fee_ids=None):
    """Create an online payment order for the chosen outstanding fees (all of them by default), each paid in full at
    its current balance. Raises ValueError for a choice that is not payable; gateway errors pass through."""
    fees = outstanding_fees(student)
    if fee_ids is not None:
        wanted = {str(i) for i in fee_ids}
        fees = [f for f in fees if str(f.id) in wanted]
        if len(fees) != len(wanted):
            raise ValueError("One or more of the chosen fees cannot be paid.")
    if not fees:
        raise ValueError("There is nothing to pay.")
    total = sum((f._outstanding for f in fees), Decimal("0"))
    return initiate_online_payment_order(
        student=student,
        amount=total,
        allocations=[{"student_fee_id": f.id, "amount": f._outstanding} for f in fees],
        gateway=pay_gateway(),
        created_by=None,
        ttl_minutes=60,
        callback_kind="fees",
    )
