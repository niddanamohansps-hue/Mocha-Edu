"""
Phase 6 risk remediation tests: TC lifecycle authorization, staff experience
dates, opaque ID-card tokens, integrity-key versioning, certificate field
exposure and the server-side picker search. Test database only.
"""

import datetime
import hashlib
import re
import uuid

from django.core import signing
from django.db import IntegrityError, connection, transaction
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from core.models import AuditLog
from profiles.models import Profile
from staff.models import StaffMember
from students.models import PromotionRecord, Student, StudentLevel

from . import idcards, services
from .models import Certificate, IdCardToken
from .tests import CertificateFixtureMixin, PASSWORD  # noqa: F401  (PASSWORD re-exported for clarity)

YESTERDAY = lambda: (timezone.localdate() - datetime.timedelta(days=1))  # noqa: E731


class TransferLifecycleTest(CertificateFixtureMixin, TransactionTestCase):
    """A TC needs the Promotion & Transfer record, not just a status."""

    def _tc(self, student, client=None, **extra):
        client = client or self._client(self.owner)
        body = {"certificate_type": "transfer", "student_id": str(student.id),
                "leaving_date": YESTERDAY().isoformat(), "reason": "Relocation", **extra}
        return self._api(client, "post", "", body)

    def test_valid_records_and_every_refusal(self):
        # Valid withdrawal record (fixture) -> issued, and the proof is kept on the certificate.
        res = self._tc(self.leaver)
        self.assertEqual(res.status_code, 201, res.data)
        with tenant_context(self.school):
            snap = Certificate.objects.get(pk=res.data["id"]).snapshot
        self.assertEqual(snap["exit_action"], "withdrawn")
        self.assertEqual(snap["exit_recorded_on"], timezone.localdate().isoformat())

        # Valid transfer record.
        moved = self._student("Tara", "CERT-T1", status="transferred")
        self._record_exit(moved, "transferred")
        res = self._tc(moved)
        self.assertEqual(res.status_code, 201, res.data)

        # Active student: refused.
        self.assertEqual(self._tc(self.active).status_code, 400)

        # Inactive student with no exit record: refused with the workflow message.
        inactive = self._student("Ira", "CERT-I1", status="inactive")
        res = self._tc(inactive)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Transferred or Withdrawn", str(res.data))

        # Legacy: status says withdrawn but nothing in the workflow -> refused, clearly.
        legacy = self._student("Lena", "CERT-L1", status="withdrawn")
        res = self._tc(legacy)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Promotion & Transfer workflow", str(res.data))
        self.assertIn("school owner", str(res.data))

        # A record that belongs to a DIFFERENT student does not help this one.
        victim = self._student("Vik", "CERT-V1", status="withdrawn")
        other_with_record = self._student("Opal", "CERT-O1", status="withdrawn")
        self._record_exit(other_with_record, "withdrawn")
        self.assertEqual(self._tc(victim).status_code, 400)

        # Record and status must agree (record says transferred, status says withdrawn).
        mismatch = self._student("Milo", "CERT-M1", status="withdrawn")
        self._record_exit(mismatch, "transferred")
        self.assertEqual(self._tc(mismatch).status_code, 400)

        # A record of a non-exit kind (e.g. promoted) is not an exit.
        promoted = self._student("Pia", "CERT-P1", status="withdrawn")
        self._record_exit(promoted, "promoted")
        self.assertEqual(self._tc(promoted).status_code, 400)

        # Duplicate live TC.
        dup = self._tc(self.leaver)
        self.assertEqual(dup.status_code, 400)
        self.assertIn("already exists", str(dup.data))

    def test_unauthorized_issuer_and_no_side_effects(self):
        issuer = self._client(self.issuer)  # issue_certificates only, not approve_certificates
        self.assertEqual(self._tc(self.leaver, issuer).status_code, 403)
        self.assertEqual(self._tc(self.leaver, self._client(self.viewer)).status_code, 403)

        with tenant_context(self.school):
            before = (PromotionRecord.objects.count(), StudentLevel.objects.filter(student=self.leaver).count(),
                      Student.objects.get(pk=self.leaver.pk).status)
        res = self._tc(self.leaver, self._client(self.approver))
        self.assertEqual(res.status_code, 201, res.data)
        with tenant_context(self.school):
            after = (PromotionRecord.objects.count(), StudentLevel.objects.filter(student=self.leaver).count(),
                     Student.objects.get(pk=self.leaver.pk).status)
        self.assertEqual(before, after)  # issuing changes no status, enrollment or lifecycle history

    def test_cancel_and_reissue_keep_history_and_still_need_the_record(self):
        client = self._client(self.canceller)
        first = self._tc(self.leaver, client)
        self.assertEqual(first.status_code, 201, first.data)
        cancelled = self._api(client, "post", f"{first.data['id']}/cancel/", {"reason": "Typo"})
        self.assertEqual(cancelled.data["status"], "cancelled")
        again = self._api(client, "post", f"{first.data['id']}/reissue/", {"reason": "Fixed"})
        self.assertEqual(again.status_code, 201, again.data)
        self.assertEqual(again.data["supersedes_number"], first.data["certificate_number"])
        with tenant_context(self.school):
            statuses = list(Certificate.objects.filter(student=self.leaver).order_by("issued_at").values_list("status", flat=True))
            self.assertEqual(statuses, ["cancelled", "issued"])
            self.assertEqual(PromotionRecord.objects.filter(student=self.leaver).count(), 1)

    def test_lifecycle_records_of_another_tenant_cannot_be_used(self):
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        with tenant_context(other):
            profile = Profile.objects.create(first_name="Zed", last_name="Other")
            foreign = Student.objects.create(profile=profile, enrollment_id="OTH-1", status="withdrawn")
            PromotionRecord.objects.create(student=foreign, action="withdrawn")
        # Through the API: a student id from another school simply does not exist here.
        res = self._tc(foreign)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Student not found", str(res.data))
        # At the service level: the other tenant's record is invisible from this schema.
        with tenant_context(self.school):
            self.assertIsNone(services.authoritative_exit_record(foreign))
            self.assertEqual(PromotionRecord.objects.filter(student_id=foreign.pk).count(), 0)


