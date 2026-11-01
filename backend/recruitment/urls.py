from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ApplicantViewSet,
    InterviewViewSet,
    JobOpeningViewSet,
    PublicApplyView,
    PublicOpeningsView,
    PublicStatusView,
    RecruitmentSummaryView,
)

router = DefaultRouter()
router.register(r"openings", JobOpeningViewSet, basename="recruitment-openings")
router.register(r"applicants", ApplicantViewSet, basename="recruitment-applicants")
router.register(r"interviews", InterviewViewSet, basename="recruitment-interviews")

urlpatterns = [
    path("summary/", RecruitmentSummaryView.as_view(), name="recruitment-summary"),
    path("public/openings/", PublicOpeningsView.as_view(), name="recruitment-public-openings"),
    path("public/apply/", PublicApplyView.as_view(), name="recruitment-public-apply"),
    path("public/status/", PublicStatusView.as_view(), name="recruitment-public-status"),
    path("", include(router.urls)),
]
