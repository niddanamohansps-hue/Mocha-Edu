from django.urls import path, re_path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register(r"", views.CertificateViewSet, basename="certificate")

UUID = r"[0-9a-fA-F-]{36}"

# Fixed paths first so they are never read as a certificate pk.
urlpatterns = [
    path("settings/", views.CertificateSettingsView.as_view(), name="certificate-settings"),
    path("verify/certificate/<str:verification_id>/", views.PublicCertificateVerifyView.as_view(), name="certificate-verify"),
    path("verify/id/<str:token>/", views.PublicIdCardVerifyView.as_view(), name="id-card-verify"),
    re_path(rf"^id-cards/student/(?P<record_id>{UUID})/$", views.StudentIdCardData.as_view(), name="student-id-card"),
    re_path(rf"^id-cards/student/(?P<record_id>{UUID})/pdf/$", views.StudentIdCardPdf.as_view(), name="student-id-card-pdf"),
    re_path(rf"^id-cards/student/(?P<record_id>{UUID})/rotate/$", views.StudentIdCardRotate.as_view(), name="student-id-card-rotate"),
    re_path(rf"^id-cards/staff/(?P<record_id>{UUID})/rotate/$", views.StaffIdCardRotate.as_view(), name="staff-id-card-rotate"),
    re_path(rf"^id-cards/staff/(?P<record_id>{UUID})/$", views.StaffIdCardData.as_view(), name="staff-id-card"),
    re_path(rf"^id-cards/staff/(?P<record_id>{UUID})/pdf/$", views.StaffIdCardPdf.as_view(), name="staff-id-card-pdf"),
] + router.urls
