"""
Homework API (homework/services.py has the access rules).

Staff (view_homework / manage_homework):
- GET  /api/homework/?section=&subject=&from=&to=     homework they may see, newest first (paginated)
- POST /api/homework/                                  {section, subject, title, details, due_date}
- PATCH /api/homework/<id>/  ·  POST /api/homework/<id>/cancel/
- POST /api/homework/<id>/attachments/  (file)  ·  DELETE /api/homework/<id>/attachments/<att_id>/
- GET  /api/homework/<id>/progress/                    each student in the section: seen / done
- GET  /api/homework/overview/?date=                    per section: homework set that day; sections without any
Students and parents (view_own_homework / view_child_homework):
- GET  /api/homework/my/?student=<child>&days=          current and upcoming homework with own progress
- POST /api/homework/<id>/mark/ {student?, done}        mark seen (always) and done / not done
"""
from datetime import datetime, timedelta

from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404

from core.dates import school_today
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import HasAnyPermission
from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from .models import Homework, HomeworkAttachment, HomeworkProgress
from .services import (
    can_set_for,
    created_by_for,
    current_section_id,
    mark,
    notify_new_homework,
    staff_sections,
    student_for_request,
)

MAX_FILES = 3
MAX_FILE_BYTES = 10 * 1024 * 1024
ALLOWED = (".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt")


class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeworkAttachment
        fields = ["id", "original_name", "size", "created_at"]


class HomeworkSerializer(serializers.ModelSerializer):
    section_name = serializers.SerializerMethodField()
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    created_by_name = serializers.SerializerMethodField()
    attachments = AttachmentSerializer(many=True, read_only=True)

    class Meta:
        model = Homework
        fields = ["id", "section", "section_name", "subject", "subject_name", "title", "details", "assigned_on",
                  "due_date", "status", "created_by_name", "attachments", "created_at"]
        read_only_fields = ["id", "assigned_on", "status", "created_at"]

    def get_section_name(self, obj):
        return f"{obj.section.level.name} {obj.section.name}"

    def get_created_by_name(self, obj):
        profile = obj.created_by.profile if obj.created_by_id else None
        return f"{profile.first_name} {profile.last_name}".strip() if profile else ""

    def validate(self, attrs):
        title = (attrs.get("title") or getattr(self.instance, "title", "")).strip()
        if not title:
            raise serializers.ValidationError({"title": "Give the homework a title."})
        due = attrs.get("due_date") or getattr(self.instance, "due_date", None)
        if due and due < school_today() and (self.instance is None or "due_date" in attrs):
            raise serializers.ValidationError({"due_date": "The due date cannot be in the past."})
        return attrs


def _base_queryset():
    return Homework.objects.select_related("section__level", "subject", "created_by__profile").prefetch_related("attachments")


class HomeworkListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), HasPermission("manage_homework")]
        return [IsAuthenticated(), HasAnyPermission("view_homework", "manage_homework")]

    def get(self, request):
        qs = _base_queryset()
        allowed = staff_sections(request)
        if allowed is not None:
            qs = qs.filter(section_id__in=allowed)
        params = request.query_params
        for key, field in (("section", "section_id"), ("subject", "subject_id")):
            if params.get(key):
                qs = qs.filter(**{field: params[key]})
        if params.get("from"):
            qs = qs.filter(assigned_on__gte=params["from"])
        if params.get("to"):
            qs = qs.filter(assigned_on__lte=params["to"])
        if params.get("status") in ("active", "cancelled"):
            qs = qs.filter(status=params["status"])
        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        data = HomeworkSerializer(page, many=True).data
        counts = {str(row["homework_id"]): row for row in HomeworkProgress.objects.filter(homework__in=page)
                  .values("homework_id").annotate(seen=Count("seen_at"), done=Count("done_at"))}
        for item in data:
            row = counts.get(str(item["id"]), {})
            item["seen_count"], item["done_count"] = row.get("seen", 0), row.get("done", 0)
        return paginator.get_paginated_response(data)

    def post(self, request):
        serializer = HomeworkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        if not can_set_for(request, data["section"].id, data["subject"].id):
            return Response({"error": "You can only set homework for your own classes and subjects."},
                            status=status.HTTP_403_FORBIDDEN)
        if data["subject"].level_id != data["section"].level_id:
            return Response({"subject": ["This subject is not taught in that class."]}, status=status.HTTP_400_BAD_REQUEST)
        homework = serializer.save(assigned_on=school_today(), created_by=created_by_for(request))
        transaction.on_commit(lambda: notify_new_homework(homework))
        log_action(request, action="homework_created", model_name="Homework", object_id=homework.id,
                   changes={"section": str(homework.section_id), "due_date": str(homework.due_date)})
        return Response(HomeworkSerializer(_base_queryset().get(pk=homework.pk)).data, status=status.HTTP_201_CREATED)


