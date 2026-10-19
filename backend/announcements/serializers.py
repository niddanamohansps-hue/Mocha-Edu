from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import Announcement, AnnouncementRecipient


def to_drf_error(exc):
    """Converts a Django ValidationError into DRF's error shape."""
    if hasattr(exc, "error_dict"):
        return serializers.ValidationError(exc.message_dict)
    return serializers.ValidationError({"non_field_errors": exc.messages})


class AnnouncementSerializer(serializers.ModelSerializer):
    """
    Admin read/write shape. status/published_at are changed only through the
    lifecycle actions (schedule, cancel, publish, archive), never by PATCH.
    Model.save() runs full validation, so the audience and scheduling rules
    are enforced here too; their errors are returned as 400s.
    """

    recipient_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Announcement
        fields = [
            "id",
            "title",
            "body",
            "audience_type",
            "audience_section",
            "audience_level",
            "send_email",
            "status",
            "scheduled_at",
            "published_at",
            "created_by_user_id",
            "recipient_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "scheduled_at",
            "published_at",
            "created_by_user_id",
            "recipient_count",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        try:
            return super().create(validated_data)
        except DjangoValidationError as exc:
            raise to_drf_error(exc)

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except DjangoValidationError as exc:
            raise to_drf_error(exc)


class ScheduleSerializer(serializers.Serializer):
    scheduled_at = serializers.DateTimeField()


class AnnouncementRecipientSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnnouncementRecipient
        fields = ["user_id", "email_sent", "created_at"]
        read_only_fields = fields


class MyAnnouncementSerializer(serializers.ModelSerializer):
    """What a recipient sees: content only, no audience or delivery data."""

    class Meta:
        model = Announcement
        fields = ["id", "title", "body", "published_at"]
        read_only_fields = fields
