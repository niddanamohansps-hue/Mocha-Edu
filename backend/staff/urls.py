from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    StaffMemberViewSet,
    InstructorViewSet,
    InstructorOnboardingView,
    InstructorActivationView,
    CredentialDistributionView,
    StaffOnboardingView,
    StaffActivationView,
)

from .documents import (
    ChecklistOverviewView,
    DocumentItemView,
    DocumentTypeDetailView,
    DocumentTypesView,
    StaffDocumentsView,
)

router = DefaultRouter()
router.register(r"members", StaffMemberViewSet)
router.register(r"instructors", InstructorViewSet)

urlpatterns = [
    path(
        "onboard-instructor/",
        InstructorOnboardingView.as_view(),
        name="instructor-onboard",
    ),
    path(
        "activate-instructor/",
        InstructorActivationView.as_view(),
        name="instructor-activate",
    ),
    path(
        "onboard-staff/",
        StaffOnboardingView.as_view(),
        name="staff-onboard",
    ),
    path(
        "activate-staff/",
        StaffActivationView.as_view(),
        name="staff-activate",
    ),
    path(
        "credential-distribution/",
        CredentialDistributionView.as_view(),
        name="instructor-credentials",
    ),
    path("document-types/", DocumentTypesView.as_view(), name="staff-document-types"),
    path("document-types/<uuid:pk>/", DocumentTypeDetailView.as_view(), name="staff-document-type"),
    path("document-checklists/", ChecklistOverviewView.as_view(), name="staff-document-checklists"),
    path("member-documents/<uuid:staff_id>/", StaffDocumentsView.as_view(), name="staff-member-documents"),
    path("document-items/<uuid:pk>/", DocumentItemView.as_view(), name="staff-document-item"),
    path("leaves/", include("staff.leave_urls")),
    path("", include(router.urls)),
]