def _editable(request, pk):
    homework = get_object_or_404(_base_queryset(), pk=pk)
    if not can_set_for(request, homework.section_id, homework.subject_id):
        return None
    return homework


class HomeworkDetailView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_homework")]

    def patch(self, request, pk):
        homework = _editable(request, pk)
        if homework is None:
            return Response({"error": "You can only change homework for your own classes."}, status=status.HTTP_403_FORBIDDEN)
        data = {k: v for k, v in request.data.items() if k in ("title", "details", "due_date")}
        serializer = HomeworkSerializer(homework, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        log_action(request, action="homework_updated", model_name="Homework", object_id=homework.id, changes=list(data))
        return Response(HomeworkSerializer(_base_queryset().get(pk=homework.pk)).data)


class HomeworkCancelView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_homework")]

    def post(self, request, pk):
        homework = _editable(request, pk)
        if homework is None:
            return Response({"error": "You can only change homework for your own classes."}, status=status.HTTP_403_FORBIDDEN)
        homework.status = Homework.CANCELLED
        homework.save(update_fields=["status", "updated_at"])
        log_action(request, action="homework_cancelled", model_name="Homework", object_id=homework.id, changes={})
        return Response(HomeworkSerializer(homework).data)


class AttachmentView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [IsAuthenticated()]
        return [IsAuthenticated(), HasPermission("manage_homework")]

    def post(self, request, pk):
        from students.antivirus import scan_file_for_malware

        homework = _editable(request, pk)
        if homework is None:
            return Response({"error": "You can only change homework for your own classes."}, status=status.HTTP_403_FORBIDDEN)
        upload = request.FILES.get("file")
        if upload is None:
            return Response({"error": "Choose a file."}, status=status.HTTP_400_BAD_REQUEST)
        if homework.attachments.count() >= MAX_FILES:
            return Response({"error": f"At most {MAX_FILES} files per homework."}, status=status.HTTP_400_BAD_REQUEST)
        if upload.size > MAX_FILE_BYTES:
            return Response({"error": "Files can be at most 10 MB."}, status=status.HTTP_400_BAD_REQUEST)
        if not upload.name.lower().endswith(ALLOWED):
            return Response({"error": "Allowed files: PDF, images, Word, Excel, PowerPoint, text."},
                            status=status.HTTP_400_BAD_REQUEST)
        clean, _, _ = scan_file_for_malware(upload, upload.name)
        if not clean:
            return Response({"error": "The file could not be accepted (virus check failed)."}, status=status.HTTP_400_BAD_REQUEST)
        upload.seek(0)
        attachment = HomeworkAttachment.objects.create(homework=homework, file=upload,
                                                       original_name=upload.name[-255:], size=upload.size)
        return Response(AttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)

    def delete(self, request, pk, attachment_id):
        homework = _editable(request, pk)
        if homework is None:
            return Response({"error": "You can only change homework for your own classes."}, status=status.HTTP_403_FORBIDDEN)
        attachment = get_object_or_404(HomeworkAttachment, pk=attachment_id, homework=homework)
        attachment.file.delete(save=False)
        attachment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def get(self, request, pk, attachment_id):
        """Download: staff who may see the section, or the student / parent of a student in it."""
        homework = get_object_or_404(Homework, pk=pk)
        attachment = get_object_or_404(HomeworkAttachment, pk=attachment_id, homework=homework)
        if not _may_read(request, homework):
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        return FileResponse(attachment.file.open("rb"), as_attachment=True, filename=attachment.original_name)


def _may_read(request, homework):
    if HasAnyPermission("view_homework", "manage_homework").has_permission(request, None):
        allowed = staff_sections(request)
        if allowed is None or homework.section_id in allowed:
            return True
    student = student_for_request(request, request.query_params.get("student"))
    return bool(student and current_section_id(student) == homework.section_id)


class ProgressView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasAnyPermission("view_homework", "manage_homework")]

    def get(self, request, pk):
        from students.models import StudentLevel

        homework = get_object_or_404(Homework, pk=pk)
        allowed = staff_sections(request)
        if allowed is not None and homework.section_id not in allowed:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        progress = {p.student_id: p for p in HomeworkProgress.objects.filter(homework=homework)}
        students = (StudentLevel.objects.filter(section_id=homework.section_id, is_current=True, student__status="active")
                    .select_related("student__profile").order_by("student__profile__first_name"))
        rows = []
        for level in students:
            p = progress.get(level.student_id)
            rows.append({"student": str(level.student_id), "enrollment_id": level.student.enrollment_id,
                         "name": f"{level.student.profile.first_name} {level.student.profile.last_name}".strip(),
                         "seen_at": p.seen_at if p else None, "done_at": p.done_at if p else None})
        return Response({"homework": HomeworkSerializer(homework).data, "students": rows,
                         "seen": sum(1 for r in rows if r["seen_at"]), "done": sum(1 for r in rows if r["done_at"])})


