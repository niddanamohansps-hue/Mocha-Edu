import datetime
import io
import uuid as uuid_module
from decimal import Decimal

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, AcademicYear, Program, Section, Subject
from accounts.models import User
from certificates.cbse import check_student_fee_dues, date_to_words
from certificates.models import Certificate
from certificates.pdf import render_cbse_tc_pdf
from certificates.services import _student_snapshot
from fees.models import FeeHead, FeeStructure, StudentFee
from organizations.models import Domain, Organization
from profiles.models import InstitutionProfile, Profile
from roles.models import Permission, Role, UserRole
from students.bulk_import import check, save
from students.exports import export_cbse_loc_csv, export_udise_plus_csv
from students.models import Student, StudentLevel


class ComplianceFixtureMixin:
    def _build_school(self, schema_name=None, domain=None, name="Compliance Test School"):
        suffix = uuid_module.uuid4().hex[:8]
        schema_name = schema_name or f"comp_{suffix}"
        domain = domain or f"comp-{suffix}.localhost"
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school


class CbseHelpersSimpleTest(SimpleTestCase):
    def test_date_to_words(self):
        self.assertEqual(date_to_words("2010-08-15"), "Fifteenth August Two Thousand Ten")
        self.assertEqual(date_to_words("1999-12-31"), "Thirty-First December Nineteen Ninety Nine")
        self.assertEqual(date_to_words(datetime.date(2005, 1, 1)), "First January Two Thousand Five")
        self.assertEqual(date_to_words("2000-05-20"), "Twentieth May Two Thousand")


class CompliancePackIntegrationTest(ComplianceFixtureMixin, TransactionTestCase):
    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            self.ay, _ = AcademicYear.objects.get_or_create(
                name="2026-27",
                defaults={
                    "start_date": datetime.date(2026, 4, 1),
                    "end_date": datetime.date(2027, 3, 31),
                    "is_current": True,
                },
            )
            if not self.ay.is_current:
                self.ay.is_current = True
                self.ay.save()

            self.inst, _ = InstitutionProfile.objects.get_or_create(
                organization_id=self.school.id,
                defaults={
                    "affiliation_number": "CBSE-2130888",
                    "school_code": "09876",
                    "udise_code": "09123456789",
                    "board_name": "CBSE",
                },
            )
            if not self.inst.affiliation_number:
                self.inst.affiliation_number = "CBSE-2130888"
                self.inst.school_code = "09876"
                self.inst.udise_code = "09123456789"
                self.inst.board_name = "CBSE"
                self.inst.save()

            program, _ = Program.objects.get_or_create(name="CBSE Secondary", code="SEC")
            self.level_10, _ = AcademicLevel.objects.get_or_create(program=program, name="Grade 10", defaults={"order": 10})
            self.section_10a, _ = Section.objects.get_or_create(level=self.level_10, name="A", defaults={"capacity": 40})

            Subject.objects.get_or_create(level=self.level_10, code="ENG10", defaults={"name": "English"})
            Subject.objects.get_or_create(level=self.level_10, code="MTH10", defaults={"name": "Mathematics"})
            Subject.objects.get_or_create(level=self.level_10, code="SCI10", defaults={"name": "Science"})

            self.profile = Profile.objects.create(
                first_name="Aarav",
                last_name="Sharma",
                gender="male",
                date_of_birth=datetime.date(2010, 8, 15),
            )

            self.enrollment_id = f"ADM-{uuid_module.uuid4().hex[:6].upper()}"
            self.student = Student.objects.create(
                profile=self.profile,
                enrollment_id=self.enrollment_id,
                status="transferred",
                admission_date=datetime.date(2020, 4, 1),
                apaar_id="123456789012",
                pen="20349812345",
                caste_category="OBC",
                is_rte=True,
                aadhaar_last_4="9012",
                mother_name="Sunita Sharma",
                father_name="Rajesh Sharma",
            )

            self.enrollment = StudentLevel.objects.create(
                student=self.student,
                level=self.level_10,
                section=self.section_10a,
                academic_year="2026-27",
                is_current=True,
            )

    def test_compliance_fields_persisted(self):
        with tenant_context(self.school):
            s = Student.objects.get(pk=self.student.pk)
            self.assertEqual(s.apaar_id, "123456789012")
            self.assertEqual(s.pen, "20349812345")
            self.assertEqual(s.caste_category, "OBC")
            self.assertTrue(s.is_rte)
            self.assertEqual(s.aadhaar_last_4, "9012")
            self.assertEqual(s.get_mother_name(), "Sunita Sharma")
            self.assertEqual(s.get_father_name(), "Rajesh Sharma")

    def test_udise_plus_csv_export(self):
        with tenant_context(self.school):
            response = export_udise_plus_csv()
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/csv", response["Content-Type"])
            content = response.content.decode("utf-8-sig")

            self.assertIn("PEN,APAAR_ID,STUDENT_NAME", content)
            self.assertIn("20349812345", content)
            self.assertIn("Aarav Sharma", content)
            self.assertIn("Sunita Sharma", content)
            self.assertIn("Rajesh Sharma", content)
            self.assertIn("OBC", content)
            self.assertIn("Yes", content)

    def test_cbse_loc_csv_export(self):
        with tenant_context(self.school):
            response = export_cbse_loc_csv()
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/csv", response["Content-Type"])
            content = response.content.decode("utf-8-sig")

            self.assertIn("REG_NO_OR_PEN,APAAR_ID,CANDIDATE_NAME", content)
            self.assertIn(self.enrollment_id, content)
            self.assertIn("20349812345", content)
            self.assertIn("123456789012", content)
            self.assertIn("Aarav Sharma", content)
            self.assertIn("Grade 10", content)

    def test_cbse_20_point_tc_snapshot_and_pdf(self):
        with tenant_context(self.school):
            extra = {
                "leaving_date": "2026-09-30",
                "reason": "Parents Transfer",
                "conduct": "Excellent",
            }
            snap, year = _student_snapshot(self.student, Certificate.Type.TRANSFER, extra)

            self.assertEqual(snap["holder_name"], "Aarav Sharma")
            self.assertEqual(snap["mother_name"], "Sunita Sharma")
            self.assertEqual(snap["father_name"], "Rajesh Sharma")
            self.assertEqual(snap["dob_figures"], "15-08-2010")
            self.assertEqual(snap["dob_words"], "Fifteenth August Two Thousand Ten")
            self.assertEqual(snap["affiliation_number"], "CBSE-2130888")
            self.assertEqual(snap["school_code"], "09876")
            self.assertEqual(snap["pen"], "20349812345")
            self.assertEqual(snap["apaar_id"], "123456789012")
            self.assertEqual(snap["caste_category"], "OBC")
            self.assertTrue(snap["is_rte"])
            self.assertEqual(snap["fee_concession"], "RTE 25% Quota")
            self.assertIn("English", snap["subjects_studied"])

            cert = Certificate(
                certificate_type=Certificate.Type.TRANSFER,
                certificate_number="TC-2026-00001",
                verification_id="v" * 32,
                issue_date=datetime.date(2026, 10, 1),
                snapshot=snap,
                status=Certificate.Status.ISSUED,
                issued_by_user_id=uuid_module.uuid4(),
            )
            pdf_bytes = render_cbse_tc_pdf(
                cert,
                "http://test.localhost/verify/certificate/test",
                signatory_name="Dr. S. K. Gupta",
                signatory_title="Principal",
            )
            self.assertTrue(pdf_bytes.startswith(b"%PDF"))
            self.assertGreater(len(pdf_bytes), 2000)

    def test_bulk_import_compliance_columns(self):
        with tenant_context(self.school):
            raw_rows = [
                {
                    "_row": 1,
                    "first_name": "Rohan",
                    "last_name": "Verma",
                    "gender": "Male",
                    "date_of_birth": "12-04-2011",
                    "class": "Grade 10",
                    "section": "A",
                    "father_name": "Ramesh Verma",
                    "father_phone": "9876543210",
                    "pen": "20349819999",
                    "apaar_id": "987654321098",
                    "caste_category": "SC",
                    "is_rte": "Yes",
                    "aadhaar_last_4": "4321",
                }
            ]
            result = check(raw_rows)
            self.assertEqual(len(result.errors), 0, f"Errors: {result.errors}")
            self.assertEqual(len(result.rows), 1)

            clean_row = result.rows[0]
            self.assertEqual(clean_row["pen"], "20349819999")
            self.assertEqual(clean_row["apaar_id"], "987654321098")
            self.assertEqual(clean_row["caste_category"], "SC")
            self.assertTrue(clean_row["is_rte"])
            self.assertEqual(clean_row["aadhaar_last_4"], "4321")

            created_count = save(result.rows)
            self.assertEqual(created_count, 1)

            saved = Student.objects.get(profile__first_name="Rohan", profile__last_name="Verma")
            self.assertEqual(saved.pen, "20349819999")
            self.assertEqual(saved.apaar_id, "987654321098")
            self.assertEqual(saved.caste_category, "SC")
            self.assertTrue(saved.is_rte)
            self.assertEqual(saved.aadhaar_last_4, "4321")
            self.assertEqual(saved.father_name, "Ramesh Verma")


