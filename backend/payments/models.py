from django.db import models
import uuid


class Payment(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
    )

    transaction_uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")

    # Registration Data (Stored temporarily until payment success)
    organization_name = models.CharField(max_length=255)
    subdomain = models.CharField(max_length=255)
    username = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20)
    password = models.CharField(
        max_length=512
    )  # Encrypted at rest via accounts.utils.crypto (see payments/views.py)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_uuid} - {self.amount} - {self.status}"
