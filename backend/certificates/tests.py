"""
Certificates and ID cards (Phase 6). Runs on the isolated test database only.

Each test builds one tenant schema (slow by design, like the other tenant test
suites), so scenarios are grouped into a handful of dense tests.
"""

import datetime
import io
import re
import threading
import uuid
from unittest import mock

import segno
from reportlab.pdfbase import pdfmetrics

from django.db import connection, transaction
from django.test import SimpleTestCase, TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import User
from academics.models import AcademicLevel, Program, Section
from core.models import AuditLog
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember
from students.models import Student, StudentLevel

from . import idcards, pdf, services
from .models import Certificate, CertificateSequence

PASSWORD = "Pass1234!"
PRIVATE_KEYS = {
    "date_of_birth", "address", "phone", "alt_phone", "email", "enrollment_id", "employee_id",
    "reason", "conduct", "internal_notes", "snapshot", "student", "staff_member", "issued_by_user_id",
    "approved_by_user_id", "id",
}


class CertificateFixtureMixin:
    SCHEMA = "cert_p06_school"
    OTHER_SCHEMA = "cert_p06_other"
    DOMAIN = "cert-p06.localhost"
    OTHER_DOMAIN = "cert-p06-other.localhost"

    def _school(self, schema, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=f"School {schema}")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _user(self, school, username, codenames=(), owner=False):
        user = User.objects.create_user(username=username, email=f"{username}@cert.test", password=PASSWORD)
        with tenant_context(school):
            if owner:
                role = Role.objects.get(slug="owner")
            else:
                slug = f"r-{uuid.uuid4().hex[:8]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.create(user=user, role=role)
        return user

    def _client(self, user, domain=None):
        client = APIClient()
        resp = client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD},
                           HTTP_HOST=domain or self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.content)
        return client

    def _api(self, client, method, path, data=None, domain=None):
        kwargs = {"HTTP_HOST": domain or self.DOMAIN}
        if method in ("post", "patch", "put"):
            kwargs["format"] = "json"
        return getattr(client, method)(f"/api/certificates/{path}", data, **kwargs)

    def _student(self, first, enrollment, status="active", dob=datetime.date(2012, 5, 17), admitted=datetime.date(2020, 4, 1)):
        with tenant_context(self.school):
            profile = Profile.objects.create(
                first_name=first, last_name="Sharma", date_of_birth=dob,
                address="Secret Street 12", phone="9800000000",
            )
            student = Student.objects.create(profile=profile, enrollment_id=enrollment, status=status, admission_date=admitted)
            StudentLevel.objects.create(student=student, level=self.level, section=self.section,
                                        academic_year="2026-27", is_current=True)
            return student

    def _staff(self, first, employee_id, joined=datetime.date(2018, 6, 1), active=True):
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name=first, last_name="Rai", address="Hidden Lane 3", phone="9811111111")
            return StaffMember.objects.create(profile=profile, employee_id=employee_id, designation="Teacher",
                                              department="Science", joining_date=joined, is_active=active)

    def _record_exit(self, student, action):
        """What the Promotion & Transfer workflow writes when a student leaves."""
        from students.models import PromotionRecord

        with tenant_context(self.school):
            return PromotionRecord.objects.create(student=student, action=action, reason="test exit")

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA, self.OTHER_SCHEMA]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="cert_").delete()

    def setUp(self):
        super().setUp()
        self.addCleanup(self._cleanup)
        self.school = self._school(self.SCHEMA, self.DOMAIN)
        self.owner = self._user(self.school, "cert_owner", owner=True)
        self.viewer = self._user(self.school, "cert_viewer", ["view_certificates"])
        self.issuer = self._user(self.school, "cert_issuer", ["view_certificates", "issue_certificates"])
        self.approver = self._user(self.school, "cert_approver", ["view_certificates", "approve_certificates"])
        self.canceller = self._user(self.school, "cert_canceller",
                                    ["view_certificates", "cancel_certificates", "issue_certificates", "approve_certificates"])
        self.carder = self._user(self.school, "cert_carder", ["generate_id_cards"])
        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="HS")
            self.level = AcademicLevel.objects.create(program=program, name="Grade 10", order=10)
            self.section = Section.objects.create(level=self.level, name="A")
        self.active = self._student("Anita", "CERT-001")
        self.leaver = self._student("Bikash", "CERT-002", status="withdrawn")
        self._record_exit(self.leaver, "withdrawn")
        self.teacher = self._staff("Chandra", "CERT-E1")  # active: ID cards
        self.former = self._staff("Farid", "CERT-E2", active=False)  # inactive: experience certificates


