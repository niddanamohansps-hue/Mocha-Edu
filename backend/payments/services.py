"""Signup-payment state transitions (see ``Payment`` for the state machine).

Rules: a confirmed payment is never undone; every transition is a locked read-modify-write or a
conditional UPDATE, so concurrent callbacks cannot both provision; tenant creation (schema DDL)
runs outside any transaction and can be resumed.
"""
import logging
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from accounts.provisioning import ProvisioningError, provision_organization
from accounts.utils.crypto import decrypt_secret
from .models import Payment

logger = logging.getLogger(__name__)

# Outcomes of process_confirmed_payment
PROVISIONED = "provisioned"
ALREADY_PROVISIONED = "already_provisioned"
IN_PROGRESS = "in_progress"
FAILED = "failed"
NEEDS_ATTENTION = "needs_attention"

# Failure codes that retrying cannot fix (a person has to look at the payment).
PERMANENT_FAILURE_CODES = frozenset(
    {"subdomain_taken", "username_taken", "password_mismatch", "domain_conflict", "data_discarded"}
)


# A claim that has not finished after this long belongs to a crashed attempt and may be taken over.
PROVISIONING_STALL = timedelta(minutes=15)


def reservation_ttl():
    return timedelta(minutes=int(getattr(settings, "SIGNUP_PAYMENT_TTL_MINUTES", 60)))


def expire_stale_reservations(subdomain=None):
    """PENDING signups past their expiry give up their subdomain. The stored password is kept for
    a retention window so a payment that arrives late can still be honoured."""
    stale = Payment.objects.filter(status=Payment.PENDING, expires_at__lt=timezone.now())
    if subdomain is not None:
        stale = stale.filter(subdomain=subdomain)
    return stale.update(status=Payment.EXPIRED)


def create_pending_payment(*, amount, data):
    """Reserve the subdomain and store the (encrypted-by-caller) signup. Returns None if the
    subdomain is reserved by another signup."""
    from accounts.utils.crypto import encrypt_secret

    expire_stale_reservations(data["subdomain"])
    try:
        with transaction.atomic():
            return Payment.objects.create(
                amount=amount,
                organization_name=data["organization_name"],
                subdomain=data["subdomain"],
                username=data["username"],
                email=data["email"],
                phone=data.get("phone", ""),
                password=encrypt_secret(data["password"]),
                expires_at=timezone.now() + reservation_ttl(),
            )
    except IntegrityError:
        return None


def _flag_attention(payment_pk, code):
    Payment.objects.filter(pk=payment_pk).update(failure_code=code)
    logger.error("Signup payment %s needs a person to look at it (%s).", payment_pk, code)


def record_confirmed_payment(payment_pk, *, gateway_reference):
    """Record that the gateway confirmed the money. Returns the payment's state afterwards:
    one of the outcomes above, or ``None`` when the payment is ready to be provisioned."""
    with transaction.atomic():
        payment = Payment.objects.select_for_update().get(pk=payment_pk)
        if payment.status == Payment.PROVISIONED:
            return ALREADY_PROVISIONED
        if payment.status == Payment.PROVISIONING:
            return IN_PROGRESS
        if payment.status in (Payment.PAID, Payment.PROVISIONING_FAILED):
            return None
        # PENDING, or EXPIRED/FAILED where the money arrived after we gave up: honour it.
        was_late = payment.status != Payment.PENDING
        if was_late and not payment.password:
            # The signup data was already discarded, so the institution cannot be created.
            payment.paid_at = payment.paid_at or timezone.now()
            payment.gateway_reference = gateway_reference
            payment.failure_code = "data_discarded"
            payment.save(update_fields=["paid_at", "gateway_reference", "failure_code", "updated_at"])
            logger.error("Signup payment %s was paid after its data was discarded.", payment.pk)
            return NEEDS_ATTENTION
        previous = payment.status
        payment.status = Payment.PAID
        payment.paid_at = timezone.now()
        payment.gateway_reference = gateway_reference
        payment.failure_code = ""
        try:
            with transaction.atomic():
                payment.save(update_fields=["status", "paid_at", "gateway_reference", "failure_code", "updated_at"])
        except IntegrityError:
            # Someone else reserved the subdomain after this signup expired.
            payment.status = previous
            payment.paid_at = payment.paid_at or timezone.now()
            payment.failure_code = "subdomain_taken"
            payment.save(update_fields=["paid_at", "gateway_reference", "failure_code", "updated_at"])
            logger.error("Signup payment %s was paid after its subdomain was reserved by another.", payment.pk)
            return NEEDS_ATTENTION
    return None


def _claim_for_provisioning(payment_pk):
    return Payment.objects.filter(
        pk=payment_pk, status__in=[Payment.PAID, Payment.PROVISIONING_FAILED]
    ).update(
        status=Payment.PROVISIONING,
        provisioning_attempts=F("provisioning_attempts") + 1,
        updated_at=timezone.now(),
    )


