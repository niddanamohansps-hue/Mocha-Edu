from rest_framework import serializers

from academics.models import Subject

from .models import Chapter, Question, QuestionReview, QuestionVersion, SubjectReviewer, Topic


def person_name(staff):
    if staff is None:
        return ""
    profile = staff.profile
    return f"{profile.first_name} {profile.last_name}".strip()


class TopicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Topic
        fields = ("id", "chapter", "name", "order", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the topic name.")
        return value

    def validate_chapter(self, chapter):
        if self.instance is not None and chapter.pk != self.instance.chapter_id:
            raise serializers.ValidationError("A topic cannot move to another chapter.")
        return chapter


class ChapterSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    topics = TopicSerializer(many=True, read_only=True)

    class Meta:
        model = Chapter
        fields = ("id", "subject", "subject_name", "name", "order", "topics", "created_at")
        read_only_fields = ("id", "created_at")

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the chapter name.")
        return value

    def validate_subject(self, subject):
        if self.instance is not None and subject.pk != self.instance.subject_id:
            raise serializers.ValidationError("A chapter cannot move to another subject.")
        return subject


class SubjectReviewerSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    level_name = serializers.CharField(source="subject.level.name", read_only=True)
    staff_name = serializers.SerializerMethodField()

    class Meta:
        model = SubjectReviewer
        fields = ("id", "subject", "subject_name", "level_name", "staff", "staff_name", "created_at")
        read_only_fields = ("id", "created_at")

    def get_staff_name(self, row):
        return person_name(row.staff)

    def validate_staff(self, staff):
        if not staff.is_active:
            raise serializers.ValidationError("Choose a staff member who is still working here.")
        if not staff.profile.user_id:
            raise serializers.ValidationError("This staff member has no login, so they could not review.")
        return staff


class QuestionSerializer(serializers.ModelSerializer):
    """Read shape. Answers and marking schemes are included: only staff can reach this API."""

    subject_name = serializers.CharField(source="subject.name", read_only=True)
    level_name = serializers.CharField(source="subject.level.name", read_only=True)
    chapter_name = serializers.CharField(source="chapter.name", read_only=True, default="")
    topic_name = serializers.CharField(source="topic.name", read_only=True, default="")
    author_name = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    times_used = serializers.SerializerMethodField()
    last_used_in = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ("id", "subject", "subject_name", "level_name", "chapter", "chapter_name", "topic", "topic_name",
                  "question_type", "difficulty", "marks", "body", "options", "answer", "explanation", "marking_scheme",
                  "learning_outcome", "status", "version", "author_name", "is_mine", "times_used", "last_used_in",
                  "submitted_at", "decided_at", "created_at", "updated_at")
        read_only_fields = fields

    def get_author_name(self, question):
        return person_name(question.author)

    def get_is_mine(self, question):
        request = self.context.get("request")
        return bool(request and question.created_by_user_id == request.user.id)

    def _uses(self, question):
        """Papers that used the question and were approved (withdrawn ones still count: they may have been seen)."""
        return question.paper_items.filter(paper__status__in=["approved", "released", "withdrawn"]).select_related("paper__examination")

    def get_times_used(self, question):
        return self._uses(question).count()

    def get_last_used_in(self, question):
        item = self._uses(question).order_by("-paper__approved_at").first()
        return f"{item.paper.examination.name} (Set {item.paper.set_label})" if item else ""


class QuestionInputSerializer(serializers.Serializer):
    """What a teacher may set. Status, version, author and hashes are never accepted from the client."""

    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    chapter = serializers.PrimaryKeyRelatedField(queryset=Chapter.objects.all(), required=False, allow_null=True)
    topic = serializers.PrimaryKeyRelatedField(queryset=Topic.objects.all(), required=False, allow_null=True)
    question_type = serializers.ChoiceField(choices=Question.Type.choices)
    difficulty = serializers.ChoiceField(choices=Question.Difficulty.choices, required=False)
    marks = serializers.DecimalField(max_digits=5, decimal_places=2, min_value=0)
    body = serializers.CharField(max_length=5000, trim_whitespace=True)
    options = serializers.ListField(child=serializers.DictField(), required=False, max_length=8)
    answer = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    explanation = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    marking_scheme = serializers.CharField(max_length=5000, required=False, allow_blank=True)
    learning_outcome = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate(self, attrs):
        unknown = sorted(set(self.initial_data) - set(self.fields))
        if unknown:
            raise serializers.ValidationError({"non_field_errors": [f"These fields cannot be set: {', '.join(unknown)}."]})
        return attrs


class ReviewInputSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=QuestionReview.Decision.choices)
    comment = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class QuestionVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionVersion
        fields = ("id", "number", "content", "created_at")
        read_only_fields = fields


class QuestionReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = QuestionReview
        fields = ("id", "version", "decision", "comment", "reviewer_name", "created_at")
        read_only_fields = fields

    def get_reviewer_name(self, review):
        return person_name(review.reviewer)
