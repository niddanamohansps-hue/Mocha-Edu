from django.urls import path

from .school_views import PlatformWebhookView
from .views import PlanSignupConfirmView, PlanSignupView, PublicPlansView

urlpatterns = [
    path("plans/", PublicPlansView.as_view(), name="billing-plans"),
    path("signup/", PlanSignupView.as_view(), name="billing-signup"),
    path("signup/confirm/", PlanSignupConfirmView.as_view(), name="billing-signup-confirm"),
    path("webhook/razorpay/", PlatformWebhookView.as_view(), name="billing-webhook-razorpay"),
]