class CertificateRulesAndAccessTest(CertificateFixtureMixin, TransactionTestCase):
    def test_type_validation_tc_safeguards_and_no_lifecycle_side_effects(self):
        client = self._client(self.owner)
        post = lambda body: self._api(client, "post", "", body)
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        tomorrow = (timezone.localdate() + datetime.timedelta(days=1)).isoformat()

        # Required subject per type.
        self.assertEqual(post({"certificate_type": "bonafide"}).status_code, 400)
        self.assertEqual(post({"certificate_type": "experience"}).status_code, 400)

        # TC: only for transferred/withdrawn students.
        res = post({"certificate_type": "transfer", "student_id": str(self.active.id),
                    "leaving_date": yesterday, "reason": "Relocation"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("Transferred or Withdrawn", str(res.data))
        base = {"certificate_type": "transfer", "student_id": str(self.leaver.id)}
        self.assertEqual(post({**base, "reason": "Relocation"}).status_code, 400)  # no leaving date
        self.assertEqual(post({**base, "leaving_date": tomorrow, "reason": "x"}).status_code, 400)  # future
        self.assertEqual(post({**base, "leaving_date": "2019-01-01", "reason": "x"}).status_code, 400)  # < admission
        self.assertEqual(post({**base, "leaving_date": yesterday}).status_code, 400)  # no reason

        # Other student types.
        self.assertEqual(post({"certificate_type": "bonafide", "student_id": str(self.leaver.id)}).status_code, 400)
        self.assertEqual(post({"certificate_type": "character", "student_id": str(self.active.id)}).status_code, 400)
        # Staff experience: end date required, ordered, not in the future.
        exp = {"certificate_type": "experience", "staff_id": str(self.former.id)}
        self.assertEqual(post(exp).status_code, 400)
        self.assertEqual(post({**exp, "period_end": "2017-01-01"}).status_code, 400)
        self.assertEqual(post({**exp, "period_end": tomorrow}).status_code, 400)
        # Characters the PDF font cannot draw are rejected, not printed as blanks.
        res = post({"certificate_type": "character", "student_id": str(self.active.id), "conduct": "उत्तम"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("cannot print", str(res.data))

        # Valid issues.
        ok = post({**base, "leaving_date": yesterday, "reason": "Relocation", "conduct": "Good"})
        self.assertEqual(ok.status_code, 201, ok.data)
        self.assertTrue(ok.data["certificate_number"].startswith("TC-"))
        self.assertNotIn("snapshot", ok.data)
        with tenant_context(self.school):
            self.assertEqual(Certificate.objects.get(pk=ok.data["id"]).snapshot["date_of_birth"], "2012-05-17")
        self.assertEqual(ok.data["approved_by_user_id"], str(self.owner.id))
        # Duplicate live TC is refused.
        dup = post({**base, "leaving_date": yesterday, "reason": "Again"})
        self.assertEqual(dup.status_code, 400)
        self.assertIn("already exists", str(dup.data))

        bon = post({"certificate_type": "bonafide", "student_id": str(self.active.id), "reason": "Bank account"})
        self.assertEqual(bon.status_code, 201, bon.data)
        with tenant_context(self.school):
            self.assertNotIn("date_of_birth", Certificate.objects.get(pk=bon.data["id"]).snapshot)
        chr_ = post({"certificate_type": "character", "student_id": str(self.leaver.id), "conduct": "Excellent"})
        self.assertEqual(chr_.status_code, 201, chr_.data)
        exp_ok = post({**exp, "period_end": yesterday, "conduct": "Very good"})
        self.assertEqual(exp_ok.status_code, 201, exp_ok.data)
        self.assertEqual(exp_ok.data["period_start"], "2018-06-01")  # defaulted from joining date

        # Issuing never alters the student lifecycle or enrolment history.
        with tenant_context(self.school):
            self.leaver.refresh_from_db()
            self.assertEqual(self.leaver.status, "withdrawn")
            self.assertEqual(StudentLevel.objects.filter(student=self.leaver).count(), 1)
            self.assertTrue(Student.objects.filter(pk=self.leaver.pk).exists())

        # Snapshot survives later profile edits.
        with tenant_context(self.school):
            Profile.objects.filter(pk=self.active.profile_id).update(first_name="Renamed")
        with tenant_context(self.school):
            self.assertEqual(Certificate.objects.get(pk=bon.data["id"]).snapshot["holder_name"], "Anita Sharma")
        self.assertEqual(self._api(client, "get", f"{bon.data['id']}/").data["holder_name"], "Anita Sharma")

    def test_authorization_tenant_isolation_settings_and_audit(self):
        payload_b = {"certificate_type": "bonafide", "student_id": str(self.active.id)}
        payload_tc = {"certificate_type": "transfer", "student_id": str(self.leaver.id),
                      "leaving_date": (timezone.localdate() - datetime.timedelta(days=2)).isoformat(), "reason": "Move"}

        anon = APIClient()
        self.assertIn(self._api(anon, "get", "").status_code, (401, 403))

        viewer = self._client(self.viewer)
        self.assertEqual(self._api(viewer, "get", "").status_code, 200)
        self.assertEqual(self._api(viewer, "post", "", payload_b).status_code, 403)

        issuer = self._client(self.issuer)
        made = self._api(issuer, "post", "", payload_b)
        self.assertEqual(made.status_code, 201, made.data)
        self.assertIsNone(made.data["approved_by_user_id"])
        self.assertEqual(self._api(issuer, "post", "", payload_tc).status_code, 403)  # needs approve_certificates

        approver = self._client(self.approver)
        tc = self._api(approver, "post", "", payload_tc)
        self.assertEqual(tc.status_code, 201, tc.data)
        self.assertEqual(tc.data["approved_by_user_id"], str(self.approver.id))
        self.assertEqual(self._api(approver, "post", "", payload_b).status_code, 403)

        # Cancel / reissue need their own permission.
        self.assertEqual(self._api(issuer, "post", f"{made.data['id']}/cancel/", {"reason": "x"}).status_code, 403)
        self.assertEqual(self._api(issuer, "post", f"{made.data['id']}/reissue/", {"reason": "x"}).status_code, 403)

        # PDF download needs view_certificates.
        self.assertEqual(self._api(self._client(self.carder), "get", f"{made.data['id']}/pdf/").status_code, 403)
        res = self._api(viewer, "get", f"{made.data['id']}/pdf/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/pdf")
        self.assertTrue(res.content.startswith(b"%PDF"))
        self.assertIn("no-store", res["Cache-Control"])

        # Settings: view for viewers, change only with manage_certificate_settings.
        self.assertEqual(self._api(viewer, "get", "settings/").status_code, 200)
        self.assertEqual(self._api(viewer, "patch", "settings/", {"signatory_name": "X"}).status_code, 403)
        owner = self._client(self.owner)
        res = self._api(owner, "patch", "settings/", {"signatory_name": "A. Principal", "signatory_title": "Principal"})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["signatory_name"], "A. Principal")

        # Another tenant cannot see or touch this tenant's certificates.
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        other_owner = self._user(other, "cert_other_owner", owner=True)
        other_client = self._client(other_owner, self.OTHER_DOMAIN)
        listing = self._api(other_client, "get", "", domain=self.OTHER_DOMAIN)
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data["count"], 0)
        for method, path in (("get", f"{made.data['id']}/"), ("get", f"{made.data['id']}/pdf/"),
                             ("post", f"{made.data['id']}/cancel/")):
            body = {"reason": "x"} if method == "post" else None
            self.assertEqual(self._api(other_client, method, path, body, domain=self.OTHER_DOMAIN).status_code, 404, path)
        # ... and the public verifier on the other tenant does not know the id either.
        res = self._api(APIClient(), "get", f"verify/certificate/{made.data['verification_id']}/", domain=self.OTHER_DOMAIN)
        self.assertEqual(res.status_code, 404)

        # Search by number and by holder name.
        found = self._api(viewer, "get", f"?search={made.data['certificate_number']}")
        self.assertEqual(found.data["count"], 1)
        found = self._api(viewer, "get", "?search=Bikash&certificate_type=transfer")
        self.assertEqual(found.data["count"], 1)

        # Audit trail.
        with tenant_context(self.school):
            actions = set(AuditLog.objects.filter(model_name__in=["Certificate", "CertificateSettings"])
                          .values_list("action", flat=True))
        self.assertTrue({"certificate_issued", "certificate_downloaded", "certificate_settings_updated"} <= actions, actions)


class CertificateLifecycleAndVerificationTest(CertificateFixtureMixin, TransactionTestCase):
    def _issue(self, client, **body):
        res = self._api(client, "post", "", body)
        self.assertEqual(res.status_code, 201, res.data)
        return res.data

    def _verify(self, verification_id):
        return self._api(APIClient(), "get", f"verify/certificate/{verification_id}/")

    def test_cancel_reissue_history_integrity_and_public_privacy(self):
        client = self._client(self.canceller)
        yesterday = (timezone.localdate() - datetime.timedelta(days=1)).isoformat()
        tc = self._issue(client, certificate_type="transfer", student_id=str(self.leaver.id),
                         leaving_date=yesterday, reason="Relocation", conduct="Good", internal_notes="Fee dispute")

        # Public verification: no auth, minimal fields, no private data.
        pub = self._verify(tc["verification_id"])
        self.assertEqual(pub.status_code, 200)
        self.assertTrue(pub.data["valid"])
        self.assertEqual(pub.data["status"], "issued")
        self.assertEqual(set(pub.data), {"valid", "status", "certificate_type", "certificate_type_label",
                                         "certificate_number", "issue_date", "school_name", "holder_name",
                                         "replaced_by_number"})
        body = str(pub.data)
        for secret in ("Secret Street", "9800000000", "2012-05-17", "CERT-002", "Relocation", "Fee dispute"):
            self.assertNotIn(secret, body)
        self.assertEqual(self._verify("not-a-real-id").status_code, 404)

        # Cancel needs a reason; then verification shows cancelled, never valid.
        self.assertEqual(self._api(client, "post", f"{tc['id']}/cancel/", {"reason": ""}).status_code, 400)
        res = self._api(client, "post", f"{tc['id']}/cancel/", {"reason": "Wrong leaving date"})
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["status"], "cancelled")
        pub = self._verify(tc["verification_id"])
        self.assertFalse(pub.data["valid"])
        self.assertEqual(pub.data["status"], "cancelled")
        self.assertEqual(self._api(client, "post", f"{tc['id']}/cancel/", {"reason": "again"}).status_code, 400)

        # A cancelled TC frees the slot; reissue the cancelled one with a fix.
        new = self._api(client, "post", f"{tc['id']}/reissue/", {"reason": "Corrected date", "leaving_date": yesterday})
        self.assertEqual(new.status_code, 201, new.data)
        self.assertNotEqual(new.data["certificate_number"], tc["certificate_number"])
        self.assertEqual(new.data["supersedes_number"], tc["certificate_number"])
        self.assertEqual(new.data["status"], "issued")
        self.assertEqual(self._verify(tc["verification_id"]).data["replaced_by_number"], new.data["certificate_number"])
        # The old record cannot be replaced twice.
        self.assertEqual(self._api(client, "post", f"{tc['id']}/reissue/", {"reason": "x"}).status_code, 400)

        # Reissuing a live certificate marks the old one superseded.
        bon = self._issue(client, certificate_type="bonafide", student_id=str(self.active.id), reason="Passport")
        re_bon = self._api(client, "post", f"{bon['id']}/reissue/", {"reason": "Typo in purpose", "new_reason": "Visa"})
        self.assertEqual(re_bon.status_code, 201, re_bon.data)
        old = self._api(client, "get", f"{bon['id']}/")
        self.assertEqual(old.data["status"], "superseded")
        self.assertEqual(old.data["superseded_by_number"], re_bon.data["certificate_number"])
        pub = self._verify(bon["verification_id"])
        self.assertFalse(pub.data["valid"])
        self.assertEqual(pub.data["status"], "superseded")
        self.assertTrue(self._verify(re_bon.data["verification_id"]).data["valid"])

        # Edits outside the workflow are detected (keyed hash), without leaking why.
        with tenant_context(self.school):
            row = Certificate.objects.get(pk=re_bon.data["id"])
            Certificate.objects.filter(pk=row.pk).update(snapshot={**row.snapshot, "holder_name": "Someone Else"})
        pub = self._verify(re_bon.data["verification_id"])
        self.assertFalse(pub.data["valid"])
        self.assertEqual(pub.data["status"], "integrity_failed")
        self.assertEqual(pub.data["holder_name"], "")

        # Audit trail for the lifecycle.
        with tenant_context(self.school):
            actions = list(AuditLog.objects.filter(model_name="Certificate").values_list("action", flat=True))
        for expected in ("certificate_issued", "certificate_cancelled", "certificate_reissued"):
            self.assertIn(expected, actions)

    def test_pdf_content_qr_payload_and_missing_branding(self):
        client = self._client(self.owner)
        bon = self._issue(client, certificate_type="bonafide", student_id=str(self.active.id), reason="Scholarship")
        tc = self._issue(client, certificate_type="transfer", student_id=str(self.leaver.id),
                         leaving_date=(timezone.localdate() - datetime.timedelta(days=1)).isoformat(),
                         reason="Relocation", internal_notes="PRIVATE-NOTE")

        drawn, qr_payloads = [], []
        real = {n: getattr(pdf.canvas.Canvas, n) for n in ("drawString", "drawCentredString", "drawRightString")}

        def spy(name):
            def wrapper(self_, x, y, text, *a, **k):
                drawn.append(str(text))
                return real[name](self_, x, y, text, *a, **k)
            return wrapper

        def spy_qr(c, payload, *a, **k):
            qr_payloads.append(payload)
            return real_qr(c, payload, *a, **k)

        real_qr = pdf._draw_qr
        with mock.patch.object(pdf.canvas.Canvas, "drawString", spy("drawString")), \
                mock.patch.object(pdf.canvas.Canvas, "drawCentredString", spy("drawCentredString")), \
                mock.patch.object(pdf.canvas.Canvas, "drawRightString", spy("drawRightString")), \
                mock.patch.object(pdf, "_draw_qr", spy_qr):
            res = self._api(client, "get", f"{tc['id']}/pdf/")
        self.assertEqual(res.status_code, 200)
        data = res.content
        self.assertTrue(data.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", data[-32:])
        self.assertEqual(len(re.findall(rb"/Type\s*/Page(?![a-z])", data)), 1)

        text = " ".join(drawn)
        for expected in (tc["certificate_number"], "Bikash Sharma", "CERT-002", "17 May 2012", "Relocation",
                         "TRANSFER CERTIFICATE", f"School {self.SCHEMA}"):
            self.assertIn(expected, text)
        for secret in ("PRIVATE-NOTE", "Secret Street", "9800000000", str(self.leaver.id)):
            self.assertNotIn(secret, text)
        self.assertEqual(len(qr_payloads), 1)
        self.assertTrue(qr_payloads[0].endswith(f"/verify/certificate/{tc['verification_id']}"), qr_payloads)
        self.assertNotIn(tc["id"], qr_payloads[0])  # internal id never in the QR

        # No DOB on a bonafide; cancelled documents carry a visible watermark.
        drawn.clear()
        with mock.patch.object(pdf.canvas.Canvas, "drawString", spy("drawString")), \
                mock.patch.object(pdf.canvas.Canvas, "drawCentredString", spy("drawCentredString")):
            self._api(client, "get", f"{bon['id']}/pdf/")
        self.assertNotIn("17 May 2012", " ".join(drawn))
        self._api(client, "post", f"{bon['id']}/cancel/", {"reason": "Test"})
        drawn.clear()
        with mock.patch.object(pdf.canvas.Canvas, "drawCentredString", spy("drawCentredString")):
            self._api(client, "get", f"{bon['id']}/pdf/")
        self.assertIn("CANCELLED", drawn)

        # Branding present: logo + signature are embedded without error.
        png = io.BytesIO()
        Image.new("RGB", (40, 40), (3, 105, 161)).save(png, format="PNG")
        from django.core.files.uploadedfile import SimpleUploadedFile
        from profiles.models import InstitutionProfile
        from .models import CertificateSettings
        with tenant_context(self.school):
            inst, _ = InstitutionProfile.objects.get_or_create(organization_id=self.school.id)
            inst.logo.save("logo.png", SimpleUploadedFile("logo.png", png.getvalue(), "image/png"))
            sett = CertificateSettings.load()
            sett.signature.save("sig.png", SimpleUploadedFile("sig.png", png.getvalue(), "image/png"))
        res = self._api(client, "get", f"{tc['id']}/pdf/")
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.content), len(data))  # images embedded
        with tenant_context(self.school):
            inst.logo.delete(save=False)
            sett.signature.delete(save=False)

    def test_id_cards_minimal_data_and_public_verification(self):
        carder = self._client(self.carder)
        res = self._api(carder, "get", f"id-cards/student/{self.active.id}/")
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data["holder_name"], "Anita Sharma")
        self.assertEqual(res.data["id_number"], "CERT-001")
        self.assertIsNone(res.data["photo"])  # missing photo handled
        self.assertIsNone(res.data["logo"])  # missing branding handled
        self.assertTrue(res.data["qr_svg"].startswith("data:image/svg+xml"))
        flat = str(res.data)
        for secret in ("Secret Street", "9800000000", "2012-05-17", "date_of_birth", "address", "phone"):
            self.assertNotIn(secret, flat)

        pdf_res = self._api(carder, "get", f"id-cards/student/{self.active.id}/pdf/")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertTrue(pdf_res.content.startswith(b"%PDF-"))
        staff_res = self._api(carder, "get", f"id-cards/staff/{self.teacher.id}/")
        self.assertEqual(staff_res.status_code, 200, staff_res.data)
        self.assertNotIn("Hidden Lane", str(staff_res.data))
        self.assertEqual(self._api(carder, "get", f"id-cards/staff/{self.teacher.id}/pdf/").status_code, 200)

        # Only active holders; unknown ids; permission.
        self.assertEqual(self._api(carder, "get", f"id-cards/student/{self.leaver.id}/").status_code, 400)
        self.assertEqual(self._api(carder, "get", f"id-cards/student/{uuid.uuid4()}/").status_code, 404)
        self.assertEqual(self._api(self._client(self.viewer), "get", f"id-cards/student/{self.active.id}/").status_code, 403)

        # Public verification via the QR token: minimal, live status, tenant-bound.
        with tenant_context(self.school):
            token = idcards.card_token("student", self.active)
        pub = self._api(APIClient(), "get", f"verify/id/{token}/")
        self.assertEqual(pub.status_code, 200)
        self.assertTrue(pub.data["valid"])
        self.assertEqual(pub.data["holder"], "Anita S.")
        self.assertEqual(set(pub.data), {"valid", "kind", "school_name", "holder", "status"})
        self.assertNotIn("CERT-001", str(pub.data))
        self.assertFalse(self._api(APIClient(), "get", f"verify/id/{token}x/").data["valid"])
        with tenant_context(self.school):
            Student.objects.filter(pk=self.active.pk).update(status="withdrawn")
        self.assertFalse(self._api(APIClient(), "get", f"verify/id/{token}/").data["valid"])

        self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        with tenant_context(self.school):
            Student.objects.filter(pk=self.active.pk).update(status="active")
        res = self._api(APIClient(), "get", f"verify/id/{token}/", domain=self.OTHER_DOMAIN)
        self.assertFalse(res.data["valid"])  # token from school A means nothing on school B

    def test_id_card_pdf_refuses_text_the_font_cannot_print_but_screen_data_still_works(self):
        with tenant_context(self.school):
            Profile.objects.filter(pk=self.active.profile_id).update(first_name="अनिता")
        carder = self._client(self.carder)
        pdf_res = self._api(carder, "get", f"id-cards/student/{self.active.id}/pdf/")
        self.assertEqual(pdf_res.status_code, 400)
        self.assertIn("cannot print", str(pdf_res.data))
        self.assertFalse(getattr(pdf_res, "content", b"").startswith(b"%PDF"))
        # The on-screen card (browser fonts) is unaffected.
        self.assertEqual(self._api(carder, "get", f"id-cards/student/{self.active.id}/").status_code, 200)
        # Latin holders still produce a PDF.
        self.assertEqual(self._api(carder, "get", f"id-cards/staff/{self.teacher.id}/pdf/").status_code, 200)


