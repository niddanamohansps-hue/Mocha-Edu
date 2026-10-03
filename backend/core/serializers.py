from rest_framework import serializers

from .models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Read-only projection of AuditLog for the audit log API. Deliberately
    excludes nothing sensitive is on the model to begin with - the
    `changes` JSON is whatever the calling view passed to log_action(),
    and a repo-wide audit (see views.py docstring) found no call site that
    puts passwords/tokens/secrets into it.
    """

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "actor_id",
            "actor_username",
            "action",
            "model_name",
            "object_id",
            "changes",
            "ip_address",
            "user_agent",
            "created_at",
        ]
        read_only_fields = fields
