import datetime
import uuid

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from accounts.models import User
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import Instructor, StaffMember

from .models import AcademicLevel, Program, Section, Subject, SubjectAssignment

PASSWORD = "Pass1234!"
CHAR_VARYING_OID = 1043  # PostgreSQL varchar type_code
UUID_OID = 2950  # PostgreSQL uuid type_code (confirmed via pg_type, matches AcademicYear.id)


class AcademicsFixtureMixin:
    """Tenant + user fixtures for academics API tests (mirrors examinations/tests.py)."""

    SCHEMA_NAME = "acad_p04_school"
    DOMAIN = "academics-p04.localhost"

    def _build_school(self, schema_name, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=f"School {schema_name}")
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, codenames=None, owner=False):
        user = User.objects.create_user(username=username, email=f"{username}@p04.test", password=PASSWORD)
        with tenant_context(self.school):
            if owner:
                role = Role.objects.get(slug="owner")
            else:
                slug = f"p04-{uuid.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _client_as(self, user, host):
        client = APIClient()
        resp = client.post("/api/auth/login/", {"username": user.username, "password": PASSWORD}, HTTP_HOST=host)
        assert resp.status_code == 200, resp.data
        return client

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=self.TENANT_SCHEMAS):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="acad_").delete()

    def setUp(self):
        self.addCleanup(self._cleanup)
        self.school = self._build_school(self.SCHEMA_NAME, self.DOMAIN)
        with tenant_context(self.school):
            self.program = Program.objects.create(name="Senior Secondary", code="SS")
            self.level = AcademicLevel.objects.create(program=self.program, name="Class 9", order=9)
            self.section_a = Section.objects.create(level=self.level, name="A", capacity=40)
            self.section_b = Section.objects.create(level=self.level, name="B", capacity=40)
            self.subject = Subject.objects.create(level=self.level, name="Mathematics", code="MTH")
            profile = Profile.objects.create(first_name="Ivy", last_name="Teach")
            staff = StaffMember.objects.create(profile=profile, employee_id="EMP-ACAD-1", designation="Teacher")
            self.instructor = Instructor.objects.create(staff_member=staff, specialization="Math")

        self.owner = self._build_user("acad_owner", owner=True)
        self.viewer = self._build_user("acad_viewer", codenames=["view_program", "view_subject_assignment", "view_section"])
        self.stranger = self._build_user("acad_stranger", codenames=[])