class ExperienceCertificateRulesTest(CertificateFixtureMixin, TransactionTestCase):
    def _exp(self, staff, client=None, **extra):
        client = client or self._client(self.owner)
        body = {"certificate_type": "experience", "staff_id": str(staff.id),
                "period_end": YESTERDAY().isoformat(), **extra}
        return self._api(client, "post", "", body)

    def test_rules(self):
        # Former employee with a joining date: issued; start comes from the record, end is labelled issuer-entered.
        res = self._exp(self.former)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["period_start"], "2018-06-01")
        with tenant_context(self.school):
            self.assertEqual(Certificate.objects.get(pk=res.data["id"]).snapshot["end_date_source"], "issuer_entered")
            audit = AuditLog.objects.filter(action="certificate_issued", object_id=str(res.data["id"])).first()
        self.assertEqual(audit.changes["end_date_source"], "issuer_entered")

        # Current (active) employee: refused until marked inactive.
        res = self._exp(self.teacher)
        self.assertEqual(res.status_code, 400)
        self.assertIn("still active", str(res.data))

        # Missing joining date: not invented, not typed in.
        nojoin = self._staff("Nora", "CERT-E3", joined=None, active=False)
        res = self._exp(nojoin, period_start="2019-01-01")
        self.assertEqual(res.status_code, 400)
        self.assertIn("no joining date", str(res.data))

        # A typed start that disagrees with the record is refused.
        other = self._staff("Omar", "CERT-E4", active=False)
        self.assertEqual(self._exp(other, period_start="2017-01-01").status_code, 400)
        self.assertEqual(self._exp(other, period_start="2018-06-01").status_code, 201)

        # End date: required, not in the future, not before the joining date.
        third = self._staff("Pam", "CERT-E5", active=False)
        self.assertEqual(self._api(self._client(self.owner), "post", "",
                                   {"certificate_type": "experience", "staff_id": str(third.id)}).status_code, 400)
        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()
        self.assertEqual(self._exp(third, period_end=tomorrow).status_code, 400)
        self.assertEqual(self._exp(third, period_end="2018-01-01").status_code, 400)

        # Duplicate live experience certificate.
        self.assertEqual(self._exp(self.former).status_code, 400)

    def test_authorization_and_tenant_isolation(self):
        self.assertEqual(self._exp(self.former, self._client(self.issuer)).status_code, 403)  # needs approve
        self.assertEqual(self._exp(self.former, self._client(self.viewer)).status_code, 403)
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        with tenant_context(other):
            profile = Profile.objects.create(first_name="Zoe", last_name="Other")
            foreign = StaffMember.objects.create(profile=profile, employee_id="OTH-E", designation="T",
                                                 joining_date=datetime.date(2015, 1, 1), is_active=False)
        res = self._exp(foreign)
        self.assertEqual(res.status_code, 400)
        self.assertIn("Staff member not found", str(res.data))


