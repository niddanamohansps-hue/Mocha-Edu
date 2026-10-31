"""
Stage C: Assessment components (Theory + Internal/Practical), separate pass enforcement,
co-scholastic letter grades, term weightage consolidation, and CBSE-ready report card payload.
"""
from decimal import Decimal

from django.test import TransactionTestCase
from django_tenants.utils import tenant_context

from .models import (
    CoScholasticActivity,
    CoScholasticGrade,
    ExamComponentMark,
    ExamMark,
    ExamResult,
    ExamScheduleComponent,
    TermWeightage,
)
from .services import (
    calculate_examination_results_bulk,
    calculate_subject_result,
    get_student_co_scholastic_summary,
    get_student_term_weightage_summary,
)
from .tests import ExamFixtureMixin


class StageCBase(ExamFixtureMixin, TransactionTestCase):
    def setUp(self):
        super().setUp()
        self.schedule = self._create_schedule()
        self.owner = self._client_as(self.owner_user)
        self.teacher = self._client_as(self.instructor_user)

    def mark_of(self, student, schedule=None):
        with tenant_context(self.school):
            return ExamMark.objects.get(exam_schedule=schedule or self.schedule, student=student)

    def result_of(self, student, examination=None):
        with tenant_context(self.school):
            return ExamResult.objects.get(examination=examination or self.examination, student=student)


