import datetime
import shutil
import tempfile
import uuid as uuid_module

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase, override_settings
from django_tenants.utils import tenant_context
from rest_framework.test import APIRequestFactory, force_authenticate

from organizations.models import Domain, Organization
from roles.models import Role, UserRole
from roles.signals import seed_default_roles
from staff.models import Instructor, StaffMember

from .models import Applicant, Interview, JobOpening
from .views import ApplicantViewSet, InterviewViewSet, JobOpeningViewSet, RecruitmentSummaryView

User = get_user_model()

TEMP_MEDIA = tempfile.mkdtemp(prefix="recruitment_media_")


def tearDownModule():
    shutil.rmtree(TEMP_MEDIA, ignore_errors=True)


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class RecruitmentTests(TransactionTestCase):
    def setUp(self):
        suffix = uuid_module.uuid4().hex[:8]
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=f"rec_{suffix}", name="Recruit Test School")
        Domain.objects.create(domain=f"rec-{suffix}.localhost", tenant=self.school, is_primary=True)
        self.factory = APIRequestFactory()
        with tenant_context(self.school):
            seed_default_roles()
            self.owner = self._user("owner", "owner")
            # The staff role gets no recruitment permission by default: applicants' details are HR-only.
            self.clerk = self._user("staff", "clerk")

    def _user(self, role_slug, label):
        user = User.objects.create_user(
            username=f"{label}_{uuid_module.uuid4().hex[:6]}@school.com",
            email=f"{label}@school.com",
            password="Password123!",
        )
        UserRole.objects.create(user=user, role=Role.objects.get(slug=role_slug))
        return user

    def _call(self, viewset, mapping, method, path, user, data=None, fmt="json", **kwargs):
        request = getattr(self.factory, method)(path, data, format=fmt) if method != "get" else self.factory.get(path, data)
        request.tenant = self.school
        force_authenticate(request, user=user)
        return viewset.as_view(mapping)(request, **kwargs)

    def _opening(self, **extra):
        fields = {"title": "Maths Teacher", "position_type": "instructor", "vacancies": 1, "specialization": "Mathematics"}
        fields.update(extra)
        response = self._call(JobOpeningViewSet, {"post": "create"}, "post", "/api/recruitment/openings/", self.owner, fields)
        self.assertEqual(response.status_code, 201, response.data)
        return JobOpening.objects.get(pk=response.data["id"])

    def _publish(self, opening):
        response = self._call(
            JobOpeningViewSet, {"post": "publish"}, "post", "/x/", self.owner, pk=str(opening.pk)
        )
        self.assertEqual(response.status_code, 200, response.data)

    def _apply(self, opening, **extra):
        fields = {"opening": str(opening.pk), "first_name": "Asha", "last_name": "Rao", "email": "asha@example.com", "gender": "female"}
        fields.update(extra)
        return self._call(ApplicantViewSet, {"post": "create"}, "post", "/api/recruitment/applicants/", self.owner, fields)

    def _move(self, applicant, stage, **extra):
        return self._call(
            ApplicantViewSet, {"post": "move"}, "post", "/x/", self.owner, {"stage": stage, **extra}, pk=str(applicant.pk)
        )

    def _to_offered(self, applicant):
        for stage in ("shortlisted", "interview", "offered"):
            self.assertEqual(self._move(applicant, stage).status_code, 200)

    def test_recruitment_data_is_limited_to_users_with_the_permission(self):
        with tenant_context(self.school):
            opening = self._opening()
            for viewset, mapping, path in (
                (JobOpeningViewSet, {"get": "list"}, "/api/recruitment/openings/"),
                (ApplicantViewSet, {"get": "list"}, "/api/recruitment/applicants/"),
                (InterviewViewSet, {"get": "list"}, "/api/recruitment/interviews/"),
            ):
                self.assertEqual(self._call(viewset, mapping, "get", path, self.clerk).status_code, 403, path)
                self.assertEqual(self._call(viewset, mapping, "get", path, self.owner).status_code, 200, path)
            request = self.factory.get("/api/recruitment/summary/")
            request.tenant = self.school
            force_authenticate(request, user=self.clerk)
            self.assertEqual(RecruitmentSummaryView.as_view()(request).status_code, 403)
            denied = self._call(
                JobOpeningViewSet, {"post": "publish"}, "post", "/x/", self.clerk, pk=str(opening.pk)
            )
            self.assertEqual(denied.status_code, 403)

    def test_applications_only_open_once_the_opening_is_published(self):
        with tenant_context(self.school):
            opening = self._opening()
            self.assertEqual(self._apply(opening).status_code, 400)
            self._publish(opening)
            self.assertEqual(self._apply(opening).status_code, 201)
            past = self._opening(title="Old post", last_date=datetime.date.today() - datetime.timedelta(days=1))
            self._publish(past)
            self.assertEqual(self._apply(past).status_code, 400)

    def test_the_same_email_cannot_apply_twice_to_one_opening(self):
        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            self.assertEqual(self._apply(opening).status_code, 201)
            again = self._apply(opening, email="ASHA@example.com")
            self.assertEqual(again.status_code, 400)
            self.assertIn("email", again.data)
            # Applicants with no email are not treated as duplicates of each other.
            self.assertEqual(self._apply(opening, email="", first_name="Ben").status_code, 201)
            self.assertEqual(self._apply(opening, email="", first_name="Cara").status_code, 201)

    def test_pipeline_enforces_the_order_and_keeps_a_history(self):
        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            applicant = Applicant.objects.get(pk=self._apply(opening).data["id"])

            self.assertEqual(self._move(applicant, "offered").status_code, 400)
            self.assertEqual(self._move(applicant, "hired").status_code, 400)
            self.assertEqual(self._move(applicant, "rejected").status_code, 400)  # needs a reason
            self._to_offered(applicant)
            self.assertEqual(self._move(applicant, "rejected", rejection_reason="Declined the offer").status_code, 200)
            applicant.refresh_from_db()
            self.assertEqual(applicant.stage, "rejected")
            self.assertEqual(applicant.rejection_reason, "Declined the offer")
            self.assertEqual(self._move(applicant, "applied").status_code, 200)  # a rejection can be reopened
            applicant.refresh_from_db()
            self.assertEqual(applicant.rejection_reason, "")

            trail = [(e.from_stage, e.to_stage) for e in applicant.events.all()]
            self.assertEqual(trail[0], ("", "applied"))
            self.assertEqual(trail[1:], [("applied", "shortlisted"), ("shortlisted", "interview"), ("interview", "offered"), ("offered", "rejected"), ("rejected", "applied")])

    def test_hiring_an_instructor_creates_the_records_and_fills_the_opening(self):
        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            applicant = Applicant.objects.get(pk=self._apply(opening, qualification="M.Sc", experience_years=4).data["id"])

            early = self._call(ApplicantViewSet, {"post": "hire"}, "post", "/x/", self.owner, {}, pk=str(applicant.pk))
            self.assertEqual(early.status_code, 400)  # not offered yet

            self._to_offered(applicant)
            denied = self._call(ApplicantViewSet, {"post": "hire"}, "post", "/x/", self.clerk, {}, pk=str(applicant.pk))
            self.assertEqual(denied.status_code, 403)

            response = self._call(
                ApplicantViewSet, {"post": "hire"}, "post", "/x/", self.owner,
                {"joining_date": "2027-04-01"}, pk=str(applicant.pk),
            )
            self.assertEqual(response.status_code, 201, response.data)
            applicant.refresh_from_db()
            opening.refresh_from_db()
            self.assertEqual(applicant.stage, "hired")
            staff = applicant.hired_staff
            self.assertEqual(staff.profile.first_name, "Asha")
            self.assertEqual(staff.qualification, "M.Sc")
            self.assertEqual(staff.experience_years, 4)
            self.assertEqual(Instructor.objects.get(staff_member=staff).specialization, "Mathematics")
            self.assertEqual(opening.status, "closed")  # the only vacancy is filled

    def test_hiring_general_staff_uses_the_opening_title_as_designation(self):
        with tenant_context(self.school):
            opening = self._opening(title="Front Desk Executive", position_type="staff", department="Admin", vacancies=2)
            self._publish(opening)
            first = Applicant.objects.get(pk=self._apply(opening).data["id"])
            second = Applicant.objects.get(pk=self._apply(opening, email="b@example.com", first_name="Bina").data["id"])
            for applicant in (first, second):
                self._to_offered(applicant)
            self.assertEqual(
                self._call(ApplicantViewSet, {"post": "hire"}, "post", "/x/", self.owner, {}, pk=str(first.pk)).status_code, 201
            )
            opening.refresh_from_db()
            self.assertEqual(opening.status, "open")  # one of two vacancies still free
            staff = StaffMember.objects.get(recruitment_application=first)
            self.assertEqual((staff.designation, staff.department), ("Front Desk Executive", "Admin"))
            self.assertEqual(
                self._call(ApplicantViewSet, {"post": "hire"}, "post", "/x/", self.owner, {}, pk=str(second.pk)).status_code, 201
            )
            opening.refresh_from_db()
            self.assertEqual(opening.status, "closed")

    def test_hiring_needs_a_gender_and_cannot_exceed_the_vacancies(self):
        with tenant_context(self.school):
            opening = self._opening(position_type="staff")
            self._publish(opening)
            no_gender = Applicant.objects.get(pk=self._apply(opening, gender="").data["id"])
            self._to_offered(no_gender)
            hire = lambda a, body: self._call(ApplicantViewSet, {"post": "hire"}, "post", "/x/", self.owner, body, pk=str(a.pk))
            self.assertEqual(hire(no_gender, {}).status_code, 400)
            self.assertEqual(hire(no_gender, {"gender": "male"}).status_code, 201)

            # The single vacancy is now filled, so another applicant cannot be hired against it.
            JobOpening.objects.filter(pk=opening.pk).update(status="open")
            other = Applicant.objects.get(pk=self._apply(opening, email="o@example.com", first_name="Om").data["id"])
            self._to_offered(other)
            self.assertEqual(hire(other, {}).status_code, 400)
            other.refresh_from_db()
            self.assertEqual(other.stage, "offered")

    def test_resume_is_validated_and_only_served_to_permitted_users(self):
        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            request_data = {
                "opening": str(opening.pk), "first_name": "Asha", "last_name": "Rao",
                "resume": SimpleUploadedFile("cv.exe", b"MZ", content_type="application/octet-stream"),
            }
            rejected = self._call(ApplicantViewSet, {"post": "create"}, "post", "/x/", self.owner, request_data, fmt="multipart")
            self.assertEqual(rejected.status_code, 400)
            self.assertIn("resume", rejected.data)

            request_data["resume"] = SimpleUploadedFile("cv.pdf", b"%PDF-1.4 test", content_type="application/pdf")
            created = self._call(ApplicantViewSet, {"post": "create"}, "post", "/x/", self.owner, request_data, fmt="multipart")
            self.assertEqual(created.status_code, 201, created.data)
            self.assertNotIn("/media/", created.data["resume_url"])
            self.assertNotIn("resume", created.data)

            applicant_id = created.data["id"]
            served = self._call(ApplicantViewSet, {"get": "resume"}, "get", "/x/", self.owner, pk=applicant_id)
            self.assertEqual(served.status_code, 200)
            self.assertEqual(b"".join(served.streaming_content), b"%PDF-1.4 test")
            denied = self._call(ApplicantViewSet, {"get": "resume"}, "get", "/x/", self.clerk, pk=applicant_id)
            self.assertEqual(denied.status_code, 403)

    def test_interviews_are_scored_once_and_feed_the_average(self):
        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            applicant = Applicant.objects.get(pk=self._apply(opening).data["id"])
            when = "2027-01-15T10:00:00Z"
            made = self._call(
                InterviewViewSet, {"post": "create"}, "post", "/x/", self.owner,
                {"applicant": str(applicant.pk), "round_name": "Demo class", "scheduled_at": when},
            )
            self.assertEqual(made.status_code, 201, made.data)
            interview = Interview.objects.get(pk=made.data["id"])

            complete = lambda body: self._call(
                InterviewViewSet, {"post": "complete"}, "post", "/x/", self.owner, body, pk=str(interview.pk)
            )
            self.assertEqual(complete({"score": "11"}).status_code, 400)
            self.assertEqual(complete({"score": "8.5", "feedback": "Strong"}).status_code, 200)
            self.assertEqual(complete({"score": "2"}).status_code, 400)  # already completed
            shown = self._call(ApplicantViewSet, {"get": "retrieve"}, "get", "/x/", self.owner, pk=str(applicant.pk))
            self.assertEqual(shown.data["average_score"], 8.5)

    def test_openings_with_applicants_are_closed_not_deleted(self):
        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            self._apply(opening)
            gone = self._call(JobOpeningViewSet, {"delete": "destroy"}, "delete", "/x/", self.owner, pk=str(opening.pk))
            self.assertEqual(gone.status_code, 400)
            closed = self._call(JobOpeningViewSet, {"post": "close"}, "post", "/x/", self.owner, pk=str(opening.pk))
            self.assertEqual(closed.data["status"], "closed")
            edit = self._call(JobOpeningViewSet, {"patch": "partial_update"}, "patch", "/x/", self.owner, {"title": "New"}, pk=str(opening.pk))
            self.assertEqual(edit.status_code, 400)
            reopen = self._call(JobOpeningViewSet, {"post": "publish"}, "post", "/x/", self.owner, pk=str(opening.pk))
            self.assertEqual(reopen.status_code, 400)

    def _public(self, view, method, data=None, fmt="multipart"):
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get("/x/") if method == "get" else self.factory.post("/x/", data, format=fmt)
        request.tenant = self.school
        request.user = AnonymousUser()
        return view.as_view()(request)

    def _public_form(self, opening, **extra):
        form = {
            "opening": str(opening.pk), "first_name": "Ravi", "last_name": "Kumar",
            "email": "Ravi@Example.com", "phone": "9876543210",
            "resume": SimpleUploadedFile("cv.pdf", b"%PDF-1.4 real", content_type="application/pdf"),
        }
        form.update(extra)
        return form

    def test_public_page_lists_only_positions_that_are_taking_applications(self):
        from .views import PublicOpeningsView

        with tenant_context(self.school):
            live = self._opening(title="Live post")
            self._publish(live)
            self._opening(title="Draft post")  # never published
            expired = self._opening(title="Expired post", last_date=datetime.date.today() - datetime.timedelta(days=1))
            self._publish(expired)
            self._apply(live)

            response = self._public(PublicOpeningsView, "get")
            self.assertEqual(response.status_code, 200)
            self.assertEqual([o["title"] for o in response.data], ["Live post"])
            # Nothing about the school's own hiring state leaks to visitors.
            for hidden in ("applicant_count", "hired_count", "vacancies", "status", "created_by_id"):
                self.assertNotIn(hidden, response.data[0])

    def test_a_visitor_can_apply_and_lands_in_the_applied_stage(self):
        from .views import PublicApplyView

        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            response = self._public(PublicApplyView, "post", self._public_form(opening))
            self.assertEqual(response.status_code, 201, response.data)
            self.assertEqual(set(response.data), {"success", "message", "reference", "access_code"})  # no internal ids

            applicant = Applicant.objects.get()
            self.assertEqual((applicant.stage, applicant.source, applicant.email), ("applied", "Careers page", "ravi@example.com"))
            self.assertTrue(applicant.resume)
            self.assertEqual([(e.from_stage, e.to_stage) for e in applicant.events.all()], [("", "applied")])

    def test_public_apply_rejects_unusable_requests(self):
        from .views import PublicApplyView

        with tenant_context(self.school):
            opening = self._opening()
            draft_response = self._public(PublicApplyView, "post", self._public_form(opening))
            self.assertEqual(draft_response.status_code, 400)  # not published yet
            self._publish(opening)

            for label, extra in (
                ("no email", {"email": ""}),
                ("no phone", {"phone": ""}),
                ("not a pdf inside", {"resume": SimpleUploadedFile("cv.pdf", b"MZ not a pdf", content_type="application/pdf")}),
                ("wrong type", {"resume": SimpleUploadedFile("cv.exe", b"%PDF-1.4", content_type="application/pdf")}),
                ("absurd experience", {"experience_years": "900"}),
            ):
                response = self._public(PublicApplyView, "post", self._public_form(opening, **extra))
                self.assertEqual(response.status_code, 400, label)
            self.assertEqual(Applicant.objects.count(), 0)

    def test_public_apply_does_not_reveal_who_already_applied_and_ignores_bots(self):
        from .views import PublicApplyView

        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            first = self._public(PublicApplyView, "post", self._public_form(opening))
            again = self._public(PublicApplyView, "post", self._public_form(opening, first_name="Different"))
            self.assertEqual((first.status_code, again.status_code), (201, 201))
            self.assertEqual(set(first.data), set(again.data))  # same shape, so the reply gives nothing away
            self.assertNotEqual(first.data["reference"], again.data["reference"])
            self.assertEqual(Applicant.objects.count(), 1)
            self.assertEqual(Applicant.objects.get().first_name, "Ravi")

            bot = self._public(PublicApplyView, "post", self._public_form(opening, email="bot@example.com", website="http://spam"))
            self.assertEqual(bot.status_code, 201)
            self.assertFalse(Applicant.objects.filter(email="bot@example.com").exists())

    def test_staff_resume_upload_also_checks_the_file_contents(self):
        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            fake = {
                "opening": str(opening.pk), "first_name": "A", "last_name": "B",
                "resume": SimpleUploadedFile("cv.pdf", b"MZ not a pdf", content_type="application/pdf"),
            }
            response = self._call(ApplicantViewSet, {"post": "create"}, "post", "/x/", self.owner, fake, fmt="multipart")
            self.assertEqual(response.status_code, 400)
            self.assertIn("resume", response.data)

    def _status(self, reference, code):
        from django.contrib.auth.models import AnonymousUser
        from .views import PublicStatusView

        request = self.factory.post("/x/", {"reference": reference, "access_code": code}, format="json")
        request.tenant = self.school
        request.user = AnonymousUser()
        return PublicStatusView.as_view()(request)

    def test_a_candidate_can_follow_their_application_with_the_reference_and_code(self):
        from .views import PublicApplyView

        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            reply = self._public(PublicApplyView, "post", self._public_form(opening)).data
            applicant = Applicant.objects.get()
            self.assertNotIn(reply["access_code"], applicant.access_token_hash)  # only a hash is stored

            shown = self._status(reply["reference"], reply["access_code"])
            self.assertEqual(shown.status_code, 200)
            self.assertEqual((shown.data["status"], shown.data["position"]), ("Received", "Maths Teacher"))
            self.assertNotIn("email", shown.data)

            self.assertEqual(self._status(reply["reference"], "wrong-code").status_code, 404)
            self.assertEqual(self._status("JOB-00000000", reply["access_code"]).status_code, 404)
            self.assertEqual(self._status(reply["reference"].lower(), reply["access_code"]).status_code, 200)

            # Interview details appear while the interview is ahead, and a rejection shows as a plain outcome.
            for stage in ("shortlisted", "interview"):
                self._move(applicant, stage)
            self._call(
                InterviewViewSet, {"post": "create"}, "post", "/x/", self.owner,
                {"applicant": str(applicant.pk), "round_name": "Demo class", "scheduled_at": "2027-02-01T09:00:00Z",
                 "location_or_url": "Room 4"},
            )
            interview = self._status(reply["reference"], reply["access_code"]).data
            self.assertEqual(interview["status"], "Interview stage")
            self.assertEqual((interview["interview"]["round"], interview["interview"]["location_or_url"]), ("Demo class", "Room 4"))
            self._move(applicant, "rejected", rejection_reason="Internal note that must stay private")
            rejected = self._status(reply["reference"], reply["access_code"]).data
            self.assertEqual(rejected["status"], "Not selected")
            self.assertNotIn("Internal note", str(rejected))

    def test_duplicate_applicants_receive_credentials_that_match_nothing(self):
        from .views import PublicApplyView

        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            self._public(PublicApplyView, "post", self._public_form(opening))
            again = self._public(PublicApplyView, "post", self._public_form(opening)).data
            self.assertEqual(self._status(again["reference"], again["access_code"]).status_code, 404)

    def test_the_confirmation_email_is_queued_with_the_reference_and_code(self):
        from notifications.models import EmailOutboxEvent
        from .views import PublicApplyView

        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            reply = self._public(PublicApplyView, "post", self._public_form(opening)).data
            event = EmailOutboxEvent.objects.get(to_email="ravi@example.com")
            self.assertIn(reply["reference"], event.body)
            self.assertIn(reply["access_code"], event.body)
            self.assertIn("/careers/status", event.body)
            # A repeat application or a bot sends no email.
            self._public(PublicApplyView, "post", self._public_form(opening))
            self._public(PublicApplyView, "post", self._public_form(opening, email="bot@example.com", website="x"))
            self.assertEqual(EmailOutboxEvent.objects.count(), 1)

    def test_captcha_is_enforced_only_when_configured(self):
        from unittest import mock

        import requests

        from .views import PublicApplyView

        with tenant_context(self.school):
            opening = self._opening()
            self._publish(opening)
            with override_settings(TURNSTILE_SECRET_KEY="test-secret"):
                missing = self._public(PublicApplyView, "post", self._public_form(opening))
                self.assertEqual(missing.status_code, 400)
                self.assertIn("captcha", missing.data)

                with mock.patch("recruitment.captcha.requests.post") as post:
                    post.return_value.json.return_value = {"success": False}
                    failed = self._public(PublicApplyView, "post", self._public_form(opening, **{"cf-turnstile-response": "bad"}))
                    self.assertEqual(failed.status_code, 400)
                    post.return_value.json.return_value = {"success": True}
                    passed = self._public(PublicApplyView, "post", self._public_form(opening, **{"cf-turnstile-response": "good"}))
                    self.assertEqual(passed.status_code, 201)
                with mock.patch("recruitment.captcha.requests.post", side_effect=requests.ConnectionError("down")):
                    down = self._public(PublicApplyView, "post", self._public_form(opening, email="x@example.com", **{"cf-turnstile-response": "t"}))
                    self.assertEqual(down.status_code, 400)  # fails closed
            self.assertEqual(Applicant.objects.count(), 1)