class OpaqueIdCardTokenTest(CertificateFixtureMixin, TransactionTestCase):
    OPAQUE = re.compile(r"^[A-Za-z0-9_-]{32}$")

    def _verify(self, token, domain=None):
        return self._api(APIClient(), "get", f"verify/id/{token}/", domain=domain)

    def test_token_is_random_stable_unique_and_reveals_nothing(self):
        with tenant_context(self.school):
            token = idcards.card_token("student", self.active)
            self.assertRegex(token, self.OPAQUE)
            self.assertEqual(idcards.card_token("student", self.active), token)  # stable across reprints
            other = idcards.card_token("staff", self.teacher)
            self.assertNotEqual(other, token)
            for needle in (str(self.active.id), self.SCHEMA, "student", self.active.enrollment_id):
                self.assertNotIn(needle, token)
            # 192-bit random: a few hundred draws never collide or repeat a prefix pattern.
            from .models import new_card_token
            draws = {new_card_token() for _ in range(500)}
            self.assertEqual(len(draws), 500)
            self.assertTrue(all(self.OPAQUE.match(d) for d in draws))
            # Database uniqueness: the same token cannot be stored twice, and one live token per holder.
            with self.assertRaises(IntegrityError), transaction.atomic():
                IdCardToken.objects.create(kind="staff", staff_member=self.former, token=token)
            with self.assertRaises(IntegrityError), transaction.atomic():
                IdCardToken.objects.create(kind="student", student=self.active)  # second live token

    def test_qr_url_and_public_verification_are_minimal(self):
        carder = self._client(self.carder)
        res = self._api(carder, "get", f"id-cards/student/{self.active.id}/")
        self.assertEqual(res.status_code, 200, res.data)
        with tenant_context(self.school):
            token = IdCardToken.objects.get(student=self.active).token
        # The printed QR must not carry the internal id or schema name: decode the SVG-embedded URL is not possible,
        # so check the URL the server builds (same function feeds both QR renderers).
        class R:  # minimal request stand-in
            def get_host(self_inner): return "school.localhost:8000"
        with tenant_context(self.school):
            url = idcards.frontend_url(R(), f"/verify/id/{idcards.card_token('student', self.active)}")
        self.assertTrue(url.endswith("/verify/id/" + token))
        self.assertNotIn(str(self.active.id), url)
        self.assertNotIn(self.SCHEMA, url)

        pub = self._verify(token)
        self.assertEqual(pub.status_code, 200)
        self.assertEqual(set(pub.data), {"valid", "kind", "school_name", "holder", "status"})
        self.assertTrue(pub.data["valid"])
        self.assertEqual(pub.data["holder"], "Anita S.")
        self.assertNotIn(str(self.active.id), str(pub.data))

    def test_invalid_malformed_and_revoked_tokens_look_identical(self):
        carder = self._client(self.carder)
        self._api(carder, "get", f"id-cards/student/{self.active.id}/")
        with tenant_context(self.school):
            token = IdCardToken.objects.get(student=self.active).token
        rotated = self._api(carder, "post", f"id-cards/student/{self.active.id}/rotate/")
        self.assertEqual(rotated.status_code, 200, rotated.data)
        with tenant_context(self.school):
            new_token = IdCardToken.objects.get(student=self.active, revoked_at__isnull=True).token
            self.assertEqual(IdCardToken.objects.filter(student=self.active).count(), 2)
        self.assertNotEqual(new_token, token)
        revoked, unknown, malformed = self._verify(token), self._verify("Z" * 32), self._verify("not-a-token")
        self.assertEqual(revoked.data, unknown.data)
        self.assertEqual(unknown.data, malformed.data)
        self.assertFalse(revoked.data["valid"])
        self.assertEqual(revoked.data["status"], "invalid")
        self.assertTrue(self._verify(new_token).data["valid"])

        # Rotation is audited without the secret; it needs generate_id_cards; only for eligible holders.
        with tenant_context(self.school):
            log = AuditLog.objects.get(action="id_card_token_rotated")
        self.assertNotIn(new_token, str(log.changes))
        self.assertNotIn(token, str(log.changes))
        self.assertEqual(self._api(self._client(self.viewer), "post", f"id-cards/student/{self.active.id}/rotate/").status_code, 403)
        self.assertEqual(self._api(carder, "post", f"id-cards/student/{self.leaver.id}/rotate/").status_code, 400)

    def test_tenant_isolation_and_holder_deactivation(self):
        with tenant_context(self.school):
            token = idcards.card_token("student", self.active)
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        res = self._verify(token, domain=self.OTHER_DOMAIN)
        self.assertFalse(res.data["valid"])
        self.assertEqual(res.data["status"], "invalid")  # looks up only inside the host's tenant
        with tenant_context(self.school):
            Student.objects.filter(pk=self.active.pk).update(status="withdrawn")
        self.assertEqual(self._verify(token).data["status"], "inactive")
        del other

    def test_legacy_signed_tokens_are_accepted_only_while_the_setting_is_on(self):
        with tenant_context(self.school):
            legacy = signing.dumps({"k": "student", "i": str(self.active.id), "s": self.SCHEMA},
                                   salt=idcards.SALT, compress=True)
        with override_settings(ID_CARD_ACCEPT_LEGACY_TOKENS=True):
            res = self._verify(legacy)
            self.assertTrue(res.data["valid"])
        with override_settings(ID_CARD_ACCEPT_LEGACY_TOKENS=False):
            res = self._verify(legacy)
            self.assertFalse(res.data["valid"])
            self.assertEqual(res.data["status"], "invalid")
        # A legacy token from another schema is never honoured, even while accepted.
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        with override_settings(ID_CARD_ACCEPT_LEGACY_TOKENS=True):
            self.assertFalse(self._verify(legacy, domain=self.OTHER_DOMAIN).data["valid"])
        del other
        # And no new card is ever printed in the legacy format.
        with tenant_context(self.school):
            self.assertNotIn(":", idcards.card_token("student", self.active))


