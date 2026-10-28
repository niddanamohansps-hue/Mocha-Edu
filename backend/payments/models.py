from django.db import models
from django.db.models import Q
import uuid


class Payment(models.Model):
    """
    One paid signup. The state machine:

        PENDING -> PAID -> PROVISIONING -> PROVISIONED
                              |  ^
                              v  |
                      PROVISIONING_FAILED          (retried, then handled by a person)
        PENDING -> EXPIRED                          (never paid; a late valid payment is still honoured)

    ``PAID`` means the gateway confirmed the money; it is never undone. The institution is created
    afterwards and the stored (encrypted) signup password is discarded once that has happened.
    """

    PENDING = "PENDING"
    PAID = "PAID"
    PROVISIONING = "PROVISIONING"
    PROVISIONED = "PROVISIONED"
    PROVISIONING_FAILED = "PROVISIONING_FAILED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"

    STATUS_CHOICES = (
        (PENDING, "Pending"),
        (PAID, "Paid"),
        (PROVISIONING, "Provisioning"),
        (PROVISIONED, "Provisioned"),
        (PROVISIONING_FAILED, "Provisioning failed"),
        (EXPIRED, "Expired"),
        (FAILED, "Failed"),
    )
    # States in which the subdomain is reserved for this signup (PROVISIONED is covered by the
    # Organization's own unique schema name).
    RESERVING_STATUSES = (PENDING, PAID, PROVISIONING, PROVISIONING_FAILED)

    transaction_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)

    # Registration Data (Stored temporarily until payment success)
    organization_name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=255)
    username = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    password = models.CharField(
        max_length=512, blank=True
    )  # Encrypted at rest via accounts.utils.crypto; emptied once provisioned or discarded

    expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    gateway_reference = models.CharField(max_length=100, blank=True)
    provisioned_at = models.DateTimeField(null=True, blank=True)
    provisioning_attempts = models.PositiveSmallIntegerField(default=0)
    gateway_checked_at = models.DateTimeField(null=True, blank=True)
    attention_notified_at = models.DateTimeField(null=True, blank=True)
    failure_code = models.CharField(max_length=50, blank=True)
    # What the school chose at signup (empty for signups made before plans existed).
    plan = models.ForeignKey("billing.Plan", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    cycle = models.CharField(max_length=10, blank=True)
    gateway = models.CharField(max_length=20, default="esewa")
    # The gateway's own order id (Razorpay order_...), to match its confirmation.
    gateway_order_id = models.CharField(max_length=60, blank=True, db_index=True)
    organization = models.OneToOneField(
        "organizations.Organization",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="signup_payment",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subdomain"],
                condition=Q(status__in=["PENDING", "PAID", "PROVISIONING", "PROVISIONING_FAILED"]),
                name="uniq_reserved_signup_subdomain",
            ),
        ]

    def __str__(self):
        return f"{self.transaction_uuid} - {self.amount} - {self.status}"
