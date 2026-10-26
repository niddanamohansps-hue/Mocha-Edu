from django.db import connection
from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import HasAnyPermission
from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from . import services
from .models import Chapter, Question, SubjectReviewer, Topic
from .serializers import (
    ChapterSerializer,
    QuestionInputSerializer,
    QuestionReviewSerializer,
    QuestionSerializer,
    QuestionVersionSerializer,
    ReviewInputSerializer,
    SubjectReviewerSerializer,
    TopicSerializer,
)

ANY_ACCESS = ("view_question_bank", "create_questions", "review_questions", "manage_question_bank")
MANAGE = "manage_question_bank"


class TenantOnlyMixin:
    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)


class SetupViewSet(TenantOnlyMixin, viewsets.ModelViewSet):
    """Chapters, topics and reviewers: anyone using the bank reads them; only a manager changes them."""

    audit_name = ""
    in_use_message = "This is in use and cannot be deleted."

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), HasAnyPermission(*ANY_ACCESS)]
        return [IsAuthenticated(), HasPermission(MANAGE)]

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, action=f"{self.audit_name}_created", model_name=type(obj).__name__, object_id=obj.pk)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, action=f"{self.audit_name}_updated", model_name=type(obj).__name__, object_id=obj.pk)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        model_name, pk = type(obj).__name__, obj.pk
        try:
            obj.delete()
        except ProtectedError:
            return Response({"error": self.in_use_message}, status=status.HTTP_409_CONFLICT)
        log_action(request, action=f"{self.audit_name}_deleted", model_name=model_name, object_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ChapterViewSet(SetupViewSet):
    serializer_class = ChapterSerializer
    queryset = Chapter.objects.select_related("subject").prefetch_related("topics")
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["subject"]
    pagination_class = None
    audit_name = "question_chapter"
    in_use_message = "Questions use this chapter. Move them to another chapter first."


class TopicViewSet(SetupViewSet):
    serializer_class = TopicSerializer
    queryset = Topic.objects.all()
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["chapter"]
    pagination_class = None
    audit_name = "question_topic"
    in_use_message = "Questions use this topic. Move them to another topic first."


class SubjectReviewerViewSet(SetupViewSet):
    serializer_class = SubjectReviewerSerializer
    queryset = SubjectReviewer.objects.select_related("subject__level", "staff__profile")
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["subject", "staff"]
    pagination_class = None
    http_method_names = ["get", "post", "delete", "head", "options"]
    audit_name = "question_reviewer"


class QuestionViewSet(TenantOnlyMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """The bank. What a person can see and do is decided per request in ``services`` (subject scope, author,
    reviewer); a question outside their scope is simply not found."""

    serializer_class = QuestionSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["subject", "chapter", "topic", "question_type", "difficulty", "status"]
    search_fields = ["body", "learning_outcome", "chapter__name", "topic__name"]
    ordering_fields = ["updated_at", "marks", "difficulty"]

    def get_permissions(self):
        return [IsAuthenticated(), HasAnyPermission(*ANY_ACCESS)]

    def get_queryset(self):
        queryset = services.visible_questions(self.request)
        params = self.request.query_params
        if params.get("mine") == "true":
            queryset = queryset.filter(created_by_user_id=self.request.user.id)
        if params.get("to_review") == "true":
            reviewable = services.reviewable_subject_ids(self.request)
            queryset = queryset.filter(status=Question.Status.SUBMITTED).exclude(created_by_user_id=self.request.user.id)
            if reviewable is not None:
                queryset = queryset.filter(subject_id__in=reviewable)
        return queryset

    def _input(self, partial=False):
        serializer = QuestionInputSerializer(data=self.request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def _out(self, question, code=status.HTTP_200_OK):
        question = Question.objects.select_related("subject__level", "chapter", "topic", "author__profile").get(pk=question.pk)
        return Response(QuestionSerializer(question, context={"request": self.request}).data, status=code)

    def create(self, request):
        question = services.create_question(request=request, data=self._input())
        log_action(request, action="question_created", model_name="Question", object_id=question.pk,
                   changes={"subject": str(question.subject_id), "type": question.question_type})
        return self._out(question, status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        question = services.update_question(request=request, question=self.get_object(), data=self._input(partial=True))
        log_action(request, action="question_updated", model_name="Question", object_id=question.pk, changes={"version": question.version})
        return self._out(question)

    def destroy(self, request, pk=None):
        question = self.get_object()
        question_id = question.pk
        services.delete_question(request=request, question=question)
        log_action(request, action="question_deleted", model_name="Question", object_id=question_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        question = services.submit_question(request=request, question=self.get_object())
        log_action(request, action="question_submitted", model_name="Question", object_id=question.pk, changes={"version": question.version})
        return self._out(question)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        serializer = ReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        question = services.review_question(request=request, question=self.get_object(), **serializer.validated_data)
        log_action(request, action=f"question_{serializer.validated_data['decision']}", model_name="Question", object_id=question.pk,
                   changes={"version": question.version, "comment": serializer.validated_data["comment"][:200]})
        return self._out(question)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        question = services.archive_question(request=request, question=self.get_object())
        log_action(request, action="question_archived", model_name="Question", object_id=question.pk)
        return self._out(question)

    @action(detail=True, methods=["get"])
    def history(self, request, pk=None):
        question = self.get_object()
        return Response({
            "versions": QuestionVersionSerializer(question.versions.all(), many=True).data,
            "reviews": QuestionReviewSerializer(question.reviews.select_related("reviewer__profile"), many=True).data,
        })


class MyScopeView(TenantOnlyMixin, APIView):
    """Which subjects the caller may write for and review, so the screens can offer the right choices."""

    def get_permissions(self):
        return [IsAuthenticated(), HasAnyPermission(*ANY_ACCESS)]

    def get(self, request):
        from academics.models import Subject

        def describe(ids):
            subjects = Subject.objects.select_related("level").order_by("level__order", "name")
            if ids is not None:
                subjects = subjects.filter(id__in=ids)
            return [{"id": str(s.id), "name": s.name, "code": s.code, "level_name": s.level.name} for s in subjects]

        return Response({
            "is_manager": services.is_manager(request),
            "can_write": describe(services.authorable_subject_ids(request)),
            "can_review": describe(services.reviewable_subject_ids(request)),
        })
