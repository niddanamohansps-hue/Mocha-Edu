import datetime
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TransactionTestCase
from django.utils import timezone
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section, Subject, SubjectAssignment
from accounts.models import User
from families.models import Parent, StudentParentRelation
from notifications.models import Notification
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import Instructor, StaffMember
from students.models import Student, StudentLevel

from core.dates import school_today

from .models import Homework
from .tasks import remind_due_tomorrow

PASSWORD = "Pass1234!"


class HomeworkTests(TransactionTestCase):
    SCHEMA, DOMAIN = "homework_school", "homework.localhost"

    def setUp(self):
        cache.clear()
        connection.set_schema_to_public()
        self.school = Organization.objects.create(schema_name=self.SCHEMA, name="Homework School")
        Domain.objects.create(domain=self.DOMAIN, tenant=self.school, is_primary=True)
        with tenant_context(self.school):
            program = Program.objects.create(name="School", code="HW")
            self.level = AcademicLevel.objects.create(program=program, name="Class 6", order=6)
            self.other_level = AcademicLevel.objects.create(program=program, name="Class 7", order=7)
            self.section_a = Section.objects.create(level=self.level, name="A", capacity=40)
            self.section_b = Section.objects.create(level=self.level, name="B", capacity=40)
            self.maths = Subject.objects.create(level=self.level, name="Maths", code="M6")
            self.science7 = Subject.objects.create(level=self.other_level, name="Science", code="S7")
        self.teacher = self._staff("hw_teacher", "Asha", teacher=True)
        self.other_teacher = self._staff("hw_other", "Bina", teacher=True)
        self.owner = self._user("hw_owner", "owner")
        with tenant_context(self.school):
            SubjectAssignment.objects.create(section=self.section_a, subject=self.maths,
                                             instructor=Instructor.objects.get(staff_member__profile__user_id=self.teacher.id))
        self.student_user, self.student = self._student("hw_student", "Ravi", self.section_a)
        _, self.other_student = self._student(None, "Kiran", self.section_b)
        self.parent_user = self._parent("hw_parent", self.student)

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        User.objects.filter(username__startswith="hw_").delete()

    # --- fixtures ---

    def _user(self, username, role_slug, profile=None):
        user = User.objects.create_user(username=username, email=f"{username}@hw.test", password=PASSWORD)
        with tenant_context(self.school):
            if profile is not None:
                profile.user_id = user.id
                profile.save(update_fields=["user_id"])
            role, _ = Role.objects.get_or_create(slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True})
            UserRole.objects.create(user=user, role=role)
        return user

    def _staff(self, username, name, teacher):
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name=name, last_name="T")
            staff = StaffMember.objects.create(profile=profile, employee_id=f"E-{username}", designation="Teacher")
            if teacher:
                Instructor.objects.create(staff_member=staff, specialization="Maths")
        return self._user(username, "instructor", profile)

    def _student(self, username, name, section):
        with tenant_context(self.school):
            profile = Profile.objects.create(first_name=name, last_name="S")
            student = Student.objects.create(profile=profile, enrollment_id=f"HW-{name}", status="active")
            StudentLevel.objects.create(student=student, level=section.level, section=section, academic_year="2026",
                                        is_current=True)
        user = self._user(username, "student", profile) if username else None
        return user, student

    def _parent(self, username, child):
        user = User.objects.create_user(username=username, email=f"{username}@hw.test", password=PASSWORD)
        with tenant_context(self.school):
            profile = Profile.objects.create(user_id=user.id, first_name="Parent", last_name="P")
            parent = Parent.objects.create(profile=profile)
            StudentParentRelation.objects.create(student=child, parent=parent, relation_type="mother", is_primary_contact=True)
            role, _ = Role.objects.get_or_create(slug="parent", defaults={"name": "Parent", "is_system_role": True})
            UserRole.objects.create(user=user, role=role)
        return user

    def _client(self, user):
        client = APIClient()
        assert client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD},
                           HTTP_HOST=self.DOMAIN).status_code == 200
        return client

    def _set(self, client=None, section=None, subject=None, due=None, **extra):
        due = due or (school_today() + datetime.timedelta(days=2))
        return (client or self._client(self.teacher)).post("/api/homework/", {
            "section": str((section or self.section_a).id), "subject": str((subject or self.maths).id),
            "title": "Exercise 4.2", "details": "Questions 1-10", "due_date": str(due), **extra},
            format="json", HTTP_HOST=self.DOMAIN)

    # --- tests ---

    def test_the_default_roles_can_use_homework(self):
        with tenant_context(self.school):
            def has(slug, code):
                return Role.objects.get(slug=slug).permissions.filter(codename=code).exists()
            self.assertTrue(has("instructor", "manage_homework"))
            self.assertTrue(has("student", "view_own_homework"))
            self.assertTrue(has("parent", "view_child_homework"))

    def test_teacher_sets_homework_only_for_their_own_class_and_subject(self):
        response = self._set()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["section_name"], "Class 6 A")
        self.assertEqual(self._set(section=self.section_b).status_code, 403)
        self.assertEqual(self._set(client=self._client(self.other_teacher)).status_code, 403)

    def test_bad_input_is_refused(self):
        self.assertEqual(self._set(due=school_today() - datetime.timedelta(days=1)).status_code, 400)
        owner = self._client(self.owner)
        self.assertEqual(self._set(client=owner, subject=self.science7).status_code, 400)  # not taught in Class 6

    def test_students_and_parents_are_notified(self):
        self._set()
        with tenant_context(self.school):
            notified = set(Notification.objects.filter(category="homework").values_list("recipient_user_id", flat=True))
        self.assertEqual(notified, {self.student_user.id, self.parent_user.id})

    def test_student_and_parent_see_and_mark_it(self):
        homework_id = self._set().data["id"]
        student = self._client(self.student_user)
        mine = student.get("/api/homework/my/", HTTP_HOST=self.DOMAIN)
        self.assertEqual([h["id"] for h in mine.data["homework"]], [homework_id])
        self.assertIsNone(mine.data["homework"][0]["done_at"])
        student.post(f"/api/homework/{homework_id}/mark/", {"done": True}, format="json", HTTP_HOST=self.DOMAIN)

        parent = self._client(self.parent_user)
        child = parent.get("/api/homework/my/", {"student": str(self.student.id)}, HTTP_HOST=self.DOMAIN)
        self.assertIsNotNone(child.data["homework"][0]["done_at"])
        undo = parent.post(f"/api/homework/{homework_id}/mark/", {"student": str(self.student.id), "done": False},
                           format="json", HTTP_HOST=self.DOMAIN)
        self.assertIsNone(undo.data["done_at"])
        self.assertIsNotNone(undo.data["seen_at"])

    def test_a_parent_cannot_see_another_childs_homework(self):
        self._set()
        parent = self._client(self.parent_user)
        response = parent.get("/api/homework/my/", {"student": str(self.other_student.id)}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(response.status_code, 404)

    def test_teachers_see_only_their_classes_and_the_owner_sees_all(self):
        self._set()
        self._set(client=self._client(self.owner), section=self.section_b)
        teacher = self._client(self.teacher).get("/api/homework/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(teacher.data["count"], 1)
        owner = self._client(self.owner).get("/api/homework/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(owner.data["count"], 2)

    def test_progress_and_overview(self):
        homework_id = self._set().data["id"]
        self._client(self.student_user).post(f"/api/homework/{homework_id}/mark/", {"done": True}, format="json",
                                             HTTP_HOST=self.DOMAIN)
        progress = self._client(self.teacher).get(f"/api/homework/{homework_id}/progress/", HTTP_HOST=self.DOMAIN)
        self.assertEqual((progress.data["seen"], progress.data["done"], len(progress.data["students"])), (1, 1, 1))
        overview = self._client(self.owner).get("/api/homework/overview/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(overview.data["without_homework"], 1)  # section B got none today

    def test_cancelled_homework_disappears_for_students(self):
        homework_id = self._set().data["id"]
        self._client(self.teacher).post(f"/api/homework/{homework_id}/cancel/", HTTP_HOST=self.DOMAIN)
        mine = self._client(self.student_user).get("/api/homework/my/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(mine.data["homework"], [])

    def test_attachments_upload_and_download(self):
        homework_id = self._set().data["id"]
        teacher = self._client(self.teacher)
        upload = teacher.post(f"/api/homework/{homework_id}/attachments/",
                              {"file": SimpleUploadedFile("sheet.pdf", b"%PDF-1.4 test")}, format="multipart",
                              HTTP_HOST=self.DOMAIN)
        self.assertEqual(upload.status_code, 201, upload.data)
        bad = teacher.post(f"/api/homework/{homework_id}/attachments/",
                           {"file": SimpleUploadedFile("run.exe", b"MZ")}, format="multipart", HTTP_HOST=self.DOMAIN)
        self.assertEqual(bad.status_code, 400)
        url = f"/api/homework/{homework_id}/attachments/{upload.data['id']}/"
        self.assertEqual(self._client(self.student_user).get(url, HTTP_HOST=self.DOMAIN).status_code, 200)
        self.assertEqual(self._client(self.other_teacher).get(url, HTTP_HOST=self.DOMAIN).status_code, 404)

    def test_reminder_goes_once_and_skips_students_who_are_done(self):
        tomorrow = school_today() + datetime.timedelta(days=1)
        homework_id = self._set(due=tomorrow).data["id"]
        with tenant_context(self.school):
            Notification.objects.all().delete()
            self.assertEqual(remind_due_tomorrow(), 1)
            self.assertEqual(remind_due_tomorrow(), 0)  # already sent today
            self.assertEqual(set(Notification.objects.values_list("recipient_user_id", flat=True)),
                             {self.student_user.id, self.parent_user.id})
        cache.clear()
        self._client(self.student_user).post(f"/api/homework/{homework_id}/mark/", {"done": True}, format="json",
                                             HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            self.assertEqual(remind_due_tomorrow(), 0)  # everyone in the class is done

    def test_options_list_only_what_the_teacher_may_set(self):
        options = self._client(self.teacher).get("/api/homework/options/", HTTP_HOST=self.DOMAIN).data
        self.assertEqual([(o["section_name"], o["subject_name"]) for o in options], [("Class 6 A", "Maths")])
        owner = self._client(self.owner).get("/api/homework/options/", HTTP_HOST=self.DOMAIN).data
        self.assertEqual(len(owner), 2)  # both Class 6 sections x Maths

    def test_a_teachers_class_overview_lists_only_their_classes(self):
        overview = self._client(self.teacher).get("/api/homework/overview/", HTTP_HOST=self.DOMAIN).data
        self.assertEqual([r["name"] for r in overview["sections"]], ["Class 6 A"])