def _link_organization(payment_pk):
    def link(organization):
        Payment.objects.filter(pk=payment_pk).update(organization=organization)

    return link


def provision(payment_pk):
    """Create the institution for a paid signup. Returns ``(outcome, result)``; ``result`` holds
    the login URL when provisioned. Safe to call again after a failure or a crash."""
    if not _claim_for_provisioning(payment_pk):
        payment = Payment.objects.get(pk=payment_pk)
        return (ALREADY_PROVISIONED if payment.status == Payment.PROVISIONED else IN_PROGRESS), None

    payment = Payment.objects.select_related("organization").get(pk=payment_pk)
    try:
        result = provision_organization(
            organization_name=payment.organization_name,
            subdomain=payment.subdomain,
            username=payment.username,
            email=payment.email,
            password=decrypt_secret(payment.password),
            phone=payment.phone,
            organization=payment.organization,
            on_organization_created=_link_organization(payment_pk),
        )
    except ProvisioningError as exc:
        code = exc.code
        logger.error("Signup payment %s could not be provisioned (%s).", payment_pk, code)
    except Exception:
        code = "unexpected_error"
        logger.exception("Signup payment %s could not be provisioned.", payment_pk)
    else:
        Payment.objects.filter(pk=payment_pk).update(
            status=Payment.PROVISIONED,
            provisioned_at=timezone.now(),
            organization=result["organization"],
            password="",
            failure_code="",
            updated_at=timezone.now(),
        )
        _start_billing(payment_pk, result["organization"])
        return PROVISIONED, result

    Payment.objects.filter(pk=payment_pk).update(
        status=Payment.PROVISIONING_FAILED, failure_code=code, updated_at=timezone.now()
    )
    return FAILED, None


def _start_billing(payment_pk, organization):
    """The school exists: give it its subscription. A billing problem never undoes the school."""
    try:
        from billing.signup import on_school_provisioned

        on_school_provisioned(Payment.objects.select_related("plan").get(pk=payment_pk), organization)
    except Exception:
        logger.exception("Signup payment %s: the school was created but its subscription was not.", payment_pk)


def recover_stalled_provisioning(payment_pk=None):
    """Hand a provisioning attempt that died mid-way back to PROVISIONING_FAILED so it can resume."""
    stalled = Payment.objects.filter(
        status=Payment.PROVISIONING, updated_at__lt=timezone.now() - PROVISIONING_STALL
    )
    if payment_pk is not None:
        stalled = stalled.filter(pk=payment_pk)
    return stalled.update(status=Payment.PROVISIONING_FAILED, failure_code="stalled")


def process_confirmed_payment(payment_pk, *, gateway_reference):
    """The whole path after a verified COMPLETE: record the money, then provision."""
    recover_stalled_provisioning(payment_pk)
    early = record_confirmed_payment(payment_pk, gateway_reference=gateway_reference)
    if early is not None:
        return early, None
    return provision(payment_pk)


# --- Reconciliation (driven by payments.tasks) ------------------------------------------------

# Failure codes that a person has to decide on: retrying automatically would not help (or, for a
# row migrated from the old flow, was never reviewed).
MANUAL_REVIEW_CODES = PERMANENT_FAILURE_CODES | {"legacy_no_institution"}
PENDING_RECHECK = timedelta(minutes=10)
EXPIRED_RECHECK = timedelta(hours=6)
PROVISION_RETRY_BACKOFF = timedelta(minutes=5)


def _setting(name, default):
    return getattr(settings, name, default)


def discard_expired_signup_data():
    """Drop the stored (encrypted) password of unpaid signups once the retention window has
    passed. A signup that was paid is never touched: its data is needed until it is resolved."""
    cutoff = timezone.now() - timedelta(days=int(_setting("SIGNUP_PAYMENT_DATA_RETENTION_DAYS", 7)))
    return (
        Payment.objects.filter(
            status__in=[Payment.EXPIRED, Payment.FAILED], paid_at__isnull=True, expires_at__lt=cutoff
        )
        .exclude(password="")
        .update(password="")
    )


def _ask_gateway(payment):
    from fees.gateways import query_esewa_status

    return query_esewa_status(
        transaction_uuid=payment.transaction_uuid.hex,
        amount=payment.amount,
        merchant_code=_setting("ESEWA_PRODUCT_CODE", "EPAYTEST"),
    )


