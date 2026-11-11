"""Creating a new institution (tenant) with its first owner.

``provision_organization`` is safe to call again after a partial failure: every step either creates
what is missing or finds what a previous attempt already created. Tenant creation runs schema DDL,
so the whole thing cannot be one database transaction.
"""
from django.conf import settings
from django.db import IntegrityError
from django_tenants.utils import tenant_context

from accounts.models import User
from organizations.models import Domain, Organization
from roles.models import Role, UserRole



def base_domain():
    """The domain each school's subdomain sits under, e.g. "edusekai.in" for greenfield.edusekai.in."""
    return settings.TENANT_BASE_DOMAIN


def login_url(full_domain_name):
    return settings.TENANT_LOGIN_URL_TEMPLATE.format(domain=full_domain_name)


class ProvisioningError(Exception):
    """The institution cannot be created from this data. ``code`` is safe to store and log."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code
        self.message = message


def provision_organization(
    *,
    organization_name,
    subdomain,
    username,
    email,
    password,
    phone="",
    organization=None,
    on_organization_created=None,
):
    """
    Create the organization, its primary domain and its owner. ``organization`` resumes an earlier
    attempt that already created the tenant; ``on_organization_created(organization)`` is called
    as soon as a new tenant exists so a caller can record it before the remaining steps run.
    """
    from profiles.models import Profile  # imported here: profiles depends on accounts

    full_domain_name = f"{subdomain}.{base_domain()}"
    user = User.objects.filter(email=email).first()

    # Everything that can be known to be wrong is checked before the (slow, hard to undo) tenant
    # is created. A resumed attempt skips the subdomain/username checks: they would only find
    # what the earlier attempt itself created.
    if user is not None and not user.check_password(password):
        raise ProvisioningError("password_mismatch", "Password does not match existing account for this email.")
    if organization is None:
        if Organization.objects.filter(schema_name=subdomain).exists():
            raise ProvisioningError("subdomain_taken", "This subdomain is already taken.")
        if user is None and User.objects.filter(username=username).exists():
            raise ProvisioningError("username_taken", "This username is already taken.")
        organization = Organization.objects.create(name=organization_name, schema_name=subdomain)
        if on_organization_created is not None:
            on_organization_created(organization)

    domain, _ = Domain.objects.get_or_create(
        domain=full_domain_name, defaults={"tenant": organization, "is_primary": True}
    )
    if domain.tenant_id != organization.pk:
        raise ProvisioningError("domain_conflict", "The domain already belongs to another institution.")

    if user is None:
        try:
            user = User.objects.create_user(username=username, email=email, password=password)
        except IntegrityError:
            # A concurrent attempt created it; use that one only if it is the same account.
            user = User.objects.filter(email=email).first()
            if user is None or not user.check_password(password):
                raise ProvisioningError("username_taken", "This username is already taken.")

    with tenant_context(organization):
        owner_role, _ = Role.objects.get_or_create(
            slug="owner", defaults={"name": "Owner", "is_system_role": True}
        )
        # Creating the link triggers profiles/signals.py, which creates the identity, staff and
        # institution profiles.
        UserRole.objects.get_or_create(user=user, role=owner_role)
        Profile.objects.filter(user_id=user.id).update(phone=phone, local_username=username)

    return {
        "organization": organization,
        "domain": domain,
        "user": user,
        "domain_url": login_url(full_domain_name),
    }
