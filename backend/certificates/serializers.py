from rest_framework import serializers

from .models import Certificate, CertificateSettings


class CertificateSerializer(serializers.ModelSerializer):
    """Staff-facing representation (callers hold view_certificates)."""

    certificate_type_label = serializers.CharField(source="get_certificate_type_display", read_only=True)
    holder_name = serializers.SerializerMethodField()
    superseded_by_number = serializers.SerializerMethodField()
    supersedes_number = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = [
            "id", "certificate_type", "certificate_type_label", "certificate_number", "verification_id",
            "student", "staff_member", "holder_name", "issue_date", "academic_year", "period_start",
            "period_end", "leaving_date", "reason", "conduct", "internal_notes", "status",
            "issued_by_user_id", "approved_by_user_id", "issued_at", "cancelled_by_user_id", "cancelled_at",
            "cancellation_reason", "supersedes", "supersedes_number", "superseded_by_number", "reissue_reason",
        ]
        read_only_fields = fields

    def get_holder_name(self, obj):
        return obj.snapshot.get("holder_name", "")

    def get_superseded_by_number(self, obj):
        return obj.superseded_by.certificate_number if hasattr(obj, "superseded_by") else None

    def get_supersedes_number(self, obj):
        return obj.supersedes.certificate_number if obj.supersedes_id else None


class CertificateBasicSerializer(CertificateSerializer):
    """What a holder of view_certificates alone sees on one certificate: no
    internal notes, no internal user/record ids, no verification id. The
    snapshot (which can hold a date of birth) is never serialized at all; it
    is only printed on the PDF."""

    class Meta(CertificateSerializer.Meta):
        fields = [
            "id", "certificate_type", "certificate_type_label", "certificate_number", "holder_name", "issue_date",
            "academic_year", "period_start", "period_end", "leaving_date", "reason", "conduct", "status",
            "issued_at", "cancelled_at", "cancellation_reason", "supersedes_number", "superseded_by_number",
            "reissue_reason",
        ]
        read_only_fields = fields


class CertificateListSerializer(CertificateSerializer):
    """List rows: identification and status only."""

    class Meta(CertificateSerializer.Meta):
        fields = [
            "id", "certificate_type", "certificate_type_label", "certificate_number", "holder_name", "issue_date",
            "academic_year", "status", "supersedes_number", "superseded_by_number",
        ]
        read_only_fields = fields


class IssueSerializer(serializers.Serializer):
    certificate_type = serializers.ChoiceField(choices=Certificate.Type.choices)
    student_id = serializers.UUIDField(required=False)
    staff_id = serializers.UUIDField(required=False)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
    conduct = serializers.CharField(max_length=100, required=False, allow_blank=True)
    academic_year = serializers.CharField(max_length=20, required=False, allow_blank=True)
    leaving_date = serializers.DateField(required=False, allow_null=True)
    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)
    internal_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)

    def validate(self, attrs):
        is_student_type = attrs["certificate_type"] in Certificate.STUDENT_TYPES
        if is_student_type and not attrs.get("student_id"):
            raise serializers.ValidationError({"student_id": "Select a student."})
        if not is_student_type and not attrs.get("staff_id"):
            raise serializers.ValidationError({"staff_id": "Select a staff member."})
        return attrs


class ReissueSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)
    conduct = serializers.CharField(max_length=100, required=False, allow_blank=True)
    academic_year = serializers.CharField(max_length=20, required=False, allow_blank=True)
    leaving_date = serializers.DateField(required=False, allow_null=True)
    period_start = serializers.DateField(required=False, allow_null=True)
    period_end = serializers.DateField(required=False, allow_null=True)
    internal_notes = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    # Corrected reason-for-leaving / purpose, kept apart from the reissue reason.
    new_reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class CertificateSettingsSerializer(serializers.ModelSerializer):
    has_signature = serializers.SerializerMethodField()

    class Meta:
        model = CertificateSettings
        fields = ["signatory_name", "signatory_title", "signature", "has_signature", "updated_at"]
        read_only_fields = ["updated_at", "has_signature"]
        extra_kwargs = {"signature": {"write_only": True, "required": False}}

    def get_has_signature(self, obj):
        return bool(obj.signature)
