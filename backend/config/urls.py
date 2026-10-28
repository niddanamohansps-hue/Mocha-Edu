from django.contrib import admin
from django.urls import path, include

from .health import health
from core.system_health import SystemHealthView
from core.import_views import ImportTemplateView, ImportView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("api/health/", health, name="health"),
    path("api/billing/", include("billing.school_urls")),
    path("api/imports/<str:kind>/template/", ImportTemplateView.as_view(), name="import-template"),
    path("api/imports/<str:kind>/", ImportView.as_view(), name="import"),
    path("api/system-health/", SystemHealthView.as_view(), name="system-health"),
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/payments/", include("payments.urls")),
    path("api/organizations/", include("organizations.urls")),
    path("api/profiles/", include("profiles.urls")),
    path("api/roles/", include("roles.urls")),
    path("api/students/", include("students.urls")),
    path("api/staff/", include("staff.urls")),
    path("api/families/", include("families.urls")),
    path("api/academics/", include("academics.urls")),
    path("api/course-content/", include("course_content.urls")),
    path("api/attendance/", include("attendance.urls")),
    path("api/timetable/", include("timetable.urls")),
    path("api/examinations/", include("examinations.urls")),
    path("api/parent-portal/", include("parent_portal.urls")),
    path("api/fees/", include("fees.urls")),
    path("api/notifications/", include("notifications.urls")),
    path("api/announcements/", include("announcements.urls")),
    path("api/certificates/", include("certificates.urls")),
    path("api/inventory/", include("inventory.urls")),
    path("api/payroll/", include("payroll.urls")),
    path("api/transport/", include("transport.urls")),
    path("api/library/", include("library.urls")),
    path("api/question-bank/", include("question_bank.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/audit-logs/", include("core.urls")),
    path("api/calendar-events/", include("academics.calendar_urls")),
    path("api/admissions/", include("students.admissions_urls")),
]

import posixpath

def protected_media_serve(request, path, document_root=None, show_indexes=False):
    # Normalize path to prevent directory traversal evasion (e.g. media/public/../admission_documents/...)
    norm_path = posixpath.normpath(str(path)).lstrip("/")
    if norm_path.startswith("..") or "/../" in norm_path or "\x00" in norm_path:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Invalid or traversed file path is forbidden.")

    # Confidential files such as student submissions, admission documents, and staff leave documents must not be accessible via unauthenticated static URLs
    if (
        norm_path.startswith("submissions/")
        or norm_path.startswith("admission_documents/")
        or norm_path.startswith("leave_documents/")
        or norm_path in ("submissions", "admission_documents", "leave_documents")
    ):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Direct access to private files is forbidden. Use authorized API endpoints.")
    from django.views.static import serve
    return serve(request, path, document_root=document_root, show_indexes=show_indexes)


# Route media requests through protected handler that blocks confidential paths
from django.urls import re_path
urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", protected_media_serve, {"document_root": settings.MEDIA_ROOT}),
]