class ComplianceFieldRulesTest(SimpleTestCase):
    """The admission form and API apply the same identifier rules as the bulk import."""

    def setUp(self):
        from students.serializers import StudentEnrollmentSerializer

        self.serializer = StudentEnrollmentSerializer()

    def test_identifier_formats_are_checked(self):
        from rest_framework import serializers

        self.assertEqual(self.serializer.validate_apaar_id(" 123456789012 "), "123456789012")
        self.assertEqual(self.serializer.validate_apaar_id(""), "")
        for bad in ("12345", "12345678901a", "1234567890123"):
            with self.assertRaises(serializers.ValidationError):
                self.serializer.validate_apaar_id(bad)
        self.assertEqual(self.serializer.validate_pen("2034981234A"), "2034981234A")
        with self.assertRaises(serializers.ValidationError):
            self.serializer.validate_pen("123")
        self.assertEqual(self.serializer.validate_aadhaar_last_4("9012"), "9012")
        for bad in ("901", "90a2", "90123"):
            with self.assertRaises(serializers.ValidationError):
                self.serializer.validate_aadhaar_last_4(bad)

    def test_nothing_is_guessed_when_not_recorded(self):
        fields = self.serializer.fields
        self.assertEqual(fields["caste_category"].default, "")
        self.assertEqual(fields["mother_tongue"].default, "")
        self.assertIn("cwsn_status", fields)
        self.assertIn("bpl_status", fields)
        self.assertEqual(Student._meta.get_field("caste_category").default, "")
        self.assertEqual(Student._meta.get_field("mother_tongue").default, "")