class CertificateConcurrencyTest(CertificateFixtureMixin, TransactionTestCase):
    """Real parallel PostgreSQL transactions (one connection per thread)."""

    def _race(self, callables):
        barrier = threading.Barrier(len(callables))
        results = [None] * len(callables)

        def run(i, fn):
            try:
                with tenant_context(self.school):
                    barrier.wait(timeout=30)
                    try:
                        results[i] = ("ok", fn())
                    except Exception as exc:  # noqa: BLE001 - the outcome is the assertion
                        results[i] = ("err", exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=(i, fn)) for i, fn in enumerate(callables)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=180)
            self.assertFalse(t.is_alive(), "worker thread hung")
        return results

    def test_concurrent_issuance_yields_unique_gap_free_numbers(self):
        students = [self._student(f"Con{i}", f"CERT-C{i}") for i in range(6)]
        actor = self.owner.id

        def issue(student):
            return lambda: services.issue_certificate(
                certificate_type="bonafide", subject=Student.objects.select_related("profile").get(pk=student.pk),
                data={"reason": "Race"}, issued_by_user_id=actor).certificate_number

        results = self._race([issue(s) for s in students])
        self.assertTrue(all(r[0] == "ok" for r in results), results)
        numbers = sorted(r[1] for r in results)
        year = timezone.localdate().year
        self.assertEqual(numbers, [f"BON-{year}-{n:05d}" for n in range(1, 7)])
        with tenant_context(self.school):
            self.assertEqual(Certificate.objects.count(), 6)
            seq = CertificateSequence.objects.get(certificate_type="bonafide", year=year)
            self.assertEqual(seq.last_number, 6)

    def test_concurrent_duplicate_tc_issues_exactly_one(self):
        leaving = timezone.localdate() - datetime.timedelta(days=1)

        def issue():
            return services.issue_certificate(
                certificate_type="transfer", subject=Student.objects.select_related("profile").get(pk=self.leaver.pk),
                data={"leaving_date": leaving, "reason": "Race"}, issued_by_user_id=self.owner.id,
                approved_by_user_id=self.owner.id).certificate_number

        results = self._race([issue for _ in range(4)])
        self.assertEqual([r[0] for r in results].count("ok"), 1, results)
        for outcome, value in results:
            if outcome == "err":
                self.assertIsInstance(value, services.CertificateError)
        with tenant_context(self.school):
            self.assertEqual(Certificate.objects.filter(certificate_type="transfer", status="issued").count(), 1)
            # Losing attempts roll their number back: the sequence has no gaps.
            year = timezone.localdate().year
            self.assertEqual(CertificateSequence.objects.get(certificate_type="transfer", year=year).last_number, 1)

    def test_numbering_is_per_tenant(self):
        other = self._school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        year = timezone.localdate().year
        with tenant_context(self.school), transaction.atomic():
            self.assertEqual(services.allocate_number("bonafide", year), f"BON-{year}-00001")
            self.assertEqual(services.allocate_number("bonafide", year), f"BON-{year}-00002")
        with tenant_context(other), transaction.atomic():
            self.assertEqual(services.allocate_number("bonafide", year), f"BON-{year}-00001")


