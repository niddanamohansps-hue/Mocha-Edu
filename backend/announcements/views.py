from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction
from django.db.models import Count
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from . import services
from .models import Announcement
from .serializers import (
    AnnouncementRecipientSerializer,
    AnnouncementSerializer,
    MyAnnouncementSerializer,
    ScheduleSerializer,
    to_drf_error,
)

EDITABLE_STATUSES = (Announcement.Status.DRAFT, Announcement.Status.SCHEDULED)


class AnnouncementViewSet(viewsets.ModelViewSet):
    serializer_class = AnnouncementSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["status", "audience_type"]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "published_at", "scheduled_at", "title"]
    ordering = ["-created_at", "-id"]

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Announcement.objects.select_related("audience_section", "audience_level")
            .annotate(recipient_count=Count("recipients"))
            .order_by("-created_at", "-id")
        )

    def get_permissions(self):
        # A custom get_permissions() overrides @action permission_classes, so
        # every action is listed here explicitly (same as examinations).
        if self.action in ("mine", "mine_detail"):
            return [IsAuthenticated()]
        if self.action in ("list", "retrieve"):
            return [IsAuthenticated(), HasPermission("view_announcements")]
        return [IsAuthenticated(), HasPermission("manage_announcements")]

    def _fresh(self, announcement_id):
        return self.get_queryset().get(id=announcement_id)

    def _run(self, operation, *args):
        try:
            return operation(*args)
        except DjangoValidationError as exc:
            raise to_drf_error(exc)

    def _check_broadcast_permission(self, request, announcement):
        if announcement.audience_type == Announcement.AudienceType.ALL:
            if not HasPermission("broadcast_announcements").has_permission(request, self):
                raise PermissionDenied("Broadcasting to everyone requires the broadcast_announcements permission.")

    # --- CRUD ----------------------------------------------------------------

    def perform_create(self, serializer):
        announcement = serializer.save(created_by_user_id=self.request.user.id, status=Announcement.Status.DRAFT)
        log_action(
            self.request, action="announcement_created", model_name="Announcement", object_id=announcement.id,
            changes={"title": announcement.title, "audience_type": announcement.audience_type},
        )

    def update(self, request, *args, **kwargs):
        # Lock the row so a concurrent publish/cancel cannot be overwritten by
        # this save (save() writes every column, including status).
        partial = kwargs.pop("partial", False)
        with transaction.atomic():
            announcement = Announcement.objects.select_for_update().get(id=self.get_object().id)
            if announcement.status not in EDITABLE_STATUSES:
                raise to_drf_error(
                    DjangoValidationError("Only a draft or scheduled announcement can be edited.")
                )
            serializer = self.get_serializer(announcement, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)

            if announcement.status == Announcement.Status.SCHEDULED:
                audience_fields = ("audience_type", "audience_section", "audience_level")
                for field in audience_fields:
                    if field in serializer.validated_data and serializer.validated_data[field] != getattr(announcement, field):
                        raise to_drf_error(
                            DjangoValidationError("Changing the audience of a scheduled announcement requires cancelling the schedule first.")
                        )
                # Enforce broadcast permission against the final audience if scheduled
                final_audience = serializer.validated_data.get("audience_type", announcement.audience_type)
                if final_audience == Announcement.AudienceType.ALL:
                    self._check_broadcast_permission(request, announcement)

            serializer.save()
        log_action(
            request, action="announcement_updated", model_name="Announcement", object_id=announcement.id,
            changes={"fields": sorted(request.data.keys())},
        )
        return Response(self.get_serializer(self._fresh(announcement.id)).data)

    def destroy(self, request, *args, **kwargs):
        """DRAFT is hard-deleted; PUBLISHED is archived (its recipient
        snapshots are kept); SCHEDULED must be cancelled first."""
        announcement_id = self.get_object().id
        with transaction.atomic():
            announcement = Announcement.objects.select_for_update().get(id=announcement_id)
            if announcement.status == Announcement.Status.DRAFT:
                announcement.delete()
                action_name = "announcement_deleted"
            elif announcement.status == Announcement.Status.PUBLISHED:
                self._run(services.archive_announcement, announcement_id)
                action_name = "announcement_archived"
            elif announcement.status == Announcement.Status.SCHEDULED:
                raise to_drf_error(DjangoValidationError("Cancel the scheduled announcement before deleting it."))
            else:
                raise to_drf_error(DjangoValidationError("This announcement is already archived."))
        log_action(request, action=action_name, model_name="Announcement", object_id=announcement_id)
        return Response(status=status.HTTP_204_NO_CONTENT)

    # --- Lifecycle actions -----------------------------------------------------

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        announcement = self.get_object()
        self._check_broadcast_permission(request, announcement)
        self._run(services.publish_announcement, announcement.id, request.user)
        fresh = self._fresh(announcement.id)
        log_action(
            request, action="announcement_published", model_name="Announcement", object_id=announcement.id,
            changes={"audience_type": fresh.audience_type, "recipient_count": fresh.recipient_count},
        )
        return Response(self.get_serializer(fresh).data)

    @action(detail=True, methods=["post"])
    def schedule(self, request, pk=None):
        announcement = self.get_object()
        self._check_broadcast_permission(request, announcement)
        payload = ScheduleSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        self._run(services.schedule_announcement, announcement.id, payload.validated_data["scheduled_at"])
        log_action(
            request, action="announcement_scheduled", model_name="Announcement", object_id=announcement.id,
            changes={"scheduled_at": str(payload.validated_data["scheduled_at"])},
        )
        return Response(self.get_serializer(self._fresh(announcement.id)).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        announcement = self.get_object()
        self._run(services.cancel_schedule, announcement.id)
        log_action(request, action="announcement_schedule_cancelled", model_name="Announcement", object_id=announcement.id)
        return Response(self.get_serializer(self._fresh(announcement.id)).data)

    @action(detail=True, methods=["post"])
    def archive(self, request, pk=None):
        announcement = self.get_object()
        self._run(services.archive_announcement, announcement.id)
        log_action(request, action="announcement_archived", model_name="Announcement", object_id=announcement.id)
        return Response(self.get_serializer(self._fresh(announcement.id)).data)

    @action(detail=True, methods=["get"])
    def recipients(self, request, pk=None):
        announcement = self.get_object()
        page = self.paginate_queryset(announcement.recipients.order_by("created_at", "id"))
        return self.get_paginated_response(AnnouncementRecipientSerializer(page, many=True).data)

    @action(detail=False, methods=["get"])
    def mine(self, request):
        """Published announcements this user was a recipient of, from the
        persisted snapshot. Never filters by a client-supplied identity."""
        if connection.schema_name == "public":
            raise NotFound()
        queryset = Announcement.objects.filter(
            status=Announcement.Status.PUBLISHED, recipients__user_id=request.user.id
        ).order_by("-published_at", "-id")
        page = self.paginate_queryset(queryset)
        return self.get_paginated_response(MyAnnouncementSerializer(page, many=True).data)

    @action(detail=False, methods=["get"], url_path=r"mine/(?P<announcement_id>[0-9a-fA-F-]{36})", url_name="mine-detail")
    def mine_detail(self, request, announcement_id=None):
        """One published announcement the caller received. This is where the
        notification link (/dashboard/announcements/<id>) lands for students
        and parents, who hold no view_announcements permission and so cannot
        use the admin detail endpoint. Same snapshot rule as mine/: a user who
        was not a recipient gets 404, indistinguishable from a missing id."""
        if connection.schema_name == "public":
            raise NotFound()
        announcement = Announcement.objects.filter(
            id=announcement_id, status=Announcement.Status.PUBLISHED, recipients__user_id=request.user.id
        ).first()
        if announcement is None:
            raise NotFound()
        return Response(MyAnnouncementSerializer(announcement).data)
