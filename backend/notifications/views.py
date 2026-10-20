from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import HasAnyPermission, IsTenantMember
from core.audit import log_action
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from .models import AlertLog, Notification, NotificationSettings
from .serializers import (
    AlertLogSerializer,
    MarkAllReadResponseSerializer,
    NotificationSerializer,
    NotificationSettingsSerializer,
    UnreadCountSerializer,
)


class NotificationPagination(PageNumberPagination):
    """
    The repository has no working pagination convention to reuse - the one
    existing call to self.paginate_queryset() (staff.views.StaffMemberViewSet)
    is a no-op today because no pagination_class is configured anywhere,
    globally or per-view (confirmed by a repo-wide search - zero hits for
    pagination_class/DEFAULT_PAGINATION_CLASS/PageNumberPagination before
    this file). This is DRF's own stock paginator with a sane page size -
    not a new pagination architecture, just turning on the built-in one
    for this endpoint only, without touching global settings or any other
    view's behavior.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListView(generics.ListAPIView):
    """
    GET /api/notifications/ - only the current user's own notifications,
    newest first, paginated. Never trusts any client-supplied recipient -
    always filters by request.user.id.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        return Notification.objects.filter(
            recipient_user_id=self.request.user.id
        ).order_by("-created_at")


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Notification.objects.filter(
            recipient_user_id=request.user.id, is_read=False
        ).count()
        return Response(UnreadCountSerializer({"unread_count": count}).data)


class MarkNotificationReadView(APIView):
    """
    POST /api/notifications/{id}/read/ - a notification that doesn't exist,
    or belongs to another user, returns 404 (never 403) so a response can
    never confirm whether some other user's notification exists.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification, id=notification_id, recipient_user_id=request.user.id
        )
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save(update_fields=["is_read", "read_at"])
        return Response(NotificationSerializer(notification).data)


class MarkAllNotificationsReadView(APIView):
    """POST /api/notifications/mark-all-read/ - scoped to the current
    user's own unread rows only, never able to affect anyone else's."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = Notification.objects.filter(
            recipient_user_id=request.user.id, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response(MarkAllReadResponseSerializer({"updated_count": updated}).data)


class NotificationSettingsView(APIView):
    """
    GET/PATCH /api/notifications/settings/ - this school's alert settings.

    GET never writes: with no saved row it returns the (all-off) defaults. The row is created
    by the first PATCH. Reading needs manage_notification_settings or view_notification_log;
    changing needs manage_notification_settings. No PUT/DELETE/POST.
    """

    http_method_names = ["get", "patch", "head", "options"]

    def get_permissions(self):
        base = [IsAuthenticated(), IsTenantMember()]
        if self.request.method == "PATCH":
            return base + [HasPermission("manage_notification_settings")]
        return base + [HasAnyPermission("manage_notification_settings", "view_notification_log")]

    def get(self, request):
        return Response(NotificationSettingsSerializer(NotificationSettings.load()).data)

    def patch(self, request):
        serializer = NotificationSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # The update commits (or fails) on its own. The audit entry is written afterwards,
        # exactly as the other settings views do: core.audit.log_action is best-effort and
        # swallows its own errors, so calling it inside this transaction could leave it
        # silently broken. A failed audit write never undoes the change; a rejected or failed
        # change never produces an audit entry.
        instance, previous = NotificationSettings.update_singleton(
            user_id=request.user.id, **serializer.validated_data
        )
        log_action(
            request,
            action="notification_settings_changed",
            model_name="NotificationSettings",
            object_id=instance.id,
            changes={"old": previous, "new": instance.editable_values()},
        )
        return Response(NotificationSettingsSerializer(instance).data)


class AlertLogListView(generics.ListAPIView):
    """
    GET /api/notifications/alert-log/ - read-only list of automated alerts, newest first.
    Requires view_notification_log. Filters: kind, created_after, created_before (UTC dates,
    inclusive), enrollment_id. Invalid filter values are a 400, never silently ignored.
    """

    http_method_names = ["get", "head", "options"]
    serializer_class = AlertLogSerializer
    pagination_class = StandardResultsPagination

    def get_permissions(self):
        return [IsAuthenticated(), IsTenantMember(), HasPermission("view_notification_log")]

    def get_queryset(self):
        params = self.request.query_params
        queryset = AlertLog.objects.select_related("outbox_event").order_by("-created_at", "-id")

        kind = params.get("kind")
        if kind:
            if kind not in AlertLog.Kind.values:
                raise ValidationError({"kind": [f"Unknown kind. Use one of: {', '.join(AlertLog.Kind.values)}."]})
            queryset = queryset.filter(kind=kind)

        for name, lookup in (("created_after", "created_at__date__gte"), ("created_before", "created_at__date__lte")):
            raw = params.get(name)
            if raw:
                try:
                    # parse_date raises ValueError for well-formed but impossible dates (2026-13-45).
                    parsed = parse_date(raw) if len(raw) == 10 else None
                except ValueError:
                    parsed = None
                if parsed is None:
                    raise ValidationError({name: ["Use a valid date in YYYY-MM-DD format."]})
                queryset = queryset.filter(**{lookup: parsed})

        enrollment_id = (params.get("enrollment_id") or "").strip()
        if enrollment_id:
            queryset = queryset.filter(enrollment_id=enrollment_id[:50])

        return queryset