class FieldExposureAndPickerTest(CertificateFixtureMixin, TransactionTestCase):
    def test_certificate_fields_are_limited_by_permission(self):
        owner = self._client(self.owner)
        made = self._api(owner, "post", "", {"certificate_type": "transfer", "student_id": str(self.leaver.id),
                                             "leaving_date": YESTERDAY().isoformat(), "reason": "Move",
                                             "internal_notes": "Fee dispute"})
        self.assertEqual(made.status_code, 201, made.data)
        cid = made.data["id"]
        self.assertNotIn("snapshot", made.data)

        viewer = self._client(self.viewer)  # view_certificates only
        detail = self._api(viewer, "get", f"{cid}/")
        self.assertEqual(detail.status_code, 200)
        for hidden in ("internal_notes", "snapshot", "issued_by_user_id", "approved_by_user_id", "student",
                       "staff_member", "verification_id", "cancelled_by_user_id"):
            self.assertNotIn(hidden, detail.data, hidden)
        self.assertNotIn("Fee dispute", str(detail.data))
        self.assertNotIn("2012-05-17", str(detail.data))  # date of birth

        listing = self._api(viewer, "get", "")
        self.assertEqual(listing.status_code, 200)
        row = listing.data["results"][0]
        self.assertEqual(set(row), {"id", "certificate_type", "certificate_type_label", "certificate_number",
                                    "holder_name", "issue_date", "academic_year", "status", "supersedes_number",
                                    "superseded_by_number"})
        self.assertNotIn("2012-05-17", str(listing.data))

        # Registrar / principal workflows keep the full record (still never the snapshot).
        for user in (self.issuer, self.approver, self.canceller):
            full = self._api(self._client(user), "get", f"{cid}/")
            self.assertEqual(full.data["internal_notes"], "Fee dispute")
            self.assertIn("verification_id", full.data)
            self.assertNotIn("snapshot", full.data)
        # Even the full list stays minimal for everybody.
        self.assertNotIn("internal_notes", self._api(owner, "get", "").data["results"][0])

        # Backend enforcement, not UI hiding: unauthenticated and unrelated users get nothing.
        self.assertIn(self._api(APIClient(), "get", f"{cid}/").status_code, (401, 403))
        self.assertEqual(self._api(self._client(self.carder), "get", f"{cid}/").status_code, 403)
        # Other tenant: the same id is simply not found.
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        other_owner = self._user(other, "cert_other_owner", owner=True)
        res = self._api(self._client(other_owner, self.OTHER_DOMAIN), "get", f"{cid}/", domain=self.OTHER_DOMAIN)
        self.assertEqual(res.status_code, 404)

    def test_student_and_staff_picker_search_pagination_permissions_and_isolation(self):
        for i in range(24):
            self._student(f"Bulk{i:02d}", f"BULK-{i:03d}")
        reader = self._user(self.school, "cert_reader", ["view_student", "view_staff"])
        client = self._client(reader)
        get = lambda path, **q: client.get(path, q, HTTP_HOST=self.DOMAIN)  # noqa: E731

        everything = get("/api/students/list/", page_size=500)
        self.assertEqual(len(everything.data["results"]), everything.data["count"] if everything.data["count"] <= 100 else 100)
        page = get("/api/students/list/", page_size=10)
        self.assertEqual(len(page.data["results"]), 10)
        self.assertIsNotNone(page.data["next"])  # bounded pages, not "load everything"

        by_name = get("/api/students/list/", search="Bulk07")
        self.assertEqual([r["enrollment_id"] for r in by_name.data["results"]], ["BULK-007"])
        by_id = get("/api/students/list/", search="BULK-01")
        self.assertEqual(by_id.data["count"], 10)  # BULK-010..019
        by_terms = get("/api/students/list/", search="bulk 023")
        self.assertEqual([r["enrollment_id"] for r in by_terms.data["results"]], ["BULK-023"])
        self.assertEqual(get("/api/students/list/", search="zzzznothing").data["count"], 0)

        left = get("/api/students/list/", status="withdrawn,transferred")
        self.assertEqual({r["status"] for r in left.data["results"]}, {"withdrawn"})
        self.assertEqual(get("/api/students/list/", status="bogus").data["count"], 0)

        staff = get("/api/staff/members/", search="Farid")
        self.assertEqual([r["employee_id"] for r in staff.data["results"]], ["CERT-E2"])
        self.assertEqual(get("/api/staff/members/", is_active="false").data["count"], 1)
        self.assertEqual(get("/api/staff/members/", search="CERT-E1").data["count"], 1)

        # Permissions are unchanged: no view_student / view_staff -> 403.
        nobody = self._client(self._user(self.school, "cert_nobody", ["view_certificates"]))
        self.assertEqual(nobody.get("/api/students/list/", {"search": "Bulk"}, HTTP_HOST=self.DOMAIN).status_code, 403)
        self.assertEqual(nobody.get("/api/staff/members/", {"search": "Farid"}, HTTP_HOST=self.DOMAIN).status_code, 403)

        # Tenant isolation: another school's reader never sees this school's students.
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        other_reader = self._client(self._user(other, "cert_other_reader", ["view_student", "view_staff"]), self.OTHER_DOMAIN)
        res = other_reader.get("/api/students/list/", {"search": "Bulk"}, HTTP_HOST=self.OTHER_DOMAIN)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["count"], 0)

    def test_issuing_fails_closed_when_no_integrity_key_is_configured(self):
        owner = self._client(self.owner)
        body = {"certificate_type": "bonafide", "student_id": str(self.active.id), "reason": "x"}
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS="", CERTIFICATE_INTEGRITY_ACTIVE_KEY=""):
            res = self._api(owner, "post", "", body)
        self.assertEqual(res.status_code, 400)
        self.assertIn("integrity key", str(res.data))
        with tenant_context(self.school):
            self.assertEqual(Certificate.objects.count(), 0)  # nothing half-issued, no number consumed
            from .models import CertificateSequence
            self.assertEqual(CertificateSequence.objects.filter(last_number__gt=0).count(), 0)
        self.assertEqual(self._api(owner, "post", "", body).status_code, 201)  # dev key works again


