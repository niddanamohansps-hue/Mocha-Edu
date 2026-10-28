from django.urls import path

from .views import (
    AlertLogListView,
    MarkAllNotificationsReadView,
    MarkNotificationReadView,
    NotificationListView,
    NotificationSettingsView,
    UnreadCountView,
)

from .push_views import PushKeyView, PushSubscriptionView, PushTestView

urlpatterns = [
    path("", NotificationListView.as_view(), name="notification-list"),
    path("unread-count/", UnreadCountView.as_view(), name="notification-unread-count"),
    path("<uuid:notification_id>/read/", MarkNotificationReadView.as_view(), name="notification-read"),
    path("mark-all-read/", MarkAllNotificationsReadView.as_view(), name="notification-mark-all-read"),
    path("settings/", NotificationSettingsView.as_view(), name="notification-settings"),
    path("alert-log/", AlertLogListView.as_view(), name="notification-alert-log"),
    path("push/key/", PushKeyView.as_view(), name="push-key"),
    path("push/", PushSubscriptionView.as_view(), name="push-subscription"),
    path("push/test/", PushTestView.as_view(), name="push-test"),
]
