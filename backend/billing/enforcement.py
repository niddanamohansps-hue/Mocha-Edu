"""
What a school's subscription allows.

- SubscriptionWriteGuard (middleware): an unpaid school is read-only. Any change through the API
  (POST/PUT/PATCH/DELETE) answers 402 with a clear message, except signing in/out, billing itself, and
  the health check, so the owner can always pay. Reading is never blocked and no data is touched.
  Schools without a subscription row (before billing) and legacy schools are never blocked.
- check_student_capacity: refuses a new student beyond the plan's student limit.
"""
from django.db import connection
from django.http import JsonResponse
from rest_framework.exceptions import ValidationError

SAFE_METHODS = ("GET", "HEAD", "OPTIONS")
ALWAYS_ALLOWED = ("/api/auth/", "/api/billing/", "/api/health/", "/api/system-health/")
READ_ONLY_MESSAGE = (
    "Your school's EduSekai subscription is unpaid, so the school is read-only: you can see everything but "
    "cannot make changes. The owner can pay on the Billing page to unlock it at once. No data has been deleted."
)


def current_subscription():
    from .models import Subscription

    tenant = getattr(connection, "tenant", None)
    if tenant is None or getattr(tenant, "schema_name", "public") == "public":
        return None
    return Subscription.objects.select_related("plan").filter(organization_id=tenant.id).first()


class SubscriptionWriteGuard:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in SAFE_METHODS and request.path.startswith("/api/") \
                and not request.path.startswith(ALWAYS_ALLOWED):
            subscription = current_subscription()
            if subscription is not None and not subscription.is_legacy:
                from .services import refresh_status

                refresh_status(subscription)
                if not subscription.can_write():
                    return JsonResponse(
                        {"error": READ_ONLY_MESSAGE, "code": "subscription_read_only", "billing_url": "/dashboard/billing"},
                        status=402,
                    )
        return self.get_response(request)


def check_student_capacity(adding=1):
    """Raises a ValidationError when adding students would go past the plan's limit."""
    subscription = current_subscription()
    if subscription is None or subscription.is_legacy or not subscription.plan.student_limit:
        return
    from students.models import Student

    active = Student.objects.filter(status="active").count()
    limit = subscription.plan.student_limit
    if active + adding > limit:
        raise ValidationError({
            "error": f"Your {subscription.plan.name} plan allows {limit:,} students and the school already has "
                     f"{active:,}. Upgrade the plan on the Billing page to add more.",
            "code": "student_limit_reached",
        })
