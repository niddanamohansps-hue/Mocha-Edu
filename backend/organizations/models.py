from django.db import models
from django_tenants.models import TenantMixin, DomainMixin

from config.tenant_identity_guard import IdentityGuardedTenantMixin
import uuid


class Organization(IdentityGuardedTenantMixin, TenantMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    auto_create_schema = True

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Domain(DomainMixin):
    pass
