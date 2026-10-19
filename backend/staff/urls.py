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
    path("leaves/", include("staff.leave_urls")),
    path("", include(router.urls)),
]