class PdfLayoutRegressionTest(SimpleTestCase):
    """Regressions found by the Phase 6 visual QA (synthetic data, no database).

    Each test pins a defect that was observed in a rendered page: clipped long
    school name, missing ID number on the card PDF, silently dropped words on
    long names, doubled full stop, 'in the school' wording and a too-small QR.
    """

    LONG_SCHOOL = "The Himalayan International Residential Higher Secondary School and Research Academy of Sciences"
    LONG_NAME = "Venkatasubramanian Raghunathan Chandrasekharan Iyer-Subramaniam"

    def _cert(self, ctype="transfer", **snapshot):
        base = {"school_name": "Greenfield Model Secondary School", "holder_name": "Anita Sharma",
                "enrollment_id": "ADM-0042", "level_name": "Grade 10", "section_name": "A",
                "academic_year": "2026-27", "leaving_date": "2026-09-30", "reason": "Relocation"}
        base.update(snapshot)
        return Certificate(
            certificate_type=ctype, certificate_number="TC-2026-00001", verification_id="v" * 32,
            issue_date=datetime.date(2026, 10, 18), snapshot=base, status="issued",
            issued_by_user_id=uuid.uuid4(),
        )

    def _drawn(self, render):
        """Runs render() while recording (method, x, y, text, font, size) of every text draw."""
        drawn = []
        names = ("drawString", "drawCentredString", "drawRightString")
        real = {n: getattr(pdf.canvas.Canvas, n) for n in names}

        def spy(name):
            def wrapper(canvas_, x, y, text, *a, **k):
                drawn.append((name, x, y, str(text), canvas_._fontname, canvas_._fontsize))
                return real[name](canvas_, x, y, text, *a, **k)
            return wrapper

        with mock.patch.object(pdf.canvas.Canvas, "drawString", spy("drawString")), \
                mock.patch.object(pdf.canvas.Canvas, "drawCentredString", spy("drawCentredString")), \
                mock.patch.object(pdf.canvas.Canvas, "drawRightString", spy("drawRightString")):
            data = render()
        return data, drawn

    # --- certificate ---------------------------------------------------------------

    def test_long_school_name_wraps_inside_the_page_without_losing_words(self):
        cert = self._cert(school_name=self.LONG_SCHOOL)
        data, drawn = self._drawn(lambda: pdf.render_certificate_pdf(cert, "http://x.localhost/verify/certificate/v"))
        title_lines = [d for d in drawn if d[0] == "drawCentredString" and d[4] == pdf.FONT_BOLD and d[5] >= 13]
        school_lines = [d for d in title_lines if d[3] != "TRANSFER CERTIFICATE"]
        self.assertGreaterEqual(len(school_lines), 2)  # it wrapped
        self.assertEqual(" ".join(d[3] for d in school_lines), self.LONG_SCHOOL)  # every word kept, no ellipsis
        page_width = pdf.A4[0]
        for _, x, _, text, font, size in school_lines:
            half = pdfmetrics.stringWidth(text, font, size) / 2
            self.assertGreaterEqual(x - half, 18 * pdf.mm, text)
            self.assertLessEqual(x + half, page_width - 18 * pdf.mm, text)

    def test_body_text_never_overlaps_the_signature_block(self):
        cert = self._cert(school_name=self.LONG_SCHOOL, holder_name=self.LONG_NAME,
                          level_name="Grade 10 (Science, Advanced Mathematics and Computer Studies stream)",
                          reason="Transferred to a boarding institution abroad following relocation. " * 4, conduct="C" * 100)
        data, drawn = self._drawn(lambda: pdf.render_certificate_pdf(cert, "http://x.localhost/verify/certificate/v"))
        floor = 18 * pdf.mm + 32 * pdf.mm + 22 * pdf.mm
        body = [d for d in drawn if d[0] == "drawString" and d[5] <= 12 and d[2] > 18 * pdf.mm + 40 * pdf.mm]
        self.assertTrue(body)
        self.assertGreaterEqual(min(d[2] for d in body), floor - 1)

    def test_no_doubled_full_stop_and_no_awkward_wording_without_a_class(self):
        body = " ".join(pdf.certificate_body(self._cert(reason="Family moved.", conduct="Good.", level_name="", section_name="")))
        self.assertNotIn("..", body)
        self.assertNotIn(". .", body)
        self.assertIn("Reason for leaving: Family moved.", body)
        self.assertNotIn("in the school", body)
        for ctype, extra in (("bonafide", {"purpose": "Visa."}), ("character", {"conduct": "Excellent."})):
            text = " ".join(pdf.certificate_body(self._cert(ctype, level_name="", section_name="", **extra)))
            self.assertNotIn("..", text)
            self.assertNotIn("in the school", text)
            self.assertNotIn("studying in  ", text)

    # --- ID card ---------------------------------------------------------------------

    def _card(self, name="Anita Sharma", idno="ADM-0042", school="Greenfield Model Secondary School"):
        return {"kind": "student", "kind_label": "Student", "school_name": school, "holder_name": name,
                "id_number": idno, "details": [("Class", "Grade 10 A"), ("Year", "2026-27")]}

    def test_id_card_pdf_prints_the_id_number(self):
        data, drawn = self._drawn(lambda: pdf.render_id_card_pdf(self._card(), "http://x.localhost/verify/id/t"))
        self.assertIn("ID: ADM-0042", [d[3] for d in drawn])

    def test_id_card_long_name_and_school_keep_every_word(self):
        card = self._card(name=self.LONG_NAME, idno="ADM-0100-LONG-NUMBER", school=self.LONG_SCHOOL)
        data, drawn = self._drawn(lambda: pdf.render_id_card_pdf(card, "http://x.localhost/verify/id/t"))
        text = " ".join(d[3] for d in drawn)
        for word in self.LONG_NAME.split() + self.LONG_SCHOOL.split():
            self.assertIn(word, text)
        self.assertNotIn("...", text)
        self.assertIn("ID: ADM-0100-LONG-NUMBER", [d[3] for d in drawn])  # on one line
        card_w = pdf.ID_CARD_SIZE[0]
        for _, x, _, line, font, size in drawn:
            if x < card_w:  # left-aligned lines must not run off the card
                self.assertLessEqual(x + pdfmetrics.stringWidth(line, font, size), card_w, line)

    def test_id_card_qr_modules_are_large_enough_to_scan(self):
        token_url = "http://school1.localhost:3555/verify/id/" + "A1b2C3d4" * 4
        sizes = []
        real = pdf._draw_qr

        def spy(c, payload, x, y, size):
            sizes.append((payload, size))
            return real(c, payload, x, y, size)

        with mock.patch.object(pdf, "_draw_qr", spy):
            pdf.render_id_card_pdf(self._card(), token_url)
        payload, size = sizes[0]
        modules = segno.make(payload, error="m", micro=False).symbol_size(border=0)[0]
        module_mm = (size / pdf.mm) / (modules + 4)
        self.assertGreaterEqual(module_mm, 0.32, f"{modules} modules on {size / pdf.mm:.1f} mm")
