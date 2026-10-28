from unittest import mock

from django.db import connection
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from roles.models import Role, UserRole

from .models import PushSubscription
from .push import send
from .services import notify

KEYS = {"WEBPUSH_VAPID_PUBLIC_KEY": "BPublicKeyForTests", "WEBPUSH_VAPID_PRIVATE_KEY": "private-key-for-tests"}
ENDPOINT = "https://fcm.googleapis.com/fcm/send/abc123"
SUB = {"endpoint": ENDPOINT, "keys": {"p256dh": "B" + "x" * 86, "auth": "authsecret123"}}


class FakeResponse:
    def __init__(self, code):
        self.status_code = code


@override_settings(**KEYS)
class PushTests(TransactionTestCase):
    SCHEMA, DOMAIN = "push_school", "push.localhost"

    def setUp(self):
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Push School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        self.user = User.objects.create_user(username="push_user", email="push@x.test", password="Pass1234!")
        self.other = User.objects.create_user(username="push_other", email="other@x.test", password="Pass1234!")
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(slug="owner", defaults={"name": "Owner", "is_system_role": True})
            for user in (self.user, self.other):
                UserRole.objects.create(user=user, role=role)

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        User.objects.filter(username__in=["push_user", "push_other"]).delete()

    def _client(self, username="push_user"):
        client = APIClient()
        assert client.post("/api/auth/login/", {"username": username, "password": "Pass1234!"},
                           HTTP_HOST=self.DOMAIN).status_code == 200
        return client

    def test_key_subscribe_and_unsubscribe(self):
        client = self._client()
        self.assertEqual(client.get("/api/notifications/push/key/", HTTP_HOST=self.DOMAIN).data,
                         {"enabled": True, "public_key": KEYS["WEBPUSH_VAPID_PUBLIC_KEY"]})
        self.assertEqual(client.post("/api/notifications/push/", SUB, format="json", HTTP_HOST=self.DOMAIN).status_code, 201)
        client.post("/api/notifications/push/", SUB, format="json", HTTP_HOST=self.DOMAIN)  # same device again
        with tenant_context(self.school):
            self.assertEqual(PushSubscription.objects.filter(user_id=self.user.id).count(), 1)
        # Another user cannot remove this device.
        self._client("push_other").delete("/api/notifications/push/", {"endpoint": ENDPOINT}, format="json", HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            self.assertTrue(PushSubscription.objects.exists())
        client.delete("/api/notifications/push/", {"endpoint": ENDPOINT}, format="json", HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            self.assertFalse(PushSubscription.objects.exists())

    def test_only_https_push_services_are_accepted(self):
        bad = {**SUB, "endpoint": "http://10.0.0.5/internal"}
        self.assertEqual(self._client().post("/api/notifications/push/", bad, format="json", HTTP_HOST=self.DOMAIN).status_code, 400)

    @override_settings(WEBPUSH_VAPID_PUBLIC_KEY="", WEBPUSH_VAPID_PRIVATE_KEY="")
    def test_without_keys_push_is_off(self):
        client = self._client()
        self.assertEqual(client.get("/api/notifications/push/key/", HTTP_HOST=self.DOMAIN).data["enabled"], False)
        self.assertEqual(client.post("/api/notifications/push/", SUB, format="json", HTTP_HOST=self.DOMAIN).status_code, 503)

    def test_notifications_are_pushed_to_the_recipients_devices_only(self):
        with tenant_context(self.school):
            PushSubscription.objects.create(user_id=self.user.id, endpoint=ENDPOINT, p256dh=SUB["keys"]["p256dh"], auth="authsecret123")
            PushSubscription.objects.create(user_id=self.other.id, endpoint=ENDPOINT + "x", p256dh=SUB["keys"]["p256dh"], auth="a" * 10)
            note = notify(recipient_user_id=self.user.id, title="Fee due", body="Pay by Friday", link="/dashboard/fees")
            with mock.patch("pywebpush.webpush") as webpush:
                self.assertEqual(send([note.id]), 1)
            payload = webpush.call_args.kwargs["data"]
            self.assertIn("Fee due", payload)
            self.assertEqual(webpush.call_args.kwargs["subscription_info"]["endpoint"], ENDPOINT)

    def test_a_device_that_is_gone_is_forgotten(self):
        from pywebpush import WebPushException

        with tenant_context(self.school):
            PushSubscription.objects.create(user_id=self.user.id, endpoint=ENDPOINT, p256dh=SUB["keys"]["p256dh"], auth="authsecret123")
            note = notify(recipient_user_id=self.user.id, title="Hello")
            with mock.patch("pywebpush.webpush", side_effect=WebPushException("gone", response=FakeResponse(410))):
                self.assertEqual(send([note.id]), 0)
            self.assertFalse(PushSubscription.objects.exists())

    def test_notify_queues_a_push_after_commit(self):
        # TransactionTestCase runs in autocommit, so on_commit callbacks run straight away.
        with tenant_context(self.school), mock.patch("notifications.tasks.send_push_notifications.delay") as delay:
            notify(recipient_user_id=self.user.id, title="Homework set")
        delay.assert_called_once()
        self.assertEqual(delay.call_args.args[0], self.SCHEMA)
