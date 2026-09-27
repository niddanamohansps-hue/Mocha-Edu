from rest_framework import serializers

from .models import Notification


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