class OverviewView(APIView):
    """Per section, how much homework was set on a day: shows classes that got none."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_homework")]

    def get(self, request):
        from academics.models import Section

        try:
            day = datetime.strptime(request.query_params.get("date", ""), "%Y-%m-%d").date()
        except ValueError:
            day = school_today()
        sections = (Section.objects.select_related("level")
                    .annotate(count=Count("homework", filter=Q(homework__assigned_on=day, homework__status=Homework.ACTIVE)))
                    .order_by("level__order", "level__name", "name"))
        allowed = staff_sections(request)
        if allowed is not None:  # a teacher sees only their own classes
            sections = sections.filter(id__in=allowed)
        rows = [{"section": str(s.id), "name": f"{s.level.name} {s.name}", "homework": s.count} for s in sections]
        return Response({"date": day, "sections": rows, "without_homework": sum(1 for r in rows if not r["homework"])})


class MyHomeworkView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasAnyPermission("view_own_homework", "view_child_homework")]

    def get(self, request):
        student = student_for_request(request, request.query_params.get("student"))
        if student is None:
            return Response({"error": "No student found for this account."}, status=status.HTTP_404_NOT_FOUND)
        section_id = current_section_id(student)
        if section_id is None:
            return Response({"student": str(student.id), "homework": []})
        try:
            days = max(1, min(int(request.query_params.get("days", 14)), 60))
        except ValueError:
            days = 14
        today = school_today()
        items = list(_base_queryset().filter(section_id=section_id, status=Homework.ACTIVE,
                                             due_date__gte=today - timedelta(days=days), assigned_on__lte=today)
                     .order_by("due_date", "subject__name"))
        progress = {p.homework_id: p for p in HomeworkProgress.objects.filter(student=student, homework__in=items)}
        data = HomeworkSerializer(items, many=True).data
        for item, hw in zip(data, items):
            p = progress.get(hw.id)
            item["seen_at"] = p.seen_at if p else None
            item["done_at"] = p.done_at if p else None
            item["overdue"] = hw.due_date < today and not (p and p.done_at)
        return Response({"student": str(student.id), "homework": data})


class MarkView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasAnyPermission("view_own_homework", "view_child_homework")]

    def post(self, request, pk):
        homework = get_object_or_404(Homework, pk=pk, status=Homework.ACTIVE)
        student = student_for_request(request, request.data.get("student"))
        if student is None or current_section_id(student) != homework.section_id:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        done = request.data.get("done")
        progress = mark(homework, student, seen=True,
                        done=None if done is None else str(done).lower() in ("true", "1", "yes"))
        return Response({"seen_at": progress.seen_at, "done_at": progress.done_at})


class OptionsView(APIView):
    """GET /api/homework/options/: the class + subject pairs this user may set homework for."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("manage_homework")]

    def get(self, request):
        from academics.models import Section, Subject, SubjectAssignment

        from attendance.services import get_instructor_for_user, is_owner

        instructor = None if is_owner(request) else get_instructor_for_user(request.user)
        if instructor is not None:
            pairs = [(a.section, a.subject) for a in SubjectAssignment.objects.filter(instructor=instructor)
                     .select_related("section__level", "subject").order_by("section__level__order", "section__name", "subject__name")]
        else:
            subjects = {}
            for subject in Subject.objects.order_by("name"):
                subjects.setdefault(subject.level_id, []).append(subject)
            pairs = [(section, subject) for section in Section.objects.select_related("level").order_by("level__order", "name")
                     for subject in subjects.get(section.level_id, [])]
        return Response([{"section": str(s.id), "section_name": f"{s.level.name} {s.name}",
                          "subject": str(sub.id), "subject_name": sub.name} for s, sub in pairs])
