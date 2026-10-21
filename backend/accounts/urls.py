from django.urls import path
from .views import (
    LoginView,
    LogoutView,
    MeView,
    TokenRefreshView,
    VerifyAccountView,
    ChangePasswordView,
    ForgotPasswordView,
    ResetPasswordConfirmView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", MeView.as_view(), name="me"),
    path("verify-account/", VerifyAccountView.as_view(), name="verify-account"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("forgot-password/", ForgotPasswordView.as_view(), name="forgot-password"),
    path(
        "reset-password-confirm/",
        ResetPasswordConfirmView.as_view(),
        name="reset-password-confirm",
    ),
]
