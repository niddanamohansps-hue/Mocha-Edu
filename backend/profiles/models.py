from django.db import models, connection
from django.conf import settings
import uuid


class Profile(models.Model):
    """
    Identity Layer: Stores 'Human' data.
    Uses 'Soft Links' (UUIDs) for cross-schema relationships to
    ensure total data isolation and prevent Admin crashes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # SOFT LINK: Store the UUID of the User from the public schema
    # We don't use a ForeignKey here to prevent Cross-Schema integrity issues
    user_id = models.UUIDField(db_index=True, null=True, blank=True)

    # Personal Information
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, blank=True)
    last_name = models.CharField(max_length=50)

    gender = models.CharField(
        max_length=10,
        choices=[("male", "Male"), ("female", "Female"), ("other", "Other")],
        blank=True,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    blood_group = models.CharField(max_length=5, blank=True)

    # Contact Information
    phone = models.CharField(max_length=20, blank=True)
    alt_phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True, null=True)
    address = models.TextField(blank=True)

    profile_image = models.ImageField(
        upload_to="profiles/photos/", null=True, blank=True
    )

    # Memorable Local Identity
    local_username = models.CharField(
        max_length=150, unique=True, null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"
        indexes = [
            models.Index(
                fields=["user_id", "local_username"], name="profile_user_username_idx"
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def user(self):
        """Helper to fetch the global User object manually."""
        if hasattr(self, "_user_cache"):
            return self._user_cache

        from accounts.models import User

        if not self.user_id:
            return None

        return User.objects.filter(id=self.user_id).first()


class InstitutionProfile(models.Model):
    """
    Stores institutional branding. Also uses a Soft Link to the Organization.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # SOFT LINK to the organization ID
    organization_id = models.UUIDField(unique=True, null=True, blank=True)

    logo = models.ImageField(upload_to="institution/logos/", null=True, blank=True)
    banner = models.ImageField(upload_to="institution/banners/", null=True, blank=True)
    tagline = models.CharField(max_length=255, blank=True)
    mission = models.TextField(blank=True)
    vision = models.TextField(blank=True)
    about = models.TextField(blank=True)
    established_date = models.DateField(null=True, blank=True)
    website = models.URLField(blank=True)

    # Social links
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    twitter_url = models.URLField(blank=True)
    linkedin_url = models.URLField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Institution Profile"
        verbose_name_plural = "Institution Profiles"

    def __str__(self):
        return f"Institution Details ({self.organization_id})"
