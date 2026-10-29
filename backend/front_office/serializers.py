from rest_framework import serializers
from .models import VisitorLog, StudentGatePass, PostalRecord
from .services import generate_visitor_pass_number, generate_gate_pass_number


class VisitorLogSerializer(serializers.ModelSerializer):
    purpose_display = serializers.CharField(source="get_purpose_display", read_only=True)
    person_to_meet_staff_name = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    student_enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)

    class Meta:
        model = VisitorLog
        fields = [
            "id",
            "pass_number",
            "visitor_name",
            "phone",
            "id_proof_type",
            "id_proof_number",
            "organization",
            "purpose",
            "purpose_display",
            "purpose_details",
            "person_to_meet_staff",
            "person_to_meet_staff_name",
            "person_to_meet_name",
            "student",
            "student_name",
            "student_enrollment_id",
            "number_of_visitors",
            "badge_number",
            "vehicle_number",
            "check_in_time",
            "check_out_time",
            "status",
            "remarks",
            "created_by_user_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "pass_number",
            "check_out_time",
            "created_by_user_id",
            "created_at",
            "updated_at",
        ]

    def get_person_to_meet_staff_name(self, obj):
        if obj.person_to_meet_staff and hasattr(obj.person_to_meet_staff, "profile"):
            p = obj.person_to_meet_staff.profile
            return f"{p.first_name} {p.last_name}".strip()
        return obj.person_to_meet_name or ""

    def get_student_name(self, obj):
        if obj.student and hasattr(obj.student, "profile"):
            p = obj.student.profile
            return f"{p.first_name} {p.last_name}".strip()
        return ""

    def create(self, validated_data):
        if "pass_number" not in validated_data or not validated_data["pass_number"]:
            validated_data["pass_number"] = generate_visitor_pass_number()

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by_user_id"] = request.user.id

        return super().create(validated_data)


class StudentGatePassSerializer(serializers.ModelSerializer):
    reason_category_display = serializers.CharField(source="get_reason_category_display", read_only=True)
    relationship_display = serializers.CharField(source="get_relationship_display", read_only=True)
    student_name = serializers.SerializerMethodField()
    student_enrollment_id = serializers.CharField(source="student.enrollment_id", read_only=True)
    student_class_section = serializers.SerializerMethodField()
    authorized_by_staff_name = serializers.SerializerMethodField()

    class Meta:
        model = StudentGatePass
        fields = [
            "id",
            "pass_number",
            "student",
            "student_name",
            "student_enrollment_id",
            "student_class_section",
            "departure_date",
            "departure_time",
            "actual_exit_time",
            "reason_category",
            "reason_category_display",
            "reason_details",
            "picked_up_by_name",
            "relationship",
            "relationship_display",
            "picked_up_by_phone",
            "authorized_by_staff",
            "authorized_by_staff_name",
            "status",
            "gate_security_note",
            "created_by_user_id",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "pass_number",
            "actual_exit_time",
            "created_by_user_id",
            "created_at",
            "updated_at",
        ]

    def get_student_name(self, obj):
        if obj.student and hasattr(obj.student, "profile"):
            p = obj.student.profile
            return f"{p.first_name} {p.last_name}".strip()
        return ""

    def get_student_class_section(self, obj):
        if obj.student:
            enr = obj.student.enrollments.filter(is_current=True).select_related("level", "section").first()
            if enr:
                lvl = enr.level.name if enr.level else ""
                sec = f" - {enr.section.name}" if enr.section else ""
                return f"{lvl}{sec}".strip()
        return ""

    def get_authorized_by_staff_name(self, obj):
        if obj.authorized_by_staff and hasattr(obj.authorized_by_staff, "profile"):
            p = obj.authorized_by_staff.profile
            return f"{p.first_name} {p.last_name}".strip()
        return ""

    def create(self, validated_data):
        if "pass_number" not in validated_data or not validated_data["pass_number"]:
            validated_data["pass_number"] = generate_gate_pass_number()

        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by_user_id"] = request.user.id

        return super().create(validated_data)


class PostalRecordSerializer(serializers.ModelSerializer):
    record_type_display = serializers.CharField(source="get_record_type_display", read_only=True)
    recipient_staff_name = serializers.SerializerMethodField()

    class Meta:
        model = PostalRecord
        fields = [
            "id",
            "tracking_number",
            "record_type",
            "record_type_display",
            "title",
            "from_title",
            "to_title",
            "courier_company",
            "dispatch_date",
            "reference_number",
            "recipient_staff",
            "recipient_staff_name",
            "notes",
            "created_by_user_id",
            "created_at",
        ]
        read_only_fields = ["id", "created_by_user_id", "created_at"]

    def get_recipient_staff_name(self, obj):
        if obj.recipient_staff and hasattr(obj.recipient_staff, "profile"):
            p = obj.recipient_staff.profile
            return f"{p.first_name} {p.last_name}".strip()
        return ""

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            validated_data["created_by_user_id"] = request.user.id
        return super().create(validated_data)

