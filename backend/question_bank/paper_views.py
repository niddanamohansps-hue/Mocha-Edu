from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.tenant_access import HasAnyPermission
from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from . import paper_services as svc
from .models import BlueprintRule, PaperAccessLog, PaperQuestion, PaperSection, QuestionPaper
from .paper_serializers import (
    AddQuestionSerializer,
    AutofillSerializer,
    BlueprintRuleSerializer,
    CommentSerializer,
    PaperSectionSerializer,
    PaperSerializer,
    ReasonSerializer,
    ReleaseAtSerializer,
)
from .serializers import QuestionSerializer
from .views import TenantOnlyMixin

PREPARE, APPROVE = "prepare_papers", "approve_papers"
# Teachers reach released papers of their subjects through view_examinations.
ANY_PAPER_ACCESS = (PREPARE, APPROVE, "view_examinations")


class PaperViewSet(TenantOnlyMixin, viewsets.ModelViewSet):
    serializer_class = PaperSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["examination", "subject", "status"]
    search_fields = ["title", "subject__name", "examination__name"]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]
    APPROVER_ACTIONS = ("approve", "send_back", "release", "withdraw", "access_log")

    def get_permissions(self):
        if self.action in ("list", "retrieve", "printable", "answer_key"):
            return [IsAuthenticated(), HasAnyPermission(*ANY_PAPER_ACCESS)]
        if self.action in self.APPROVER_ACTIONS:
            return [IsAuthenticated(), HasPermission(APPROVE)]
        if self.action == "schedule":
            return [IsAuthenticated(), HasAnyPermission(PREPARE, APPROVE)]
        return [IsAuthenticated(), HasPermission(PREPARE)]

    def get_queryset(self):
        return svc.visible_papers(self.request)

    def perform_create(self, serializer):
        paper = serializer.save(prepared_by_user_id=self.request.user.id)
        PaperSection.objects.create(paper=paper, order=1, title="Section A")
        log_action(self.request, action="paper_created", model_name="QuestionPaper", object_id=paper.pk,
                   changes={"examination": str(paper.examination_id), "subject": str(paper.subject_id), "set": paper.set_label})

    def perform_update(self, serializer):
        svc._require_draft(self.get_object())
        paper = serializer.save()
        log_action(self.request, action="paper_updated", model_name="QuestionPaper", object_id=paper.pk)

    def destroy(self, request, pk=None):
        paper = self.get_object()
        svc._require_draft(paper)
        if paper.submitted_at is not None:
            return Response({"error": "This paper has been submitted before. Withdraw it after approval instead."}, status=status.HTTP_400_BAD_REQUEST)
        paper_id = paper.pk
        paper.delete()
        log_action(request, action="paper_deleted", model_name="QuestionPaper", object_id=paper_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def retrieve(self, request, pk=None):
        paper = self.get_object()
        data = PaperSerializer(paper, context={"request": request}).data
        if svc.can_prepare(request) or svc.can_approve(request):
            sections = paper.sections.prefetch_related("rules__chapter", "items__question__chapter")
            data["sections"] = PaperSectionSerializer(sections, many=True).data
            data["problems"] = svc.problems(paper)
        return Response(data)

    def _done(self, request, paper, action_name, changes=None):
        log_action(request, action=action_name, model_name="QuestionPaper", object_id=paper.pk, changes=changes)
        return self.retrieve(request, pk=paper.pk)

    @action(detail=False, methods=["get"])
    def choices(self, request):
        """What a new paper can be for: examinations not yet published, and every subject."""
        from academics.models import Subject
        from examinations.models import Examination

        exams = Examination.objects.filter(is_published=False).order_by("-start_date")
        subjects = Subject.objects.select_related("level").order_by("level__order", "name")
        return Response({
            "examinations": [{"id": str(e.id), "name": e.name, "academic_year": e.academic_year} for e in exams],
            "subjects": [{"id": str(s.id), "name": s.name, "code": s.code, "level_name": s.level.name} for s in subjects],
        })

    @action(detail=True, methods=["get"])
    def candidates(self, request, pk=None):
        """Approved questions that may be added to this paper (filters: type, difficulty, chapter, search)."""
        paper = self.get_object()
        qs = svc.eligible_questions(paper).select_related("subject__level", "chapter", "topic", "author__profile")
        params = request.query_params
        for field in ("question_type", "difficulty", "chapter"):
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("search"):
            qs = qs.filter(body__icontains=params["search"])
        page = self.paginate_queryset(qs.order_by("chapter__order", "difficulty"))
        return self.get_paginated_response(QuestionSerializer(page, many=True, context={"request": request}).data)

    @action(detail=True, methods=["post"], url_path="questions")
    def add_question(self, request, pk=None):
        paper = self.get_object()
        serializer = AddQuestionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = svc.add_question(paper=paper, **serializer.validated_data)
        return self._done(request, paper, "paper_question_added", {"question": str(item.question_id)})

    @action(detail=True, methods=["delete"], url_path=r"questions/(?P<item_id>[^/.]+)")
    def remove_question(self, request, pk=None, item_id=None):
        paper = self.get_object()
        item = get_object_or_404(PaperQuestion, pk=item_id, paper=paper)
        svc.remove_question(item=item)
        return self._done(request, paper, "paper_question_removed", {"question": str(item.question_id)})

    @action(detail=True, methods=["post"])
    def autofill(self, request, pk=None):
        paper = self.get_object()
        serializer = AutofillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        section = serializer.validated_data.get("section")
        count = svc.autofill(paper=paper, section=section)
        return self._done(request, paper, "paper_autofilled", {"section": str(section.pk) if section else "all", "questions": count})

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        paper = svc.submit(request=request, paper=self.get_object())
        return self._done(request, paper, "paper_submitted")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        paper = svc.approve(request=request, paper=self.get_object())
        return self._done(request, paper, "paper_approved")

    @action(detail=True, methods=["post"], url_path="send-back")
    def send_back(self, request, pk=None):
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        paper = svc.send_back(request=request, paper=self.get_object(), comment=serializer.validated_data["comment"])
        return self._done(request, paper, "paper_sent_back", {"comment": paper.review_comment[:200]})

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        serializer = ReleaseAtSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        paper = svc.schedule_release(paper=self.get_object(), release_at=serializer.validated_data["release_at"])
        return self._done(request, paper, "paper_release_scheduled", {"release_at": str(paper.release_at)})

    @action(detail=True, methods=["post"])
    def release(self, request, pk=None):
        paper = svc.release(paper=self.get_object())
        return self._done(request, paper, "paper_released")

    @action(detail=True, methods=["post"])
    def withdraw(self, request, pk=None):
        serializer = ReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        paper = svc.withdraw(paper=self.get_object(), reason=serializer.validated_data["reason"])
        return self._done(request, paper, "paper_withdrawn", {"reason": paper.withdraw_reason})

    def _content(self, request, kind, with_answers):
        paper = self.get_object()
        if not svc.may_open_content(request, paper):
            raise PermissionDenied("This paper has not been released yet.")
        svc.log_access(request, paper, kind)
        content = svc.content_for(paper)
        if not with_answers:
            for section in content["sections"]:
                for question in section["questions"]:
                    for key in ("correct", "answer", "explanation", "marking_scheme"):
                        question.pop(key, None)
        content.update({"status": paper.status, "is_frozen": paper.frozen_content is not None})
        return Response(content)

    @action(detail=True, methods=["get"])
    def printable(self, request, pk=None):
        return self._content(request, PaperAccessLog.Kind.PAPER, with_answers=False)

    @action(detail=True, methods=["get"], url_path="answer-key")
    def answer_key(self, request, pk=None):
        return self._content(request, PaperAccessLog.Kind.ANSWER_KEY, with_answers=True)

    @action(detail=True, methods=["get"], url_path="access-log")
    def access_log(self, request, pk=None):
        paper = self.get_object()
        from accounts.models import User

        rows = list(paper.access_log.all()[:200])
        names = dict(User.objects.filter(id__in={r.user_id for r in rows}).values_list("id", "username"))
        return Response([{"user": names.get(r.user_id, ""), "kind": r.kind, "status": r.status_at_access,
                          "at": r.created_at} for r in rows])


class DraftChildViewSet(TenantOnlyMixin, viewsets.GenericViewSet):
    """Sections and rules: only on a draft paper, only for preparers."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission(PREPARE)]

    def _check(self, paper):
        if not svc.visible_papers(self.request).filter(pk=paper.pk).exists():
            raise NotFound()
        svc._require_draft(paper)


class PaperSectionViewSet(DraftChildViewSet, mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin):
    serializer_class = PaperSectionSerializer
    queryset = PaperSection.objects.select_related("paper")
    http_method_names = ["post", "patch", "delete", "options"]

    def perform_create(self, serializer):
        self._check(serializer.validated_data["paper"])
        serializer.save()

    def perform_update(self, serializer):
        self._check(serializer.instance.paper)
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance.paper)
        instance.delete()


class BlueprintRuleViewSet(DraftChildViewSet, mixins.CreateModelMixin, mixins.DestroyModelMixin):
    serializer_class = BlueprintRuleSerializer
    queryset = BlueprintRule.objects.select_related("section__paper", "chapter")
    http_method_names = ["post", "delete", "options"]

    def perform_create(self, serializer):
        self._check(serializer.validated_data["section"].paper)
        serializer.save()

    def perform_destroy(self, instance):
        self._check(instance.section.paper)
        instance.delete()
