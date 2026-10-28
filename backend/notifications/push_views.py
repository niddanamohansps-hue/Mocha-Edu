"""
Push notification sign-up for the signed-in user's own devices (notifications/push.py):

- GET    /api/notifications/push/key/     {enabled, public_key}: whether push is set up, and the key browsers need
- POST   /api/notifications/push/         {endpoint, keys: {p256dh, auth}}: this device wants push (idempotent)
- DELETE /api/notifications/push/         {endpoint}: this device no longer wants push
- POST   /api/notifications/push/test/    sends a test notice to the user's devices
"""
from urllib.parse import urlparse

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import IsTenantMember

from .models import PushSubscription
from .push import enabled


def _valid(endpoint, p256dh, auth):
    parsed = urlparse(endpoint or "")
    # Push services are https; a URL to anything else (e.g. an internal address) is never stored.
    return (parsed.scheme == "https" and parsed.hostname and len(endpoint) <= 1000
            and 20 <= len(p256dh or "") <= 200 and 8 <= len(auth or "") <= 100)


class PushKeyView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsTenantMember()]

    def get(self, request):
        return Response({"enabled": enabled(), "public_key": getattr(settings, "WEBPUSH_VAPID_PUBLIC_KEY", "") if enabled() else ""})


class PushSubscriptionView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsTenantMember()]

    def post(self, request):
        if not enabled():
            return Response({"error": "Phone notifications are not set up on this server."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        endpoint = request.data.get("endpoint")
        keys = request.data.get("keys") or {}
        p256dh, auth = keys.get("p256dh"), keys.get("auth")
        if not _valid(endpoint, p256dh, auth):
            return Response({"error": "This browser sent an invalid subscription."}, status=status.HTTP_400_BAD_REQUEST)
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={"user_id": request.user.id, "p256dh": p256dh, "auth": auth, "failures": 0,
                      "user_agent": request.headers.get("User-Agent", "")[:255]},
        )
        return Response({"subscribed": True}, status=status.HTTP_201_CREATED)

    def delete(self, request):
        endpoint = request.data.get("endpoint") or ""
        # Only the user's own device can be removed.
        PushSubscription.objects.filter(endpoint=endpoint, user_id=request.user.id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PushTestView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), IsTenantMember()]

    def post(self, request):
        from .services import notify

        if not PushSubscription.objects.filter(user_id=request.user.id).exists():
            return Response({"error": "Turn on notifications on this device first."}, status=status.HTTP_400_BAD_REQUEST)
        notify(recipient_user_id=request.user.id, title="Notifications are working",
               body="You will get school alerts on this device.", category="push_test", link="/dashboard")
        return Response({"sent": True})
