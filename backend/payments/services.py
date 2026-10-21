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
        return PROVISIONED, result

    Payment.objects.filter(pk=payment_pk).update(
        status=Payment.PROVISIONING_FAILED, failure_code=code, updated_at=timezone.now()
    )
    return FAILED, None


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
