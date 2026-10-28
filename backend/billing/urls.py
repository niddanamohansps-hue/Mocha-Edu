from django.urls import path

from .views import PlanSignupConfirmView, PlanSignupView, PublicPlansView

urlpatterns = [
    path("plans/", PublicPlansView.as_view(), name="billing-plans"),
    path("signup/", PlanSignupView.as_view(), name="billing-signup"),
    path("signup/confirm/", PlanSignupConfirmView.as_view(), name="billing-signup-confirm"),
]