def reconcile_with_gateway(*, batch_size, deadline):
    """Ask eSewa about signups that are unpaid as far as we know: PENDING ones past a grace
    period, and EXPIRED ones whose data we still hold (money may arrive late). Only a COMPLETE
    answer whose identity matched the stored payment changes anything. Returns
    ``(summary, payment_pks_ready_to_provision)``."""
    import time

    from django.db.models import Q

    now = timezone.now()
    grace = timedelta(minutes=int(_setting("SIGNUP_RECONCILE_GRACE_MINUTES", 10)))
    due_pending = Q(status=Payment.PENDING, created_at__lt=now - grace) & (
        Q(gateway_checked_at__isnull=True) | Q(gateway_checked_at__lt=now - PENDING_RECHECK)
    )
    due_expired = Q(status=Payment.EXPIRED, paid_at__isnull=True) & ~Q(password="") & (
        Q(gateway_checked_at__isnull=True) | Q(gateway_checked_at__lt=now - EXPIRED_RECHECK)
    )
    ids = list(
        Payment.objects.filter(due_pending | due_expired)
        .order_by("gateway_checked_at", "created_at")
        .values_list("pk", flat=True)[:batch_size]
    )
    summary = {"checked": 0, "paid_found": 0, "errors": 0, "deferred": 0}
    ready = []
    for index, pk in enumerate(ids):
        if time.monotonic() > deadline:
            summary["deferred"] = len(ids) - index
            break
        payment = Payment.objects.get(pk=pk)
        result = _ask_gateway(payment)
        Payment.objects.filter(pk=pk).update(gateway_checked_at=timezone.now())
        summary["checked"] += 1
        if result.status == "COMPLETE":
            summary["paid_found"] += 1
            if record_confirmed_payment(pk, gateway_reference=result.gateway_reference) is None:
                ready.append(pk)
        elif result.status in ("ERROR", "INVALID", "UNKNOWN"):
            summary["errors"] += 1
    return summary, ready


def provisioning_retry_candidates(batch_size):
    """Paid signups whose institution still has to be created and that a person does not have to
    look at first: retried automatically a limited number of times."""
    cutoff = timezone.now() - PROVISION_RETRY_BACKOFF
    limit = int(_setting("SIGNUP_PROVISIONING_MAX_ATTEMPTS", 3))
    return list(
        Payment.objects.filter(
            status__in=[Payment.PAID, Payment.PROVISIONING_FAILED],
            provisioning_attempts__lt=limit,
            updated_at__lt=cutoff,
        )
        .exclude(failure_code__in=MANUAL_REVIEW_CODES)
        .order_by("updated_at")
        .values_list("pk", flat=True)[:batch_size]
    )


def payments_needing_attention():
    """Paid signups that will not resolve on their own and have not been announced yet."""
    from django.db.models import Q

    limit = int(_setting("SIGNUP_PROVISIONING_MAX_ATTEMPTS", 3))
    stuck = Q(status__in=[Payment.PAID, Payment.PROVISIONING_FAILED]) & (
        Q(provisioning_attempts__gte=limit) | Q(failure_code__in=MANUAL_REVIEW_CODES)
    )
    paid_but_unusable = Q(status__in=[Payment.EXPIRED, Payment.FAILED], paid_at__isnull=False)
    return Payment.objects.filter(stuck | paid_but_unusable, attention_notified_at__isnull=True)


def alert_recipients():
    raw = _setting("SIGNUP_PAYMENT_ALERT_EMAILS", "")
    if isinstance(raw, str):
        raw = raw.split(",")
    return [address.strip() for address in raw if address and address.strip()]


def notify_attention(batch_size=20):
    """Tell the platform operators about paid signups that need a person. Each payment is
    announced once (``attention_notified_at``). Always logged at ERROR; emailed when
    SIGNUP_PAYMENT_ALERT_EMAILS is set. The message carries ids and states only: no customer
    name, email, phone or password."""
    from django.core.mail import send_mail

    recipients = alert_recipients()
    notified = 0
    for payment in payments_needing_attention().order_by("created_at")[:batch_size]:
        logger.error(
            "Signup payment %s needs attention: status=%s failure_code=%s attempts=%s",
            payment.transaction_uuid,
            payment.status,
            payment.failure_code or "-",
            payment.provisioning_attempts,
        )
        if recipients:
            body = (
                "A paid signup could not be completed automatically.\n\n"
                f"Transaction: {payment.transaction_uuid}\n"
                f"Status: {payment.status}\n"
                f"Reason: {payment.failure_code or 'retries exhausted'}\n"
                f"Attempts: {payment.provisioning_attempts}\n"
                f"Subdomain: {payment.subdomain}\n"
                f"Paid at: {payment.paid_at}\n\n"
                "Open the Payments admin page to review it."
            )
            try:
                send_mail("EduSekai: a paid signup needs attention", body, None, recipients, fail_silently=False)
            except Exception:
                logger.exception("Could not email the attention alert for signup payment %s.", payment.transaction_uuid)
                continue
        Payment.objects.filter(pk=payment.pk).update(attention_notified_at=timezone.now())
        notified += 1
    return notified
