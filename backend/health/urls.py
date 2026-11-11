from django.urls import path

from .views import HealthAlertsView, IncidentDetailView, IncidentLogView, StudentHealthView, StudentIncidentsView

urlpatterns = [
    path("students/<uuid:student_id>/", StudentHealthView.as_view(), name="student-health"),
    path("students/<uuid:student_id>/incidents/", StudentIncidentsView.as_view(), name="student-health-incidents"),
    path("incidents/", IncidentLogView.as_view(), name="health-incident-log"),
    path("incidents/<uuid:incident_id>/", IncidentDetailView.as_view(), name="health-incident-detail"),
    path("alerts/", HealthAlertsView.as_view(), name="health-alerts"),
]
