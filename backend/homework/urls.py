from django.urls import path

from .views import (
    AttachmentView,
    HomeworkCancelView,
    HomeworkDetailView,
    HomeworkListCreateView,
    MarkView,
    MyHomeworkView,
    OptionsView,
    OverviewView,
    ProgressView,
)

urlpatterns = [
    path("", HomeworkListCreateView.as_view(), name="homework-list"),
    path("my/", MyHomeworkView.as_view(), name="homework-my"),
    path("overview/", OverviewView.as_view(), name="homework-overview"),
    path("options/", OptionsView.as_view(), name="homework-options"),
    path("<uuid:pk>/", HomeworkDetailView.as_view(), name="homework-detail"),
    path("<uuid:pk>/cancel/", HomeworkCancelView.as_view(), name="homework-cancel"),
    path("<uuid:pk>/progress/", ProgressView.as_view(), name="homework-progress"),
    path("<uuid:pk>/mark/", MarkView.as_view(), name="homework-mark"),
    path("<uuid:pk>/attachments/", AttachmentView.as_view(), name="homework-attachments"),
    path("<uuid:pk>/attachments/<uuid:attachment_id>/", AttachmentView.as_view(), name="homework-attachment"),
]