class IntegrityKeyVersioningTest(SimpleTestCase):
    """Pure functions: no database."""

    def _cert(self, **kw):
        cert = Certificate(
            certificate_type="bonafide", certificate_number="BON-2026-00001", verification_id="v" * 32,
            issue_date=datetime.date(2026, 10, 18), snapshot={"holder_name": "Anita Sharma"}, status="issued",
            issued_by_user_id=uuid.UUID(int=1),
        )
        cert.id = uuid.UUID(int=7)
        for k, v in kw.items():
            setattr(cert, k, v)
        return cert

    KEYS = "1:alpha-secret-one,2:beta-secret-two"

    def test_seal_names_its_key_and_verifies(self):
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS=self.KEYS, CERTIFICATE_INTEGRITY_ACTIVE_KEY="1"):
            cert = self._cert()
            cert.integrity_hash = services.compute_integrity_hash(cert)
            self.assertTrue(cert.integrity_hash.startswith("k1:"))
            self.assertEqual(services.seal_key_id(cert), "1")
            self.assertTrue(services.verify_integrity(cert))
            cert.snapshot = {"holder_name": "Someone Else"}
            self.assertFalse(services.verify_integrity(cert))  # content change detected

    def test_rotation_keeps_old_certificates_verifiable_until_the_key_is_retired(self):
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS="1:alpha-secret-one", CERTIFICATE_INTEGRITY_ACTIVE_KEY="1"):
            old = self._cert()
            old.integrity_hash = services.compute_integrity_hash(old)
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS=self.KEYS, CERTIFICATE_INTEGRITY_ACTIVE_KEY="2"):
            self.assertTrue(services.verify_integrity(old))  # signed with 1, still accepted
            new = self._cert(certificate_number="BON-2026-00002")
            new.integrity_hash = services.compute_integrity_hash(new)
            self.assertTrue(new.integrity_hash.startswith("k2:"))  # new seals use the active key
            self.assertTrue(services.verify_integrity(new))
            resealed = self._cert()
            resealed.integrity_hash = services.compute_integrity_hash(resealed)
            self.assertTrue(resealed.integrity_hash.startswith("k2:"))  # a status change re-seals under key 2
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS="2:beta-secret-two", CERTIFICATE_INTEGRITY_ACTIVE_KEY="2"):
            self.assertFalse(services.verify_integrity(old))  # key 1 retired: fails closed, never silently re-keyed
            self.assertTrue(services.verify_integrity(new))

    def test_invalid_unknown_and_wrong_key_seals_fail_closed(self):
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS=self.KEYS, CERTIFICATE_INTEGRITY_ACTIVE_KEY="1"):
            cert = self._cert()
            good = services.compute_integrity_hash(cert)
            digest = good.split(":", 1)[1]
            for bad in (f"k1:{'0' * 64}", f"k9:{digest}", f"k2:{digest}", "k1:", "kx", "", "garbage", good.upper()):
                cert.integrity_hash = bad
                self.assertFalse(services.verify_integrity(cert), bad)

    def test_missing_keys_fail_closed_and_never_fall_back_outside_debug(self):
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS="", CERTIFICATE_INTEGRITY_ACTIVE_KEY=""):
            with self.assertRaises(services.IntegrityKeyError):
                services.compute_integrity_hash(self._cert())
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS="1:alpha-secret-one", CERTIFICATE_INTEGRITY_ACTIVE_KEY="7"):
            with self.assertRaises(services.IntegrityKeyError):  # active id not in the key list
                services.compute_integrity_hash(self._cert())
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS="1:alpha-secret-one", CERTIFICATE_INTEGRITY_ACTIVE_KEY=""):
            with self.assertRaises(services.IntegrityKeyError):
                services.compute_integrity_hash(self._cert())

    def test_dev_key_is_labelled_and_never_verifies_in_production(self):
        with override_settings(DEBUG=True, CERTIFICATE_INTEGRITY_KEYS="", CERTIFICATE_INTEGRITY_ACTIVE_KEY=""):
            cert = self._cert()
            cert.integrity_hash = services.compute_integrity_hash(cert)
            self.assertTrue(cert.integrity_hash.startswith("kdev:"))
            self.assertTrue(services.verify_integrity(cert))
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS=self.KEYS, CERTIFICATE_INTEGRITY_ACTIVE_KEY="1"):
            self.assertFalse(services.verify_integrity(cert))  # a dev-sealed record is not honoured in production

    def test_legacy_unversioned_seals_only_while_accepted_and_never_for_new_seals(self):
        cert = self._cert()
        legacy = salted_hmac("certificates.integrity.v1", services._canonical(cert), algorithm="sha256").hexdigest()
        cert.integrity_hash = legacy
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS=self.KEYS, CERTIFICATE_INTEGRITY_ACTIVE_KEY="1",
                               CERTIFICATE_ACCEPT_LEGACY_SEALS=True):
            self.assertTrue(services.verify_integrity(cert))
            self.assertEqual(services.seal_key_id(cert), "legacy")
            fresh = services.compute_integrity_hash(cert)
            self.assertTrue(fresh.startswith("k1:"))  # re-sealing upgrades it; legacy is never produced again
            cert.integrity_hash = legacy[:-1] + ("0" if legacy[-1] != "0" else "1")
            self.assertFalse(services.verify_integrity(cert))
        cert.integrity_hash = legacy
        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS=self.KEYS, CERTIFICATE_INTEGRITY_ACTIVE_KEY="1",
                               CERTIFICATE_ACCEPT_LEGACY_SEALS=False):
            self.assertFalse(services.verify_integrity(cert))

    def test_secret_key_alone_cannot_forge_a_versioned_seal(self):
        from django.conf import settings

        with override_settings(DEBUG=False, CERTIFICATE_INTEGRITY_KEYS=self.KEYS, CERTIFICATE_INTEGRITY_ACTIVE_KEY="1"):
            cert = self._cert()
            forged = salted_hmac("certificates.integrity.v1", services._canonical(cert), algorithm="sha256").hexdigest()
            cert.integrity_hash = f"k1:{forged}"
            self.assertFalse(services.verify_integrity(cert))
            cert.integrity_hash = "k1:" + hashlib.sha256(settings.SECRET_KEY.encode()).hexdigest()
            self.assertFalse(services.verify_integrity(cert))
