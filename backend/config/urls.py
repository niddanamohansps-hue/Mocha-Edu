from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
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
    path("api/dashboard/", include("dashboard.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
