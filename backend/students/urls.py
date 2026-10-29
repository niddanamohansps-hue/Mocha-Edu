from django.urls import path
from .views import (
    StudentEnrollmentView,
    StudentListView,
    PortalActivationView,
    CredentialDistributionView,
    StudentDetailView,
    PromotionCandidatesView,
    PromotionExecuteView,
    PromotionHistoryView,
    PromotionPreviewView,
    PromotionReverseView,
    UdiseExportView,
    CbseLocExportView,
)

urlpatterns = [
    path("enroll/", StudentEnrollmentView.as_view(), name="student-enroll"),
    path(
        "portal-activation/",
        PortalActivationView.as_view(),
        name="student-portal-activation",
    ),
    path("list/", StudentListView.as_view(), name="student-list"),
    path(
        "credentials/", CredentialDistributionView.as_view(), name="student-credentials"
    ),
    path("detail/<uuid:pk>/", StudentDetailView.as_view(), name="student-detail"),
    path(
        "promotion/candidates/",
        PromotionCandidatesView.as_view(),
        name="promotion-candidates",
    ),
    path("promotion/preview/", PromotionPreviewView.as_view(), name="promotion-preview"),
    path("promotion/execute/", PromotionExecuteView.as_view(), name="promotion-execute"),
    path("promotion/history/", PromotionHistoryView.as_view(), name="promotion-history"),
    path(
        "promotion/<uuid:record_id>/reverse/",
        PromotionReverseView.as_view(),
        name="promotion-reverse",
    ),
    path("export/udise/", UdiseExportView.as_view(), name="student-export-udise"),
    path("export/cbse-loc/", CbseLocExportView.as_view(), name="student-export-cbse-loc"),
]
