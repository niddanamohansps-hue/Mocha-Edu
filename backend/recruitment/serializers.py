from rest_framework import serializers

from .models import Applicant, ApplicantEvent, Interview, JobOpening
from .services import is_accepting_applications

MAX_RESUME_BYTES = 5 * 1024 * 1024

# The first bytes of each allowed format. The extension alone is only a claim, so a file named cv.pdf that is
# really something else is refused.
RESUME_SIGNATURES = {
    "pdf": (b"%PDF-",),
    "docx": (b"PK\x03\x04",),
    "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
}


def check_resume(value):
    if not value:
        return value
    if value.size > MAX_RESUME_BYTES:
        raise serializers.ValidationError("The resume must be 5 MB or smaller.")
    extension = value.name.rsplit(".", 1)[-1].lower() if "." in value.name else ""
    if extension not in RESUME_SIGNATURES:
        raise serializers.ValidationError("The resume must be a PDF, DOC or DOCX file.")
    head = value.read(8)
    value.seek(0)
    if not any(head.startswith(sig) for sig in RESUME_SIGNATURES[extension]):
        raise serializers.ValidationError("The file does not look like a valid " + extension.upper() + " document.")
    return value


class JobOpeningSerializer(serializers.ModelSerializer):
    applicant_count = serializers.SerializerMethodField()
    hired_count = serializers.SerializerMethodField()
    accepting_applications = serializers.SerializerMethodField()

    class Meta:
        model = JobOpening
        fields = [
            "id",
            "title",
            "position_type",
            "department",
            "specialization",
            "vacancies",
            "description",
            "requirements",
            "min_experience_years",
            "last_date",
            "status",
            "closed_at",
            "created_at",
            "applicant_count",
            "hired_count",
            "accepting_applications",
        ]
        # Status moves only through the publish/close actions, so every change is audited.
        read_only_fields = ["id", "status", "closed_at", "created_at"]

    def get_applicant_count(self, obj):
        # The list view annotates these; a freshly created opening has no annotation yet.
        value = getattr(obj, "applicant_count", None)
        return value if value is not None else obj.applicants.count()

    def get_hired_count(self, obj):
        value = getattr(obj, "hired_count", None)
        return value if value is not None else obj.applicants.filter(stage=Applicant.Stage.HIRED).count()

    def get_accepting_applications(self, obj):
        return is_accepting_applications(obj)

    def validate_vacancies(self, value):
        if value < 1:
            raise serializers.ValidationError("An opening needs at least one vacancy.")
        return value


class ApplicantEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicantEvent
        fields = ["id", "from_stage", "to_stage", "note", "actor_name", "created_at"]


class InterviewSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.SerializerMethodField()
    applicant_name = serializers.CharField(source="applicant.full_name", read_only=True)
    applicant_summary = serializers.SerializerMethodField()
    panel = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    # Staff ids to place on the panel. Sent on create and update; the panel becomes exactly this list.
    panelist_ids = serializers.ListField(child=serializers.UUIDField(), write_only=True, required=False)

    class Meta:
        model = Interview
        fields = [
            "id",
            "applicant",
            "applicant_name",
            "applicant_summary",
            "round_name",
            "scheduled_at",
            "mode",
            "location_or_url",
            "interviewer",
            "interviewer_name",
            "panel",
            "panelist_ids",
            "can_submit",
            "status",
            "score",
            "feedback",
            "created_at",
        ]
        # The score comes from the panel (or the complete action), never from a direct edit.
        read_only_fields = ["id", "status", "score", "feedback", "created_at"]

    def get_interviewer_name(self, obj):
        staff = obj.interviewer
        return f"{staff.profile.first_name} {staff.profile.last_name}".strip() if staff else None

    def get_applicant_summary(self, obj):
        applicant = obj.applicant
        return {
            "opening_title": applicant.opening.title,
            "qualification": applicant.qualification,
            "experience_years": applicant.experience_years,
            "current_employer": applicant.current_employer,
            "resume_url": f"/api/recruitment/interviews/{obj.id}/resume/" if applicant.resume else None,
        }

    def get_panel(self, obj):
        """Everyone sees who is on the panel and whether they have scored. Scores and comments are shown to HR
        always, to a panelist for their own entry, and to everyone once the interview is complete, so panelists
        cannot be swayed by one another before they have judged."""
        is_hr = self.context.get("is_hr", True)
        mine = self.context.get("my_staff_id")
        done = obj.status == Interview.Status.COMPLETED
        rows = []
        for p in obj.panelists.all():
            own = mine is not None and p.staff_id == mine
            reveal = is_hr or own or done
            rows.append(
                {
                    "id": p.id,
                    "staff": p.staff_id,
                    "name": f"{p.staff.profile.first_name} {p.staff.profile.last_name}".strip(),
                    "submitted": p.submitted_at is not None,
                    "is_me": own,
                    "score": p.score if reveal else None,
                    "feedback": p.feedback if reveal else "",
                }
            )
        return rows

    def get_can_submit(self, obj):
        mine = self.context.get("my_staff_id")
        if mine is None or obj.status != Interview.Status.SCHEDULED:
            return False
        return any(p.staff_id == mine and p.submitted_at is None for p in obj.panelists.all())

    def validate_applicant(self, value):
        if value.stage in (Applicant.Stage.HIRED, Applicant.Stage.REJECTED):
            raise serializers.ValidationError("Interviews cannot be scheduled for a hired or rejected applicant.")
        return value

    # panelist_ids is not a model field; the view applies it through set_panel() after the interview is saved.
    def create(self, validated_data):
        validated_data.pop("panelist_ids", None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("panelist_ids", None)
        return super().update(instance, validated_data)


class PanelistFeedbackSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=4, decimal_places=1, min_value=0, max_value=10)
    feedback = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class InterviewCompleteSerializer(serializers.Serializer):
    score = serializers.DecimalField(max_digits=4, decimal_places=1, min_value=0, max_value=10)
    feedback = serializers.CharField(required=False, allow_blank=True)


