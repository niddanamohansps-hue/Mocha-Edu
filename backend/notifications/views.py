from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Notification
from .serializers import (
    MarkAllReadResponseSerializer,
    NotificationSerializer,
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