class ExamScheduleComponentTests(StageCBase):
    def test_create_components_via_api(self):
        url = f"/api/examinations/schedules/{self.schedule.id}/components/"
        theory_resp = self.owner.post(
            url,
            {
                "name": "Theory",
                "code": "TH",
                "max_marks": 80,
                "pass_marks": 26,
                "is_theory": True,
                "requires_separate_pass": True,
                "order": 1,
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(theory_resp.status_code, 201)
        self.assertEqual(theory_resp.data["name"], "Theory")
        self.assertTrue(theory_resp.data["requires_separate_pass"])

        internal_resp = self.owner.post(
            url,
            {
                "name": "Internal Assessment",
                "code": "IA",
                "max_marks": 20,
                "pass_marks": 7,
                "is_theory": False,
                "requires_separate_pass": False,
                "order": 2,
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(internal_resp.status_code, 201)

        # GET components list on schedule
        get_resp = self.owner.get(url, HTTP_HOST=self.DOMAIN)
        self.assertEqual(get_resp.status_code, 200)
        self.assertEqual(len(get_resp.data), 2)

    def test_component_validation_rejects_invalid_marks(self):
        url = f"/api/examinations/schedules/{self.schedule.id}/components/"
        # pass_marks > max_marks
        resp = self.owner.post(
            url,
            {
                "name": "Invalid",
                "code": "INV",
                "max_marks": 50,
                "pass_marks": 60,
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("pass_marks", resp.data)


class ComponentMarksEntryTests(StageCBase):
    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.c_theory = ExamScheduleComponent.objects.create(
                exam_schedule=self.schedule,
                name="Theory",
                code="TH",
                max_marks=Decimal("80.00"),
                pass_marks=Decimal("26.00"),
                is_theory=True,
                requires_separate_pass=True,
                order=1,
            )
            self.c_internal = ExamScheduleComponent.objects.create(
                exam_schedule=self.schedule,
                name="Internal Assessment",
                code="IA",
                max_marks=Decimal("20.00"),
                pass_marks=Decimal("7.00"),
                is_theory=False,
                requires_separate_pass=False,
                order=2,
            )

    def test_bulk_component_marks_entry_auto_aggregates_total(self):
        url = f"/api/examinations/schedules/{self.schedule.id}/component-marks/"
        body = {
            "records": [
                {
                    "student": str(self.student.id),
                    "attendance": "present",
                    "components": [
                        {"component": str(self.c_theory.id), "marks_obtained": "65.00"},
                        {"component": str(self.c_internal.id), "marks_obtained": "18.00"},
                    ],
                },
                {
                    "student": str(self.student2.id),
                    "attendance": "present",
                    "components": [
                        {"component": str(self.c_theory.id), "marks_obtained": "20.00"},
                        {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                    ],
                },
            ]
        }
        resp = self.teacher.post(url, body, HTTP_HOST=self.DOMAIN, format="json")
        self.assertEqual(resp.status_code, 200)

        with tenant_context(self.school):
            m1 = self.mark_of(self.student)
            self.assertEqual(m1.marks_obtained, Decimal("83.00"))
            c_marks = list(m1.component_marks.order_by("component__order"))
            self.assertEqual(len(c_marks), 2)
            self.assertEqual(c_marks[0].marks_obtained, Decimal("65.00"))
            self.assertEqual(c_marks[1].marks_obtained, Decimal("18.00"))

            m2 = self.mark_of(self.student2)
            self.assertEqual(m2.marks_obtained, Decimal("35.00"))

    def test_separate_pass_rule_enforcement(self):
        """
        Student 2 scored 20/80 in Theory (needs 26) and 15/20 in Internal.
        Total = 35/100 (which is >= 33% overall passing boundary).
        Because Theory requires_separate_pass=True and 20 < 26, subject is_pass must be False.
        """
        # Save marks
        url = f"/api/examinations/schedules/{self.schedule.id}/component-marks/"
        self.teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student2.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "20.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    }
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )

        with tenant_context(self.school):
            m2 = self.mark_of(self.student2)
            subject_res = calculate_subject_result(m2, self.schedule)
            self.assertEqual(subject_res["marks_obtained"], Decimal("35.00"))
            self.assertFalse(subject_res["is_pass"], "Student must fail subject due to failing separate theory pass mark.")
            self.assertEqual(len(subject_res["components"]), 2)
            th_comp = next(c for c in subject_res["components"] if c["code"] == "TH")
            self.assertFalse(th_comp["is_pass"])

    def test_grace_marks_cannot_override_failing_separate_theory_pass(self):
        """
        Student scores 20/80 in Theory (needs 26) and 10/20 in Internal.
        Raw total = 30/100 (below 33 pass mark).
        With 5 grace marks, total becomes 35/100 (above 33 pass mark).
        However, because Theory requires separate pass and 20 < 26, is_pass MUST remain False.
        """
        url = f"/api/examinations/schedules/{self.schedule.id}/component-marks/"
        self.teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student2.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "20.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "10.00"},
                        ],
                    }
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )

        with tenant_context(self.school):
            m2 = self.mark_of(self.student2)
            m2.grace_marks = Decimal("5.00")
            m2.save()

            # Single subject calculation
            res = calculate_subject_result(m2, self.schedule)
            self.assertEqual(res["marks_obtained"], 35.0)
            self.assertFalse(res["is_pass"], "Grace marks must not override separate theory pass requirement.")

            # Bulk examination calculation
            bulk_res = calculate_examination_results_bulk(self.examination, [self.student2])
            self.assertFalse(
                bulk_res[self.student2.id]["is_pass"], "Overall exam must remain failed due to component failure."
            )

    def test_unassigned_teacher_cannot_enter_component_marks(self):
        url = f"/api/examinations/schedules/{self.schedule.id}/component-marks/"
        other_teacher = self._client_as(self.other_instructor_user)
        resp = other_teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "60.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    }
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_locked_schedule_blocks_component_marks_without_reason(self):
        url = f"/api/examinations/schedules/{self.schedule.id}/component-marks/"
        # Initial entry
        self.teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "60.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    }
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )

        # Lock schedule
        self.owner.post(
            f"/api/examinations/schedules/{self.schedule.id}/lock/",
            {"is_locked": True},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )

        # Teacher blocked
        t_resp = self.teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "65.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    }
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(t_resp.status_code, 423)

        # Manager without reason blocked
        m_resp = self.owner.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "65.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    }
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(m_resp.status_code, 400)
        self.assertIn("reason", m_resp.data)

        # Manager with reason succeeds
        ok_resp = self.owner.post(
            url,
            {
                "reason": "Recounting theory marks",
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "65.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    }
                ],
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(ok_resp.status_code, 200)

    def test_published_examination_blocks_component_definition_and_marks(self):
        # Enter valid marks first
        url = f"/api/examinations/schedules/{self.schedule.id}/component-marks/"
        self.teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "60.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    },
                    {
                        "student": str(self.student2.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "50.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    },
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )

        # Publish
        pub_resp = self.owner.post(
            f"/api/examinations/examinations/{self.examination.id}/publish/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(pub_resp.status_code, 200)

        # Adding a component is blocked
        comp_resp = self.owner.post(
            f"/api/examinations/schedules/{self.schedule.id}/components/",
            {"name": "Oral", "code": "OR", "max_marks": 10, "pass_marks": 3},
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(comp_resp.status_code, 400)

        # Modifying marks directly on published exam is blocked
        marks_resp = self.teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "70.00"},
                        ],
                    }
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(marks_resp.status_code, 423)

    def test_end_to_end_report_card_payload(self):
        # Setup marks
        url = f"/api/examinations/schedules/{self.schedule.id}/component-marks/"
        self.teacher.post(
            url,
            {
                "records": [
                    {
                        "student": str(self.student.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "70.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "18.00"},
                        ],
                    },
                    {
                        "student": str(self.student2.id),
                        "attendance": "present",
                        "components": [
                            {"component": str(self.c_theory.id), "marks_obtained": "20.00"},
                            {"component": str(self.c_internal.id), "marks_obtained": "15.00"},
                        ],
                    },
                ]
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )

        # Setup co-scholastic
        with tenant_context(self.school):
            art = CoScholasticActivity.objects.create(name="Art Education", code="ART", order=1)
            CoScholasticGrade.objects.create(
                student=self.student,
                examination=self.examination,
                activity=art,
                grade="A",
                remarks="Outstanding",
            )
            # Setup term weightage
            TermWeightage.objects.create(
                academic_year=self.examination.academic_year,
                level=self.level,
                examination=self.examination,
                weightage_percentage=Decimal("100.00"),
            )

        # Publish examination
        self.owner.post(
            f"/api/examinations/examinations/{self.examination.id}/publish/",
            HTTP_HOST=self.DOMAIN,
        )

        # Fetch report card via API
        rc_resp = self.owner.get(
            f"/api/examinations/students/{self.student.id}/report-card/",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(rc_resp.status_code, 200)
        data = rc_resp.data

        # Verify components in subject breakdown
        self.assertIn("examinations", data)
        self.assertEqual(len(data["examinations"]), 1)
        sub_breakdown = data["examinations"][0]["subject_breakdown"]
        self.assertEqual(len(sub_breakdown), 1)
        self.assertIn("components", sub_breakdown[0])
        self.assertEqual(len(sub_breakdown[0]["components"]), 2)

        # Verify co-scholastic block
        self.assertIn("co_scholastic", data)
        self.assertEqual(len(data["co_scholastic"]), 1)
        self.assertEqual(data["co_scholastic"][0]["activity_code"], "ART")
        self.assertEqual(data["co_scholastic"][0]["grade"], "A")

        # Verify term weightage block
        self.assertIn("term_weightage", data)
        self.assertIsNotNone(data["term_weightage"])
        self.assertTrue(data["term_weightage"]["is_configured"])
        self.assertEqual(data["term_weightage"]["total_weightage_configured"], 100.0)
        # Theory 70 + Internal 18 = 88 out of 100, and the only term carries all the weightage.
        self.assertEqual(data["term_weightage"]["overall"]["percentage"], 88.0)


class TermWeightageTests(StageCBase):
    def test_term_weightage_summary_calculation(self):
        with tenant_context(self.school):
            # Term weightage: 100% for this examination on Level
            tw = TermWeightage.objects.create(
                academic_year=self.examination.academic_year,
                level=self.level,
                examination=self.examination,
                weightage_percentage=Decimal("100.00"),
            )
            # Create a published result
            ExamResult.objects.create(
                examination=self.examination,
                student=self.student,
                academic_year=self.examination.academic_year,
                total_marks_obtained=Decimal("85.00"),
                total_max_marks=Decimal("100.00"),
                percentage=Decimal("85.00"),
                overall_grade="A",
                is_pass=True,
                subject_breakdown=[
                    {
                        "subject": str(self.schedule.subject_id),
                        "subject_name": "Math",
                        "percentage": 85.0,
                        "is_pass": True,
                    }
                ],
            )

            summary = get_student_term_weightage_summary(
                self.student.id,
                academic_year=self.examination.academic_year,
                level_id=self.level.id,
            )
            self.assertTrue(summary["is_configured"])
            self.assertEqual(summary["total_weightage_configured"], 100.0)
            self.assertEqual(summary["overall"]["percentage"], 85.0)
            self.assertEqual(len(summary["examinations"]), 1)
            self.assertEqual(summary["subjects"][0]["consolidated_percentage"], 85.0)


class CoScholasticTests(StageCBase):
    def test_co_scholastic_crud_and_bulk_entry(self):
        with tenant_context(self.school):
            art = CoScholasticActivity.objects.create(name="Art Education", code="ART", order=1)
            pe = CoScholasticActivity.objects.create(name="Physical Education", code="PE", order=2)

        # Bulk entry
        url = "/api/examinations/co-scholastic/grades/bulk/"
        resp = self.teacher.post(
            url,
            {
                "examination": str(self.examination.id),
                "records": [
                    {"student": str(self.student.id), "activity": str(art.id), "grade": "A", "remarks": "Very creative"},
                    {"student": str(self.student.id), "activity": str(pe.id), "grade": "B", "remarks": "Active"},
                ],
            },
            HTTP_HOST=self.DOMAIN,
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["saved"], 2)

        with tenant_context(self.school):
            summary = get_student_co_scholastic_summary(self.student.id, academic_year=self.examination.academic_year)
            self.assertEqual(len(summary), 2)
            art_summary = next(s for s in summary if s["activity_code"] == "ART")
            self.assertEqual(art_summary["grade"], "A")
            self.assertEqual(art_summary["remarks"], "Very creative")

