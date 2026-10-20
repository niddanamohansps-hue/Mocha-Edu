from django.conf import settings
from rest_framework import serializers

from .models import AlertLog, Notification, NotificationSettings


class NotificationSerializer(serializers.ModelSerializer):
    """
    Read-only in every direction - there is no create/update serializer
    anywhere in this app. Notifications are created ONLY through
    services.notify()/notify_many(); recipient_user_id is deliberately
    excluded from the output (the client never needs it - every query is
    already scoped to the current user) and is never accepted as input.
    """

    class Meta:
        model = Notification
        fields = ["id", "title", "body", "category", "link", "is_read", "read_at", "created_at"]
        read_only_fields = fields


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()


class MarkAllReadResponseSerializer(serializers.Serializer):
    updated_count = serializers.IntegerField()


class StrictBooleanField(serializers.BooleanField):
    """Accepts only JSON true/false (DRF's default also accepts "yes", 1, "on", ...)."""

    def to_internal_value(self, data):
        if not isinstance(data, bool):
            self.fail("invalid", input=data)
        return data


class NotificationSettingsSerializer(serializers.Serializer):
    """
    Input: the six editable fields (all optional on PATCH). Unknown or read-only keys and an
    empty body are rejected, so nothing is silently ignored. Output (``instance=``): the
    editable values plus read-only ``time_zone``, ``is_default`` (no row saved yet) and
    ``updated_at``.
    """

    fee_reminders_enabled = StrictBooleanField(required=False)
    absence_alerts_enabled = StrictBooleanField(required=False)
    payment_receipts_enabled = StrictBooleanField(required=False)
    fee_reminder_days_before = serializers.IntegerField(required=False, min_value=0, max_value=30)
    overdue_reminder_interval_days = serializers.IntegerField(required=False, min_value=1, max_value=30)
    max_overdue_reminders = serializers.IntegerField(required=False, min_value=1, max_value=10)

    def validate(self, attrs):
        unknown = sorted(set(self.initial_data) - set(NotificationSettings.EDITABLE_FIELDS))
        if unknown:
            raise serializers.ValidationError(
                {"non_field_errors": [f"Unknown or read-only field(s): {', '.join(unknown)}."]}
            )
        if not attrs:
            raise serializers.ValidationError({"non_field_errors": ["No fields supplied."]})
        return attrs

    def to_representation(self, instance):
        data = instance.editable_values()
        data["time_zone"] = settings.TIME_ZONE
        data["is_default"] = instance._state.adding
        data["updated_at"] = (
            None
            if instance._state.adding
            else serializers.DateTimeField().to_representation(instance.updated_at)
        )
        return data


class AlertLogSerializer(serializers.ModelSerializer):
    """
    Read-only, and deliberately narrow: no recipient id or full address, no student name or
    UUID, no amounts. ``recipient`` is the masked hint snapshotted when the alert was sent.
    """

    delivery_status = serializers.CharField(read_only=True)
    recipient = serializers.CharField(source="recipient_hint", read_only=True)

    class Meta:
        model = AlertLog
        fields = ["id", "kind", "created_at", "delivery_status", "enrollment_id", "recipient"]
        read_only_fields = fields