class AcademicsApiTests(AcademicsFixtureMixin, TransactionTestCase):
    TENANT_SCHEMAS = ["acad_p04_school", "acad_p04_other"]

    # --- Authentication and RBAC -------------------------------------------

    def test_unauthenticated_request_is_rejected(self):
        resp = APIClient().get("/api/academics/programs/", HTTP_HOST=self.DOMAIN)
        self.assertIn(resp.status_code, (401, 403))

    def test_user_without_permission_cannot_list_programs(self):
        client = self._client_as(self.stranger, self.DOMAIN)
        resp = client.get("/api/academics/programs/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_view_only_user_can_read_but_not_create(self):
        client = self._client_as(self.viewer, self.DOMAIN)
        self.assertEqual(client.get("/api/academics/programs/", HTTP_HOST=self.DOMAIN).status_code, 200)
        resp = client.post(
            "/api/academics/programs/", {"name": "Arts", "code": "ART"}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 403)
        with tenant_context(self.school):
            self.assertFalse(Program.objects.filter(code="ART").exists())

    def test_owner_can_create_program(self):
        client = self._client_as(self.owner, self.DOMAIN)
        resp = client.post(
            "/api/academics/programs/", {"name": "Commerce", "code": "COM"}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["code"], "COM")

    # --- Validation and uniqueness -----------------------------------------

    def test_duplicate_program_code_rejected(self):
        client = self._client_as(self.owner, self.DOMAIN)
        resp = client.post(
            "/api/academics/programs/", {"name": "Another", "code": "SS"}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("code", resp.data)

    def test_duplicate_level_name_within_program_rejected(self):
        client = self._client_as(self.owner, self.DOMAIN)
        resp = client.post(
            "/api/academics/levels/",
            {"program": str(self.program.id), "name": "Class 9", "order": 10},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_duplicate_section_name_within_level_rejected(self):
        client = self._client_as(self.owner, self.DOMAIN)
        resp = client.post(
            "/api/academics/sections/",
            {"level": str(self.level.id), "name": "A", "capacity": 30},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_subject_code_unique_per_level_but_reusable_across_levels(self):
        """Subject.code is NOT globally unique: the same code may appear in another level."""
        client = self._client_as(self.owner, self.DOMAIN)
        with tenant_context(self.school):
            other_level = AcademicLevel.objects.create(program=self.program, name="Class 10", order=10)
        same_code_other_level = client.post(
            "/api/academics/subjects/",
            {"level": str(other_level.id), "name": "Mathematics", "code": "MTH"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(same_code_other_level.status_code, 201, same_code_other_level.data)

        duplicate_in_same_level = client.post(
            "/api/academics/subjects/",
            {"level": str(self.level.id), "name": "Maths Again", "code": "MTH"},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(duplicate_in_same_level.status_code, 400)

    # --- Relationships ------------------------------------------------------

    def test_section_list_includes_level_and_program_names(self):
        client = self._client_as(self.viewer, self.DOMAIN)
        resp = client.get("/api/academics/sections/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        rows = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
        row = next(r for r in rows if r["name"] == "A")
        self.assertEqual(row["level_name"], "Class 9")
        self.assertEqual(row["program_name"], "Senior Secondary")

    def test_one_instructor_per_subject_per_section(self):
        client = self._client_as(self.owner, self.DOMAIN)
        payload = {
            "section": str(self.section_a.id),
            "subject": str(self.subject.id),
            "instructor": str(self.instructor.id),
        }
        first = client.post("/api/academics/assignments/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(first.status_code, 201, first.data)
        second = client.post("/api/academics/assignments/", payload, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(second.status_code, 400)

    def test_assignment_filter_by_section_returns_only_that_section(self):
        with tenant_context(self.school):
            SubjectAssignment.objects.create(section=self.section_a, subject=self.subject, instructor=self.instructor)
            SubjectAssignment.objects.create(section=self.section_b, subject=self.subject, instructor=self.instructor)
        client = self._client_as(self.viewer, self.DOMAIN)
        resp = client.get(
            f"/api/academics/assignments/?section={self.section_a.id}", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        rows = resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data
        self.assertEqual(len(rows), 1)
        self.assertEqual(str(rows[0]["section"]), str(self.section_a.id))

    # --- Tenant isolation ---------------------------------------------------

    def test_program_created_in_one_school_is_invisible_to_another(self):
        other = self._build_school("acad_p04_other", "academics-p04-other.localhost")
        try:
            with tenant_context(other):
                Program.objects.create(name="Other School Only", code="OTHER")

            client = self._client_as(self.owner, self.DOMAIN)
            resp = client.get("/api/academics/programs/", HTTP_HOST=self.DOMAIN)
            codes = {r["code"] for r in (resp.data["results"] if "results" in resp.data else resp.data)}
            self.assertNotIn("OTHER", codes)
            self.assertIn("SS", codes)
        finally:
            connection.set_schema_to_public()


class AcademicYearModelTests(AcademicsFixtureMixin, TransactionTestCase):
    """Phase 1.2A: tenant-local AcademicYear domain model."""

    OTHER_SCHEMA = "acad_p04_other"
    OTHER_DOMAIN = "academics-p04-other.localhost"
    TENANT_SCHEMAS = ["acad_p04_school", "acad_p04_other"]

    def _make(self, name="2026-27", start=(2026, 4, 1), end=(2027, 3, 31), current=False, school=None):
        from .models import AcademicYear

        school = school or self.school
        with tenant_context(school):
            return AcademicYear.objects.create(
                name=name,
                start_date=datetime.date(*start),
                end_date=datetime.date(*end),
                is_current=current,
            )

    def _other_school(self):
        return self._build_school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)

    # --- Creation ----------------------------------------------------------

    def test_valid_year_is_created_and_multiple_years_coexist(self):
        self._make("2026-27")
        self._make("2027-28", start=(2027, 4, 1), end=(2028, 3, 31))
        with tenant_context(self.school):
            from .models import AcademicYear

            self.assertEqual(AcademicYear.objects.count(), 2)

    # --- Tenant isolation and name uniqueness -------------------------------

    def test_same_name_is_valid_in_a_different_tenant(self):
        other = self._other_school()
        try:
            self._make("2026-27")
            self._make("2026-27", school=other)
            with tenant_context(other):
                from .models import AcademicYear

                self.assertEqual(AcademicYear.objects.filter(name="2026-27").count(), 1)
        finally:
            connection.set_schema_to_public()

    def test_duplicate_name_in_same_tenant_is_rejected_by_database(self):
        self._make("2026-27")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("2026-27")

    # --- Date validation -----------------------------------------------------

    def test_start_before_end_is_valid(self):
        from .models import AcademicYear

        year = AcademicYear(name="2026-27", start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2027, 3, 31))
        year.clean()

    def test_equal_dates_are_rejected(self):
        from .models import AcademicYear

        year = AcademicYear(name="2026-27", start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2026, 4, 1))
        with self.assertRaises(DjangoValidationError) as ctx:
            year.clean()
        self.assertIn("end_date", ctx.exception.message_dict)

    def test_end_before_start_is_rejected(self):
        from .models import AcademicYear

        year = AcademicYear(name="2026-27", start_date=datetime.date(2027, 3, 31), end_date=datetime.date(2026, 4, 1))
        with self.assertRaises(DjangoValidationError):
            year.clean()

    # --- Name format (invalid values are rejected, never repaired) -----------

    def test_bare_year_and_inconsistent_names_are_rejected(self):
        from .models import AcademicYear

        for bad in ["2026", "2026-2027", "2026-28", "26-27", "abc", "", "2026-27 "]:
            with self.subTest(name=repr(bad)):
                year = AcademicYear(
                    name=bad, start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2027, 3, 31)
                )
                with self.assertRaises(DjangoValidationError):
                    year.clean()

    def test_name_is_not_silently_normalized(self):
        from .models import AcademicYear

        year = AcademicYear(name="2026-27", start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2027, 3, 31))
        year.clean()
        self.assertEqual(year.name, "2026-27")

    # --- Current-year constraint ---------------------------------------------

    def test_one_current_year_is_allowed(self):
        self._make("2026-27", current=True)
        with tenant_context(self.school):
            from .models import AcademicYear

            self.assertTrue(AcademicYear.objects.get(name="2026-27").is_current)

    def test_second_current_year_in_same_tenant_is_rejected_by_database(self):
        self._make("2026-27", current=True)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self._make("2027-28", start=(2027, 4, 1), end=(2028, 3, 31), current=True)

    def test_current_years_in_different_tenants_are_allowed(self):
        other = self._other_school()
        try:
            self._make("2026-27", current=True)
            self._make("2026-27", current=True, school=other)
        finally:
            connection.set_schema_to_public()

    def test_non_current_years_are_unlimited(self):
        for i, (start, end) in enumerate([((2025, 4, 1), (2026, 3, 31)), ((2026, 4, 1), (2027, 3, 31)), ((2027, 4, 1), (2028, 3, 31))]):
            name = f"{start[0]}-{str(start[0] + 1)[2:]}"
            self._make(name, start=start, end=end, current=False)
        with tenant_context(self.school):
            from .models import AcademicYear

            self.assertEqual(AcademicYear.objects.filter(is_current=False).count(), 3)

    # --- Existing academic-year data is untouched ----------------------------

    def test_existing_academic_year_columns_are_unchanged_and_no_fk_added(self):
        """
        Phase 1.3B Stage A: every one of the 13 legacy free-text academic_year
        columns (across all 6 affected apps, not just the 5 originally sampled
        here) remains present, unchanged, and varchar - this half of the test
        is preserved exactly as before, only extended to full coverage.

        As of Stage A, each legacy column now has a corresponding nullable
        `<column>_ref` FK column pointing at academics.AcademicYear - this is
        a deliberate, approved addition (Phase 1.3B Revision 7, Stage A), so
        the second half of this test asserts the FK's presence/shape instead
        of its absence, which is what this test originally asserted before
        Stage A existed.
        """
        legacy_fields = [
            ("attendance_attendancesession", "academic_year"),
            ("course_content_subjectenrollment", "academic_year"),
            ("examinations_examination", "academic_year"),
            ("examinations_examresult", "academic_year"),
            ("examinations_examschedule", "academic_year"),
            ("examinations_gradeboundary", "academic_year"),
            ("fees_feestructure", "academic_year"),
            ("fees_studentfee", "academic_year"),
            ("students_promotionrecord", "source_academic_year"),
            ("students_promotionrecord", "target_academic_year"),
            ("students_studentlevel", "academic_year"),
            ("timetable_period", "academic_year"),
            ("timetable_timetableentry", "academic_year"),
        ]
        self.assertEqual(len(legacy_fields), 13, "expected exactly 13 legacy academic-year fields")

        with tenant_context(self.school):
            with connection.cursor() as cursor:
                table_descs = {}
                for table, column in legacy_fields:
                    if table not in table_descs:
                        table_descs[table] = {
                            c.name: c for c in connection.introspection.get_table_description(cursor, table)
                        }
                    desc = table_descs[table]

                    # --- Legacy column: unchanged (preserved from the original test) ---
                    self.assertIn(column, desc, f"{table}.{column} was removed")
                    self.assertEqual(desc[column].type_code, CHAR_VARYING_OID, f"{table}.{column} type changed")
                    self.assertNotEqual(
                        desc[column].type_code, UUID_OID,
                        f"{table}.{column} was converted to a FK - the legacy string column must stay a string",
                    )

                    # --- New FK column: present, nullable, uuid-typed (Stage A addition) ---
                    fk_column = f"{column}_ref_id"
                    self.assertIn(fk_column, desc, f"{table}.{fk_column} (the new AcademicYear FK) is missing")
                    self.assertEqual(
                        desc[fk_column].type_code, UUID_OID,
                        f"{table}.{fk_column} should be uuid-typed (matches academics_academicyear.id)",
                    )
                    self.assertTrue(desc[fk_column].null_ok, f"{table}.{fk_column} must be nullable in Stage A")

                # Confirm the FK columns actually target academics_academicyear, not merely same-shaped.
                cursor.execute(
                    """
                    SELECT tc.table_name, kcu.column_name, ccu.table_name AS foreign_table
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage ccu
                        ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
                    WHERE tc.constraint_type = 'FOREIGN KEY' AND kcu.column_name LIKE '%_ref_id'
                    """
                )
                fk_targets = {(row[0], row[1]): row[2] for row in cursor.fetchall()}
                for table, column in legacy_fields:
                    fk_column = f"{column}_ref_id"
                    self.assertEqual(
                        fk_targets.get((table, fk_column)), "academics_academicyear",
                        f"{table}.{fk_column} does not reference academics_academicyear",
                    )


class AcademicYearApiTests(AcademicsFixtureMixin, TransactionTestCase):
    """Phase 1.2B: tenant-scoped AcademicYear API, RBAC, and atomic current-year switching."""

    OTHER_SCHEMA = "acad_p12b_other"
    OTHER_DOMAIN = "academics-p12b-other.localhost"
    TENANT_SCHEMAS = ["acad_p04_school", "acad_p04_other", "acad_p12b_other"]
    BASE = "/api/academics/academic-years/"

    def setUp(self):
        super().setUp()
        self.addCleanup(self._cleanup_other)
        self.other = self._build_school(self.OTHER_SCHEMA, self.OTHER_DOMAIN)
        self.manager = self._build_user(
            "acad_ay_manager",
            codenames=["view_academic_level", "add_academic_level", "change_academic_level", "delete_academic_level"],
        )
        self.reader = self._build_user("acad_ay_reader", codenames=["view_academic_level"])
        from .models import AcademicYear

        with tenant_context(self.school):
            self.a_2627 = AcademicYear.objects.create(
                name="2026-27", start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2027, 3, 31)
            )
            self.a_2728 = AcademicYear.objects.create(
                name="2027-28", start_date=datetime.date(2027, 4, 1), end_date=datetime.date(2028, 3, 31)
            )
        with tenant_context(self.other):
            self.b_2627 = AcademicYear.objects.create(
                name="2026-27", start_date=datetime.date(2026, 4, 1), end_date=datetime.date(2027, 3, 31), is_current=True
            )

    def _cleanup_other(self):
        connection.set_schema_to_public()
        for org in Organization.objects.filter(schema_name=self.OTHER_SCHEMA):
            org.delete(force_drop=True)

    def _body(self, **over):
        data = {"name": "2028-29", "start_date": "2028-04-01", "end_date": "2029-03-31"}
        data.update(over)
        return data

    # --- Authentication ------------------------------------------------------

    def test_unauthenticated_requests_are_rejected(self):
        anon = APIClient()
        self.assertIn(anon.get(self.BASE, HTTP_HOST=self.DOMAIN).status_code, (401, 403))
        self.assertIn(
            anon.post(self.BASE, self._body(), HTTP_HOST=self.DOMAIN, format="json").status_code, (401, 403)
        )
        self.assertIn(anon.get(f"{self.BASE}{self.a_2627.id}/", HTTP_HOST=self.DOMAIN).status_code, (401, 403))
        self.assertIn(
            anon.patch(f"{self.BASE}{self.a_2627.id}/", {"end_date": "2027-03-30"}, HTTP_HOST=self.DOMAIN, format="json").status_code,
            (401, 403),
        )
        self.assertIn(anon.post(f"{self.BASE}{self.a_2728.id}/set-current/", HTTP_HOST=self.DOMAIN).status_code, (401, 403))

    # --- Tenant isolation ----------------------------------------------------

    def test_list_returns_only_the_current_tenants_years(self):
        resp = self._client_as(self.manager, self.DOMAIN).get(self.BASE, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200, resp.data)
        ids = {r["id"] for r in resp.data["results"]}
        self.assertEqual(ids, {str(self.a_2627.id), str(self.a_2728.id)})
        self.assertNotIn(str(self.b_2627.id), ids)

    def test_cross_tenant_retrieve_update_set_current_and_delete_return_not_found(self):
        client = self._client_as(self.manager, self.DOMAIN)
        foreign = f"{self.BASE}{self.b_2627.id}/"
        self.assertEqual(client.get(foreign, HTTP_HOST=self.DOMAIN).status_code, 404)
        self.assertEqual(
            client.patch(foreign, {"end_date": "2027-03-30"}, HTTP_HOST=self.DOMAIN, format="json").status_code, 404
        )
        self.assertEqual(client.post(f"{foreign}set-current/", HTTP_HOST=self.DOMAIN).status_code, 404)
        self.assertEqual(client.delete(foreign, HTTP_HOST=self.DOMAIN).status_code, 404)
        with tenant_context(self.other):
            from .models import AcademicYear

            self.assertTrue(AcademicYear.objects.get(pk=self.b_2627.pk).is_current)

    def test_duplicate_name_in_same_tenant_is_a_validation_error(self):
        resp = self._client_as(self.manager, self.DOMAIN).post(
            self.BASE, self._body(name="2027-28", start_date="2027-04-01", end_date="2028-03-31"),
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("name", resp.data)

    def test_same_name_is_allowed_in_another_tenant(self):
        other_client = self._client_as(self.manager, self.DOMAIN)
        from .models import AcademicYear

        with tenant_context(self.school):
            self.assertEqual(AcademicYear.objects.filter(name="2026-27").count(), 1)
        self.assertIsNotNone(self.b_2627)  # other tenant already holds 2026-27
        self.assertEqual(other_client.get(self.BASE, HTTP_HOST=self.DOMAIN).status_code, 200)

    # --- Create / validation --------------------------------------------------

    def test_valid_creation_succeeds_and_is_not_current(self):
        resp = self._client_as(self.manager, self.DOMAIN).post(
            self.BASE, self._body(), HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertFalse(resp.data["is_current"])
        with tenant_context(self.school):
            from .models import AcademicYear

            self.assertTrue(AcademicYear.objects.filter(name="2028-29").exists())

    def test_client_cannot_create_a_current_year_directly(self):
        resp = self._client_as(self.manager, self.DOMAIN).post(
            self.BASE, self._body(is_current=True), HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 201)
        self.assertFalse(resp.data["is_current"])

    def test_invalid_name_formats_are_rejected(self):
        client = self._client_as(self.manager, self.DOMAIN)
        for bad in ["2026", "2081", "2026-2027", "2026-28", "abc"]:
            with self.subTest(name=bad):
                resp = client.post(self.BASE, self._body(name=bad), HTTP_HOST=self.DOMAIN, format="json")
                self.assertEqual(resp.status_code, 400)
                self.assertIn("name", resp.data)

    def test_invalid_dates_are_rejected(self):
        client = self._client_as(self.manager, self.DOMAIN)
        equal = client.post(
            self.BASE, self._body(start_date="2028-04-01", end_date="2028-04-01"), HTTP_HOST=self.DOMAIN, format="json"
        )
        reversed_ = client.post(
            self.BASE, self._body(start_date="2029-03-31", end_date="2028-04-01"), HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(equal.status_code, 400)
        self.assertEqual(reversed_.status_code, 400)
        self.assertIn("end_date", equal.data)

    # --- Update -------------------------------------------------------------------

    def test_authorized_update_succeeds(self):
        resp = self._client_as(self.manager, self.DOMAIN).patch(
            f"{self.BASE}{self.a_2728.id}/", {"end_date": "2028-03-30"}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["end_date"], "2028-03-30")

    def test_invalid_update_is_rejected(self):
        resp = self._client_as(self.manager, self.DOMAIN).patch(
            f"{self.BASE}{self.a_2728.id}/", {"start_date": "2028-04-01"}, HTTP_HOST=self.DOMAIN, format="json"
        )
        self.assertEqual(resp.status_code, 400)

    # --- Current year ----------------------------------------------------------------

    def test_set_current_switches_and_leaves_exactly_one_current(self):
        client = self._client_as(self.manager, self.DOMAIN)
        self.assertEqual(client.post(f"{self.BASE}{self.a_2627.id}/set-current/", HTTP_HOST=self.DOMAIN).status_code, 200)
        self.assertEqual(client.post(f"{self.BASE}{self.a_2728.id}/set-current/", HTTP_HOST=self.DOMAIN).status_code, 200)
        with tenant_context(self.school):
            from .models import AcademicYear

            current = list(AcademicYear.objects.filter(is_current=True).values_list("name", flat=True))
        self.assertEqual(current, ["2027-28"])

    def test_set_current_is_idempotent(self):
        client = self._client_as(self.manager, self.DOMAIN)
        client.post(f"{self.BASE}{self.a_2627.id}/set-current/", HTTP_HOST=self.DOMAIN)
        again = client.post(f"{self.BASE}{self.a_2627.id}/set-current/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(again.status_code, 200)
        with tenant_context(self.school):
            from .models import AcademicYear

            self.assertEqual(AcademicYear.objects.filter(is_current=True).count(), 1)

    def test_current_year_cannot_be_deleted(self):
        client = self._client_as(self.manager, self.DOMAIN)
        client.post(f"{self.BASE}{self.a_2627.id}/set-current/", HTTP_HOST=self.DOMAIN)
        resp = client.delete(f"{self.BASE}{self.a_2627.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 400)
        with tenant_context(self.school):
            from .models import AcademicYear

            self.assertTrue(AcademicYear.objects.filter(pk=self.a_2627.pk).exists())

    def test_database_invariant_rejects_a_second_current_year_even_without_the_api(self):
        from .models import AcademicYear

        with tenant_context(self.school):
            AcademicYear.objects.filter(pk=self.a_2627.pk).update(is_current=True)
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    AcademicYear.objects.filter(pk=self.a_2728.pk).update(is_current=True)

    def test_race_on_set_current_is_reported_as_conflict_not_500(self):
        from unittest import mock

        client = self._client_as(self.manager, self.DOMAIN)
        with mock.patch("academics.views.transaction.atomic", side_effect=IntegrityError("simulated race")):
            resp = client.post(f"{self.BASE}{self.a_2728.id}/set-current/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 409)
        self.assertNotIn("simulated", str(resp.data))

    # --- RBAC ---------------------------------------------------------------------

    def test_reader_can_view_but_cannot_mutate(self):
        client = self._client_as(self.reader, self.DOMAIN)
        self.assertEqual(client.get(self.BASE, HTTP_HOST=self.DOMAIN).status_code, 200)
        self.assertEqual(client.post(self.BASE, self._body(), HTTP_HOST=self.DOMAIN, format="json").status_code, 403)
        self.assertEqual(
            client.patch(f"{self.BASE}{self.a_2728.id}/", {"end_date": "2028-03-30"}, HTTP_HOST=self.DOMAIN, format="json").status_code,
            403,
        )
        self.assertEqual(client.post(f"{self.BASE}{self.a_2728.id}/set-current/", HTTP_HOST=self.DOMAIN).status_code, 403)
        self.assertEqual(client.delete(f"{self.BASE}{self.a_2728.id}/", HTTP_HOST=self.DOMAIN).status_code, 403)

    def test_privileged_user_is_still_tenant_isolated(self):
        resp = self._client_as(self.manager, self.DOMAIN).get(f"{self.BASE}{self.b_2627.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

    # --- Existing data safety ----------------------------------------------------

    def test_legacy_academic_year_strings_are_not_touched_by_the_api(self):
        from academics.models import AcademicLevel
        from profiles.models import Profile
        from students.models import Student, StudentLevel

        with tenant_context(self.school):
            level = AcademicLevel.objects.first()
            student = Student.objects.create(
                profile=Profile.objects.create(first_name="Keep", last_name="Legacy"),
                enrollment_id="P12B-LEGACY", status="active",
            )
            StudentLevel.objects.create(student=student, level=level, academic_year="2026", is_current=True)
        client = self._client_as(self.manager, self.DOMAIN)
        client.post(self.BASE, self._body(), HTTP_HOST=self.DOMAIN, format="json")
        client.post(f"{self.BASE}{self.a_2627.id}/set-current/", HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            values = list(StudentLevel.objects.filter(student=student).values_list("academic_year", flat=True))
        self.assertEqual(values, ["2026"])


class CalendarEventAPITests(TransactionTestCase, AcademicsFixtureMixin):
    """
    Automated test suite for Academic Calendar & Holiday Management API:
    - CRUD operations
    - RBAC permissions (view_calendar_events, manage_calendar_events)
    - Multi-tenant isolation
    - Date range validation (single day, multi-day, invalid bounds)
    - Timed event validation
    - Publish/Cancel status transitions
    - Upcoming and holidays custom endpoints
    - Server-side filtering
    - Audit logging
    """

    SCHEMA_A = "cal_school_a"
    DOMAIN_A = "calendar-a.localhost"
    SCHEMA_B = "cal_school_b"
    DOMAIN_B = "calendar-b.localhost"

    BASE = "/api/calendar-events/"

    def setUp(self):
        connection.set_schema_to_public()
        self.school_a = self._build_school(self.SCHEMA_A, self.DOMAIN_A)
        self.school_b = self._build_school(self.SCHEMA_B, self.DOMAIN_B)

        self.school = self.school_a
        self.owner = self._build_user("cal_owner", owner=True)
        self.manager = self._build_user("cal_manager", codenames=["view_calendar_events", "manage_calendar_events"])
        self.viewer = self._build_user("cal_viewer", codenames=["view_calendar_events"])
        self.no_perm = self._build_user("cal_noperm", codenames=[])

        self.school = self.school_b
        self.b_manager = self._build_user("cal_b_mgr", codenames=["view_calendar_events", "manage_calendar_events"])
        self.school = self.school_a

    def tearDown(self):
        connection.set_schema_to_public()
        self.school_a.delete(force_drop=True)
        self.school_b.delete(force_drop=True)

    def _create_event(self, school, **kwargs):
        from .models import CalendarEvent
        with tenant_context(school):
            defaults = {
                "title": "Test Event",
                "description": "Event description",
                "event_type": "ACADEMIC",
                "start_date": datetime.date(2026, 10, 20),
                "end_date": datetime.date(2026, 10, 20),
                "is_all_day": True,
                "status": "PUBLISHED",
            }
            defaults.update(kwargs)
            return CalendarEvent.objects.create(**defaults)

    def test_list_events_authenticated_with_permission(self):
        self._create_event(self.school_a, title="School Assembly")
        client = self._client_as(self.viewer, self.DOMAIN_A)
        resp = client.get(self.BASE, HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["title"], "School Assembly")

    def test_unauthenticated_gets_401(self):
        client = APIClient()
        resp = client.get(self.BASE, HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp.status_code, 401)

    def test_user_without_permission_gets_403(self):
        client = self._client_as(self.no_perm, self.DOMAIN_A)
        resp = client.get(self.BASE, HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp.status_code, 403)

    def test_tenant_a_cannot_see_tenant_b_events(self):
        self._create_event(self.school_a, title="School A Sports Day")
        self._create_event(self.school_b, title="School B Gala")

        client_a = self._client_as(self.viewer, self.DOMAIN_A)
        resp_a = client_a.get(self.BASE, HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_a.data["count"], 1)
        self.assertEqual(resp_a.data["results"][0]["title"], "School A Sports Day")

    def test_tenant_a_cannot_retrieve_tenant_b_event_by_id(self):
        event_b = self._create_event(self.school_b, title="School B Private Meeting")
        client_a = self._client_as(self.manager, self.DOMAIN_A)
        resp = client_a.get(f"{self.BASE}{event_b.id}/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp.status_code, 404)

    def test_create_event_requires_manage_permission(self):
        payload = {
            "title": "Unauthorized Create",
            "event_type": "ACADEMIC",
            "start_date": "2026-11-01",
            "end_date": "2026-11-01",
            "is_all_day": True,
        }
        # Viewer only has view_calendar_events -> gets 403 on POST
        client_viewer = self._client_as(self.viewer, self.DOMAIN_A)
        resp_viewer = client_viewer.post(self.BASE, payload, HTTP_HOST=self.DOMAIN_A, format="json")
        self.assertEqual(resp_viewer.status_code, 403)

        # Manager has manage_calendar_events -> succeeds 201
        client_mgr = self._client_as(self.manager, self.DOMAIN_A)
        resp_mgr = client_mgr.post(self.BASE, payload, HTTP_HOST=self.DOMAIN_A, format="json")
        self.assertEqual(resp_mgr.status_code, 201)
        self.assertEqual(resp_mgr.data["title"], "Unauthorized Create")

    def test_create_multi_day_holiday(self):
        payload = {
            "title": "Winter Vacation",
            "description": "School closed for winter break",
            "event_type": "HOLIDAY",
            "start_date": "2026-12-20",
            "end_date": "2026-12-31",
            "is_all_day": True,
        }
        client = self._client_as(self.manager, self.DOMAIN_A)
        resp = client.post(self.BASE, payload, HTTP_HOST=self.DOMAIN_A, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["is_holiday"], True)
        self.assertEqual(resp.data["start_date"], "2026-12-20")
        self.assertEqual(resp.data["end_date"], "2026-12-31")

    def test_create_event_invalid_date_range_fails_400(self):
        payload = {
            "title": "Invalid Dates",
            "event_type": "ACADEMIC",
            "start_date": "2026-11-15",
            "end_date": "2026-11-10",  # precedes start date
            "is_all_day": True,
        }
        client = self._client_as(self.manager, self.DOMAIN_A)
        resp = client.post(self.BASE, payload, HTTP_HOST=self.DOMAIN_A, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("end_date", resp.data)

    def test_create_timed_event_invalid_time_range_fails_400(self):
        payload = {
            "title": "PTA Meeting",
            "event_type": "MEETING",
            "start_date": "2026-11-10",
            "end_date": "2026-11-10",
            "is_all_day": False,
            "start_time": "14:00:00",
            "end_time": "12:00:00",  # precedes start_time on same date
        }
        client = self._client_as(self.manager, self.DOMAIN_A)
        resp = client.post(self.BASE, payload, HTTP_HOST=self.DOMAIN_A, format="json")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("end_time", resp.data)

    def test_update_and_delete_event(self):
        event = self._create_event(self.school_a, title="Initial Title")
        client = self._client_as(self.manager, self.DOMAIN_A)

        # Update
        patch_resp = client.patch(
            f"{self.BASE}{event.id}/",
            {"title": "Updated Title"},
            HTTP_HOST=self.DOMAIN_A,
            format="json",
        )
        self.assertEqual(patch_resp.status_code, 200)
        self.assertEqual(patch_resp.data["title"], "Updated Title")

        # Delete
        del_resp = client.delete(f"{self.BASE}{event.id}/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(del_resp.status_code, 204)

        # Verify gone
        get_resp = client.get(f"{self.BASE}{event.id}/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(get_resp.status_code, 404)

    def test_publish_and_cancel_actions(self):
        event = self._create_event(self.school_a, title="Draft Event", status="DRAFT")
        client = self._client_as(self.manager, self.DOMAIN_A)

        # Publish
        pub_resp = client.post(f"{self.BASE}{event.id}/publish/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(pub_resp.status_code, 200)
        self.assertEqual(pub_resp.data["status"], "PUBLISHED")

        # Cancel
        cancel_resp = client.post(f"{self.BASE}{event.id}/cancel/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(cancel_resp.status_code, 200)
        self.assertEqual(cancel_resp.data["status"], "CANCELLED")

    def test_draft_events_hidden_from_ordinary_viewers(self):
        self._create_event(self.school_a, title="Secret Staff Draft", status="DRAFT")
        self._create_event(self.school_a, title="Official Holiday", status="PUBLISHED")

        # Viewer only sees PUBLISHED
        client_viewer = self._client_as(self.viewer, self.DOMAIN_A)
        resp_viewer = client_viewer.get(self.BASE, HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp_viewer.status_code, 200)
        self.assertEqual(resp_viewer.data["count"], 1)
        self.assertEqual(resp_viewer.data["results"][0]["title"], "Official Holiday")

        # Manager sees both DRAFT and PUBLISHED
        client_mgr = self._client_as(self.manager, self.DOMAIN_A)
        resp_mgr = client_mgr.get(self.BASE, HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp_mgr.status_code, 200)
        self.assertEqual(resp_mgr.data["count"], 2)

    def test_filters_by_event_type_and_date_range(self):
        self._create_event(self.school_a, title="Event 1", event_type="HOLIDAY", is_holiday=True, start_date=datetime.date(2026, 10, 5), end_date=datetime.date(2026, 10, 5))
        self._create_event(self.school_a, title="Event 2", event_type="EXAMINATION", start_date=datetime.date(2026, 10, 15), end_date=datetime.date(2026, 10, 20))
        self._create_event(self.school_a, title="Event 3", event_type="ACTIVITY", start_date=datetime.date(2026, 11, 1), end_date=datetime.date(2026, 11, 2))

        client = self._client_as(self.viewer, self.DOMAIN_A)

        # Filter by event_type
        resp_type = client.get(f"{self.BASE}?event_type=HOLIDAY", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp_type.status_code, 200)
        self.assertEqual(resp_type.data["count"], 1)
        self.assertEqual(resp_type.data["results"][0]["title"], "Event 1")

        # Filter by interval overlap (date_from & date_to for October)
        resp_oct = client.get(f"{self.BASE}?date_from=2026-10-01&date_to=2026-10-31", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp_oct.status_code, 200)
        self.assertEqual(resp_oct.data["count"], 2)

    def test_filter_date_range_validation_error(self):
        client = self._client_as(self.viewer, self.DOMAIN_A)
        resp = client.get(f"{self.BASE}?date_from=2026-10-30&date_to=2026-10-01", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("date_from", resp.data)

    def test_upcoming_and_holidays_endpoints(self):
        past_date = datetime.date.today() - datetime.timedelta(days=10)
        future_date = datetime.date.today() + datetime.timedelta(days=5)

        self._create_event(self.school_a, title="Past Event", start_date=past_date, end_date=past_date)
        self._create_event(self.school_a, title="Future Holiday", event_type="HOLIDAY", is_holiday=True, start_date=future_date, end_date=future_date)

        client = self._client_as(self.viewer, self.DOMAIN_A)

        # Upcoming endpoint
        resp_up = client.get(f"{self.BASE}upcoming/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp_up.status_code, 200)
        self.assertEqual(len(resp_up.data), 1)
        self.assertEqual(resp_up.data[0]["title"], "Future Holiday")

        # Holidays endpoint
        resp_hol = client.get(f"{self.BASE}holidays/", HTTP_HOST=self.DOMAIN_A)
        self.assertEqual(resp_hol.status_code, 200)
        self.assertEqual(resp_hol.data["count"], 1)
        self.assertEqual(resp_hol.data["results"][0]["title"], "Future Holiday")

    def test_filter_by_exact_date_single_and_multi_day(self):
        # 1. Single day holiday
        self._create_event(
            self.school_a,
            title="Gandhi Jayanti",
            event_type="HOLIDAY",
            is_holiday=True,
            start_date=datetime.date(2026, 10, 2),
            end_date=datetime.date(2026, 10, 2),
            status="PUBLISHED",
        )
        # 2. Multi-day festival break
        self._create_event(
            self.school_a,
            title="Dashain Vacation",
            event_type="HOLIDAY",
            is_holiday=True,
            start_date=datetime.date(2026, 10, 15),
            end_date=datetime.date(2026, 10, 22),
            status="PUBLISHED",
        )
        # 3. School closure
        self._create_event(
            self.school_a,
            title="Facility Maintenance Closure",
            event_type="CLOSURE",
            is_holiday=True,
            start_date=datetime.date(2026, 11, 5),
            end_date=datetime.date(2026, 11, 5),
            status="PUBLISHED",
        )
        # 4. Draft holiday on Oct 2
        self._create_event(
            self.school_a,
            title="Draft Holiday",
            event_type="HOLIDAY",
            is_holiday=True,
            start_date=datetime.date(2026, 10, 2),
            end_date=datetime.date(2026, 10, 2),
            status="DRAFT",
        )
        # 5. Non-holiday academic event on Oct 2
        self._create_event(
            self.school_a,
            title="Science Workshop",
            event_type="ACADEMIC",
            is_holiday=False,
            start_date=datetime.date(2026, 10, 2),
            end_date=datetime.date(2026, 10, 2),
            status="PUBLISHED",
        )

        client = self._client_as(self.viewer, self.DOMAIN_A)

        # Query single day holiday with published status & is_holiday=true
        resp_oct2 = client.get(
            f"{self.BASE}?date=2026-10-02&is_holiday=true&status=PUBLISHED",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp_oct2.status_code, 200)
        self.assertEqual(resp_oct2.data["count"], 1)
        self.assertEqual(resp_oct2.data["results"][0]["title"], "Gandhi Jayanti")

        # Query inside multi-day range (Oct 18)
        resp_oct18 = client.get(
            f"{self.BASE}?date=2026-10-18&is_holiday=true&status=PUBLISHED",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp_oct18.status_code, 200)
        self.assertEqual(resp_oct18.data["count"], 1)
        self.assertEqual(resp_oct18.data["results"][0]["title"], "Dashain Vacation")

        # Query boundary: start_date (Oct 15)
        resp_start = client.get(
            f"{self.BASE}?date=2026-10-15&is_holiday=true&status=PUBLISHED",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp_start.status_code, 200)
        self.assertEqual(resp_start.data["count"], 1)
        self.assertEqual(resp_start.data["results"][0]["title"], "Dashain Vacation")

        # Query boundary: end_date (Oct 22)
        resp_end = client.get(
            f"{self.BASE}?date=2026-10-22&is_holiday=true&status=PUBLISHED",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp_end.status_code, 200)
        self.assertEqual(resp_end.data["count"], 1)
        self.assertEqual(resp_end.data["results"][0]["title"], "Dashain Vacation")

        # Query date outside holiday (Oct 23)
        resp_none = client.get(
            f"{self.BASE}?date=2026-10-23&is_holiday=true&status=PUBLISHED",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp_none.status_code, 200)
        self.assertEqual(resp_none.data["count"], 0)

        # Query school closure (Nov 5)
        resp_closure = client.get(
            f"{self.BASE}?date=2026-11-05&is_holiday=true&status=PUBLISHED",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp_closure.status_code, 200)
        self.assertEqual(resp_closure.data["count"], 1)
        self.assertEqual(resp_closure.data["results"][0]["title"], "Facility Maintenance Closure")
        self.assertEqual(resp_closure.data["results"][0]["event_type"], "CLOSURE")

        # Invalid date format returns 400 Bad Request
        resp_invalid = client.get(
            f"{self.BASE}?date=invalid-date",
            HTTP_HOST=self.DOMAIN_A,
        )
        self.assertEqual(resp_invalid.status_code, 400)
        self.assertIn("date", resp_invalid.data)


