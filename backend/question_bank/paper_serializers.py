from rest_framework import serializers

from . import paper_services
from .models import BlueprintRule, PaperQuestion, PaperSection, Question, QuestionPaper


class BlueprintRuleSerializer(serializers.ModelSerializer):
    chapter_name = serializers.CharField(source="chapter.name", read_only=True, default="")
    description = serializers.SerializerMethodField()

    class Meta:
        model = BlueprintRule
        fields = ("id", "section", "count", "question_type", "difficulty", "chapter", "chapter_name", "description")
        read_only_fields = ("id",)

    def get_description(self, rule):
        return f"{rule.count} × {paper_services.describe_rule(rule)}"

    def validate(self, attrs):
        section = attrs.get("section", getattr(self.instance, "section", None))
        chapter = attrs.get("chapter", getattr(self.instance, "chapter", None))
        if chapter is not None and chapter.subject_id != section.paper.subject_id:
            raise serializers.ValidationError({"chapter": "That chapter belongs to another subject."})
        return attrs


class PaperItemSerializer(serializers.ModelSerializer):
    """A question in a paper as the builder shows it: no answers here (they are in the answer key)."""

    body = serializers.CharField(source="question.body", read_only=True)
    question_type = serializers.CharField(source="question.question_type", read_only=True)
    difficulty = serializers.CharField(source="question.difficulty", read_only=True)
    chapter_name = serializers.CharField(source="question.chapter.name", read_only=True, default="")
    question_status = serializers.CharField(source="question.status", read_only=True)

    class Meta:
        model = PaperQuestion
        fields = ("id", "section", "question", "question_version", "order", "marks", "body", "question_type", "difficulty",
                  "chapter_name", "question_status")
        read_only_fields = fields


class PaperSectionSerializer(serializers.ModelSerializer):
    rules = BlueprintRuleSerializer(many=True, read_only=True)
    items = PaperItemSerializer(many=True, read_only=True)

    class Meta:
        model = PaperSection
        fields = ("id", "paper", "order", "title", "instructions", "rules", "items")
        read_only_fields = ("id",)

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Give the section a title, such as Section A.")
        return value

    def validate_paper(self, paper):
        if self.instance is not None and paper.pk != self.instance.paper_id:
            raise serializers.ValidationError("A section cannot move to another paper.")
        return paper


class PaperSerializer(serializers.ModelSerializer):
    examination_name = serializers.CharField(source="examination.name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    level_name = serializers.CharField(source="subject.level.name", read_only=True)
    marks_so_far = serializers.SerializerMethodField()
    question_count = serializers.SerializerMethodField()
    is_released = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = QuestionPaper
        fields = ("id", "examination", "examination_name", "subject", "subject_name", "level_name", "set_label", "title",
                  "instructions", "total_marks", "duration_minutes", "allow_shared_questions", "status", "release_at",
                  "review_comment", "withdraw_reason", "marks_so_far", "question_count", "is_released", "is_mine",
                  "submitted_at", "approved_at", "released_at", "withdrawn_at", "created_at", "updated_at")
        read_only_fields = ("id", "status", "release_at", "review_comment", "withdraw_reason", "submitted_at",
                            "approved_at", "released_at", "withdrawn_at", "created_at", "updated_at")

    def get_marks_so_far(self, paper):
        return f"{paper_services.paper_marks(paper):.2f}"

    def get_question_count(self, paper):
        return paper.items.count()

    def get_is_released(self, paper):
        return paper_services.is_released(paper)

    def get_is_mine(self, paper):
        request = self.context.get("request")
        return bool(request and paper.prepared_by_user_id == request.user.id)

    def validate_set_label(self, value):
        value = value.strip().upper()
        if not value or len(value) > 10 or not value.replace("-", "").isalnum():
            raise serializers.ValidationError("Use a short label such as A or B.")
        return value

    def validate(self, attrs):
        if self.instance is not None:
            for field in ("examination", "subject"):
                if field in attrs and attrs[field].pk != getattr(self.instance, f"{field}_id"):
                    raise serializers.ValidationError({field: "This cannot change. Make a new paper."})
        examination = attrs.get("examination", getattr(self.instance, "examination", None))
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        total = attrs.get("total_marks", getattr(self.instance, "total_marks", None))
        paper_services.check_paper_fields(examination=examination, subject=subject, total_marks=total)
        label = attrs.get("set_label", getattr(self.instance, "set_label", "A"))
        clash = QuestionPaper.objects.filter(examination=examination, subject=subject, set_label=label).exclude(status="withdrawn")
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError({"set_label": f"Set {label} already exists for this subject in this examination."})
        return attrs


class AddQuestionSerializer(serializers.Serializer):
    section = serializers.PrimaryKeyRelatedField(queryset=PaperSection.objects.all())
    question = serializers.PrimaryKeyRelatedField(queryset=Question.objects.all())


class AutofillSerializer(serializers.Serializer):
    section = serializers.PrimaryKeyRelatedField(queryset=PaperSection.objects.all(), required=False, allow_null=True)


class CommentSerializer(serializers.Serializer):
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


class ReleaseAtSerializer(serializers.Serializer):
    release_at = serializers.DateTimeField(allow_null=True)