class ApplicantSerializer(serializers.ModelSerializer):
    opening_title = serializers.CharField(source="opening.title", read_only=True)
    full_name = serializers.CharField(read_only=True)
    resume_url = serializers.SerializerMethodField()
    average_score = serializers.SerializerMethodField()
    # Declared so the one-application-per-email constraint does not make the field mandatory; validate() enforces it.
    email = serializers.EmailField(required=False, allow_blank=True)

    class Meta:
        model = Applicant
        validators = []
        fields = [
            "id",
            "reference",
            "opening",
            "opening_title",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "gender",
            "date_of_birth",
            "address",
            "qualification",
            "experience_years",
            "current_employer",
            "expected_salary",
            "resume",
            "resume_url",
            "cover_note",
            "source",
            "stage",
            "stage_changed_at",
            "rejection_reason",
            "hired_staff",
            "average_score",
            "created_at",
        ]
        read_only_fields = ["id", "reference", "stage", "stage_changed_at", "rejection_reason", "hired_staff", "created_at"]
        extra_kwargs = {"resume": {"write_only": True}}

    def get_resume_url(self, obj):
        # Resumes are private: they are opened through this permission-checked endpoint, never by a /media/ URL.
        return f"/api/recruitment/applicants/{obj.id}/resume/" if obj.resume else None

    def get_average_score(self, obj):
        scores = [i.score for i in obj.interviews.all() if i.status == Interview.Status.COMPLETED and i.score is not None]
        return round(float(sum(scores)) / len(scores), 1) if scores else None

    def validate_resume(self, value):
        return check_resume(value)

    def validate_email(self, value):
        return (value or "").strip().lower()

    def validate(self, attrs):
        opening = attrs.get("opening") or getattr(self.instance, "opening", None)
        if self.instance is None:
            if opening is not None and not is_accepting_applications(opening):
                raise serializers.ValidationError({"opening": "This opening is not accepting applications."})
        elif "opening" in attrs and attrs["opening"].pk != self.instance.opening_id:
            raise serializers.ValidationError({"opening": "An application cannot be moved to another opening."})
        email = attrs.get("email", getattr(self.instance, "email", ""))
        if email and opening is not None:
            clash = Applicant.objects.filter(opening=opening, email=email)
            if self.instance is not None:
                clash = clash.exclude(pk=self.instance.pk)
            if clash.exists():
                raise serializers.ValidationError({"email": "This person has already applied to this opening."})
        return attrs


class StageMoveSerializer(serializers.Serializer):
    stage = serializers.ChoiceField(choices=Applicant.Stage.choices)
    note = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)


class HireSerializer(serializers.Serializer):
    joining_date = serializers.DateField(required=False, allow_null=True)
    gender = serializers.ChoiceField(choices=Applicant.Gender.choices, required=False)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    department = serializers.CharField(max_length=100, required=False, allow_blank=True)
    specialization = serializers.CharField(max_length=100, required=False, allow_blank=True)


class PublicOpeningSerializer(serializers.ModelSerializer):
    """What a visitor to the careers page may see: nothing about applicants or internal counts."""

    class Meta:
        model = JobOpening
        fields = [
            "id",
            "title",
            "position_type",
            "department",
            "specialization",
            "description",
            "requirements",
            "min_experience_years",
            "last_date",
        ]


class PublicApplySerializer(serializers.Serializer):
    opening = serializers.PrimaryKeyRelatedField(queryset=JobOpening.objects.all())
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20)
    gender = serializers.ChoiceField(choices=Applicant.Gender.choices, required=False, allow_blank=True)
    qualification = serializers.CharField(max_length=255, required=False, allow_blank=True)
    experience_years = serializers.IntegerField(min_value=0, max_value=60, required=False, default=0)
    current_employer = serializers.CharField(max_length=200, required=False, allow_blank=True)
    expected_salary = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, allow_null=True
    )
    cover_note = serializers.CharField(max_length=2000, required=False, allow_blank=True)
    resume = serializers.FileField(required=False, allow_null=True)

    def validate_email(self, value):
        return value.strip().lower()

    def validate_resume(self, value):
        return check_resume(value)

    def validate_opening(self, value):
        # The same answer for a draft, closed or expired opening, so nothing is learned from the error.
        if not is_accepting_applications(value):
            raise serializers.ValidationError("This position is not accepting applications.")
        return value
