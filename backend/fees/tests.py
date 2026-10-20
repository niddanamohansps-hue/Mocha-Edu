import datetime
import uuid as uuid_module
from decimal import Decimal

from django.db import IntegrityError, connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django_tenants.utils import tenant_context
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section
from accounts.models import User
from core.models import AuditLog
from families.models import Parent, StudentParentRelation
from organizations.models import Domain, Organization
from profiles.models import Profile
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember
from students.models import Student, StudentLevel

from .gateways import (
    EsewaGatewayAdapter,
    MockGatewayAdapter,
    PaymentConfigurationError,
    get_gateway_adapter,
    get_gateway_credentials,
)
from .models import (
    FeeHead,
    FeeStructure,
    OnlinePaymentOrder,
    Payment,
    PaymentAllocation,
    StudentFee,
    TenantPaymentGatewayConfig,
)
from .services import (
    annotate_with_allocation_total,
    assign_student_fee,
    cancel_student_fee,
    get_amount_paid,
    get_outstanding_balance,
    get_total_allocated,
    initiate_online_payment_order,
    reconcile_online_payment_order,
    record_payment,
    reverse_payment,
    settle_online_payment_order,
    update_student_fee,
    user_can_view_student_finances,
)
from .signals import DEFAULT_FEE_HEADS
from .tasks import reconcile_pending_online_payments



class FeesFixtureMixin:
    """Mirrors attendance/timetable/examinations/parent_portal tests.py exactly."""

    SCHEMA_NAME = "fees_test_school"
    DOMAIN = "feestest.localhost"

    def _build_school(self, schema_name=None, domain=None, name="Fees Test School"):
        schema_name = schema_name or self.SCHEMA_NAME
        domain = domain or self.DOMAIN
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema_name, name=name)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _build_user(self, username, role_slug):
        user = User.objects.create_user(
            username=username, email=f"{username}@feestest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            role, _ = Role.objects.get_or_create(
                slug=role_slug, defaults={"name": role_slug.title(), "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=role)
        return user

    def _give_role_only(self, user, codenames):
        with tenant_context(self.school):
            unique_suffix = uuid_module.uuid4().hex[:8]
            role = Role.objects.create(
                name=f"custom-{unique_suffix}", slug=f"custom-{unique_suffix}", is_system_role=False
            )
            role.permissions.set(Permission.objects.filter(codename__in=codenames))
            UserRole.objects.filter(user=user).delete()
            UserRole.objects.create(user=user, role=role)
        return role

    def _client_as(self, user, password="Pass1234!"):
        client = APIClient()
        resp = client.post(
            "/api/auth/login/", {"username": user.username, "password": password}, HTTP_HOST=self.DOMAIN
        )
        assert resp.status_code == 200, resp.data
        return client

    def _make_parent(self, username, first_name, last_name):
        user = User.objects.create_user(
            username=username, email=f"{username}@feestest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            profile = Profile.objects.create(user_id=user.id, first_name=first_name, last_name=last_name)
            parent = Parent.objects.create(profile=profile, occupation="Engineer")
            parent_role, _ = Role.objects.get_or_create(
                slug="parent", defaults={"name": "Parent", "is_system_role": True}
            )
            UserRole.objects.create(user=user, role=parent_role)
        return user, parent

    def _make_student(self, enrollment_id, first_name, last_name, section, user=None):
        with tenant_context(self.school):
            profile = Profile.objects.create(
                user_id=user.id if user else None, first_name=first_name, last_name=last_name
            )
            student = Student.objects.create(profile=profile, enrollment_id=enrollment_id, status="active")
            StudentLevel.objects.create(
                student=student, level=section.level, section=section, academic_year="2026", is_current=True
            )
            if user:
                student_role, _ = Role.objects.get_or_create(
                    slug="student", defaults={"name": "Student", "is_system_role": True}
                )
                UserRole.objects.create(user=user, role=student_role)
        return student

    def setUp(self):
        self.school = self._build_school()

        with tenant_context(self.school):
            program = Program.objects.create(name="High School", code="HSFE")
            level = AcademicLevel.objects.create(program=program, name="Grade 10", order=1)
            self.section_a = Section.objects.create(level=level, name="A", capacity=40)
            self.fee_head = FeeHead.objects.create(name="Test Tuition FE")

        self.student1_user = User.objects.create_user(
            username="fe_student1", email="fe_student1@feestest.com", password="Pass1234!"
        )
        self.student1 = self._make_student(
            "ENR-FE-1", "Sam", "Pupil", self.section_a, user=self.student1_user
        )
        self.student2 = self._make_student("ENR-FE-2", "Otto", "Other", self.section_a)

        self.parent1_user, self.parent1 = self._make_parent("fe_parent1", "Pat", "Guardian")
        self.parent2_user, self.parent2 = self._make_parent("fe_parent2", "Pam", "Guardian")
        with tenant_context(self.school):
            StudentParentRelation.objects.create(
                student=self.student1, parent=self.parent1, relation_type="mother", is_primary_contact=True
            )
            StudentParentRelation.objects.create(
                student=self.student2, parent=self.parent2, relation_type="mother", is_primary_contact=True
            )

        # Built directly (not via _build_user) so the Profile can be linked
        # BEFORE the UserRole is created - profiles.signals.create_profile_for_role
        # fires on UserRole post_save and auto-creates a Profile for any role
        # NOT in its ["student", "instructor"] skip list (see the exact same
        # hazard documented in families.serializers.ParentPortalActivationSerializer).
        # "staff" is not skip-listed, so building via _build_user first and
        # creating a real Profile afterward would leave two Profile rows for
        # the same user_id.
        self.finance_user = User.objects.create_user(
            username="fe_finance", email="fe_finance@feestest.com", password="Pass1234!"
        )
        with tenant_context(self.school):
            finance_profile = Profile.objects.create(
                user_id=self.finance_user.id, first_name="Fin", last_name="Ance"
            )
            self.finance_staff_member = StaffMember.objects.create(
                profile=finance_profile, employee_id="EMP-FE-1", designation="Accountant"
            )
            staff_role, _ = Role.objects.get_or_create(
                slug="staff", defaults={"name": "Staff", "is_system_role": True}
            )
            UserRole.objects.create(user=self.finance_user, role=staff_role)

        self.owner_user = self._build_user("fe_owner", "owner")
        self.random_staff_user = self._build_user("fe_random", "staff")

        self.school2 = self._build_school(
            schema_name="fees_test_school2", domain="feestest2.localhost", name="Fees Test School 2"
        )
        with tenant_context(self.school2):
            program2 = Program.objects.create(name="Other School", code="OSFE")
            level2 = AcademicLevel.objects.create(program=program2, name="Grade 1", order=1)
            section2 = Section.objects.create(level=level2, name="A", capacity=10)
            profile2 = Profile.objects.create(first_name="Cross", last_name="Tenant")
            self.other_tenant_student = Student.objects.create(
                profile=profile2, enrollment_id="ENR-OT-1", status="active"
            )
            StudentLevel.objects.create(
                student=self.other_tenant_student, level=level2, section=section2,
                academic_year="2026", is_current=True,
            )

    def tearDown(self):
        connection.set_schema_to_public()
        self.school.delete(force_drop=True)
        self.school2.delete(force_drop=True)

    def _assign_fee(self, student, amount_due=Decimal("1000"), **overrides):
        with tenant_context(self.school):
            defaults = dict(
                student=student, fee_head=self.fee_head, academic_year="2026", amount_due=amount_due,
                due_date=datetime.date(2026, 6, 1),
            )
            defaults.update(overrides)
            return assign_student_fee(**defaults)


class FeeModelTests(FeesFixtureMixin, TransactionTestCase):
    def test_fee_head_unique_name(self):
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    FeeHead.objects.create(name="Test Tuition FE")

    def test_student_fee_default_status_active(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
            self.assertEqual(sf.status, "active")

    def test_student_fee_snapshots_level_and_section(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
            self.assertEqual(sf.level_name, "Grade 10")
            self.assertEqual(sf.section_name, "A")

    def test_payment_allocation_rejects_zero_amount(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
            payment = Payment.objects.create(
                student=self.student1, amount=Decimal("100"), receipt_number="RCPT-ZEROTEST"
            )
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    PaymentAllocation.objects.create(payment=payment, student_fee=sf, amount=Decimal("0"))

    def test_payment_allocation_unique_together_payment_student_fee(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
            payment = Payment.objects.create(
                student=self.student1, amount=Decimal("100"), receipt_number="RCPT-UNIQTEST"
            )
            PaymentAllocation.objects.create(payment=payment, student_fee=sf, amount=Decimal("50"))
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    PaymentAllocation.objects.create(payment=payment, student_fee=sf, amount=Decimal("50"))

    def test_payment_receipt_number_unique(self):
        with tenant_context(self.school):
            Payment.objects.create(student=self.student1, amount=Decimal("100"), receipt_number="RCPT-DUP")
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Payment.objects.create(student=self.student1, amount=Decimal("50"), receipt_number="RCPT-DUP")


class DefaultFeeHeadSeedingTests(FeesFixtureMixin, TransactionTestCase):
    def test_default_fee_heads_seeded_per_tenant(self):
        with tenant_context(self.school):
            names = set(FeeHead.objects.values_list("name", flat=True))
            for expected in DEFAULT_FEE_HEADS:
                self.assertIn(expected, names)

    def test_default_fee_heads_remain_editable(self):
        with tenant_context(self.school):
            tuition = FeeHead.objects.get(name="Tuition")
            tuition.description = "Updated"
            tuition.save()
            tuition.refresh_from_db()
            self.assertEqual(tuition.description, "Updated")

    def test_fee_heads_not_seeded_in_public_schema(self):
        """fees is a TENANT_APP, so its tables are never created in the
        public schema at all - querying there must find no such table,
        not merely zero rows in one."""
        connection.set_schema_to_public()
        self.assertNotIn("fees_feehead", connection.introspection.table_names())


class FeeStructureAndHeadPermissionTests(FeesFixtureMixin, TransactionTestCase):
    def test_view_fees_can_list_heads(self):
        self._give_role_only(self.finance_user, ["view_fees"])
        client = self._client_as(self.finance_user)
        resp = client.get("/api/fees/heads/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_without_permission_cannot_list_heads(self):
        client = self._client_as(self.random_staff_user)
        resp = client.get("/api/fees/heads/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_manage_fee_structures_required_to_create_head(self):
        client = self._client_as(self.random_staff_user)
        resp = client.post("/api/fees/heads/", {"name": "New Head"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_manage_fee_structures_can_create_head(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        resp = client.post("/api/fees/heads/", {"name": "Sports Fee"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_fee_head_has_no_delete_endpoint(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        with tenant_context(self.school):
            head_id = self.fee_head.id
        resp = client.delete(f"/api/fees/heads/{head_id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 405)

    def test_manage_fee_structures_can_create_structure(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        with tenant_context(self.school):
            head_id = str(self.fee_head.id)
        resp = client.post(
            "/api/fees/structures/",
            {"fee_head": head_id, "academic_year": "2026", "amount": "1200.00", "frequency": "annual"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_fee_structure_has_no_delete_endpoint(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        with tenant_context(self.school):
            fs = FeeStructure.objects.create(
                fee_head=self.fee_head, academic_year="2026", amount=Decimal("500")
            )
        resp = client.delete(f"/api/fees/structures/{fs.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 405)


class AssignStudentFeeTests(FeesFixtureMixin, TransactionTestCase):
    def test_assign_via_fee_head_and_amount(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        with tenant_context(self.school):
            head_id = str(self.fee_head.id)
        resp = client.post(
            f"/api/fees/students/{self.student1.id}/assign/",
            {"fee_head": head_id, "academic_year": "2026", "amount_due": "1000.00"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["level_name"], "Grade 10")

    def test_assign_via_fee_structure_inherits_amount(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        with tenant_context(self.school):
            fs = FeeStructure.objects.create(
                fee_head=self.fee_head, academic_year="2026", amount=Decimal("750"),
                due_date=datetime.date(2026, 5, 1),
            )
        resp = client.post(
            f"/api/fees/students/{self.student1.id}/assign/",
            {"fee_structure": str(fs.id), "academic_year": "2026"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(Decimal(resp.data["amount_due"]), Decimal("750.00"))

    def test_assign_requires_manage_fee_structures(self):
        client = self._client_as(self.random_staff_user)
        resp = client.post(
            f"/api/fees/students/{self.student1.id}/assign/",
            {"fee_head": str(self.fee_head.id), "academic_year": "2026", "amount_due": "1000"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 403)

    def test_discount_cannot_exceed_amount_due(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        resp = client.post(
            f"/api/fees/students/{self.student1.id}/assign/",
            {
                "fee_head": str(self.fee_head.id), "academic_year": "2026", "amount_due": "100",
                "discount_amount": "200", "discount_reason": "too much",
            },
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 400)

    def test_assign_logs_audit_action(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        client.post(
            f"/api/fees/students/{self.student1.id}/assign/",
            {"fee_head": str(self.fee_head.id), "academic_year": "2026", "amount_due": "1000"},
            HTTP_HOST=self.DOMAIN,
        )
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="student_fee_assigned").exists())

    def test_assign_with_discount_logs_discount_applied(self):
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        client.post(
            f"/api/fees/students/{self.student1.id}/assign/",
            {
                "fee_head": str(self.fee_head.id), "academic_year": "2026", "amount_due": "1000",
                "discount_amount": "100", "discount_reason": "sibling",
            },
            HTTP_HOST=self.DOMAIN,
        )
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="discount_applied").exists())


class StudentFeeUpdateTests(FeesFixtureMixin, TransactionTestCase):
    def test_can_edit_while_unallocated(self):
        sf = self._assign_fee(self.student1)
        with tenant_context(self.school):
            self.assertTrue(update_student_fee(sf, amount_due=Decimal("900"))[0].amount_due == Decimal("900"))

    def test_cannot_edit_once_allocated(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        with tenant_context(self.school):
            staff_member = self.finance_staff_member
            record_payment(
                student=self.student1, amount=Decimal("200"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("200")}],
                recorded_by=staff_member,
            )
            from rest_framework.exceptions import ValidationError as DRFValidationError

            with self.assertRaises(DRFValidationError):
                update_student_fee(sf, amount_due=Decimal("50"))

    def test_update_endpoint_requires_permission(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
        client = self._client_as(self.random_staff_user)
        resp = client.patch(
            f"/api/fees/students/{self.student1.id}/fees/{sf.id}/",
            {"amount_due": "500"}, HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 403)

    def test_update_endpoint_blocked_after_allocation(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        with tenant_context(self.school):
            record_payment(
                student=self.student1, amount=Decimal("1000"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("1000")}],
                recorded_by=self.finance_staff_member,
            )
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        resp = client.patch(
            f"/api/fees/students/{self.student1.id}/fees/{sf.id}/",
            {"amount_due": "1"}, HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(resp.status_code, 400)


class CancelStudentFeeTests(FeesFixtureMixin, TransactionTestCase):
    def test_cancel_requires_reason(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        resp = client.post(
            f"/api/fees/students/{self.student1.id}/cancel/{sf.id}/", {}, HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 400)

    def test_cancel_is_soft_never_deletes_row(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        resp = client.post(
            f"/api/fees/students/{self.student1.id}/cancel/{sf.id}/",
            {"cancellation_reason": "Admission withdrawn"}, HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        with tenant_context(self.school):
            sf.refresh_from_db()
            self.assertEqual(sf.status, "cancelled")
            self.assertEqual(sf.cancellation_reason, "Admission withdrawn")
            self.assertTrue(StudentFee.objects.filter(id=sf.id).exists())

    def test_cancel_requires_permission(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
        client = self._client_as(self.random_staff_user)
        resp = client.post(
            f"/api/fees/students/{self.student1.id}/cancel/{sf.id}/",
            {"cancellation_reason": "test"}, HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 403)

    def test_cancel_blocked_if_allocations_exist(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        with tenant_context(self.school):
            record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
            with self.assertRaises(Exception):
                cancel_student_fee(sf, reason="too late")

    def test_cancel_already_cancelled_rejected(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
            cancel_student_fee(sf, reason="first cancel")
            with self.assertRaises(Exception):
                cancel_student_fee(sf, reason="second cancel")

    def test_cancel_logs_audit_action(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1)
        self._give_role_only(self.finance_user, ["manage_fee_structures"])
        client = self._client_as(self.finance_user)
        client.post(
            f"/api/fees/students/{self.student1.id}/cancel/{sf.id}/",
            {"cancellation_reason": "test reason"}, HTTP_HOST=self.DOMAIN,
        )
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="student_fee_cancelled").exists())


class RecordPaymentTests(FeesFixtureMixin, TransactionTestCase):
    def _record(self, client, student, allocations, amount, method="cash"):
        return client.post(
            "/api/fees/payments/",
            {
                "student": str(student.id), "amount": str(amount), "method": method,
                "allocations": [{"student_fee": str(a[0].id), "amount": str(a[1])} for a in allocations],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )

    def test_full_payment_zeroes_outstanding(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf, Decimal("1000"))], Decimal("1000"))
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.assertEqual(get_outstanding_balance(sf), Decimal("0"))

    def test_partial_payment_reduces_outstanding(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf, Decimal("400"))], Decimal("400"))
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.assertEqual(get_outstanding_balance(sf), Decimal("600"))

    def test_multiple_payments_accumulate(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        self._record(client, self.student1, [(sf, Decimal("300"))], Decimal("300"))
        self._record(client, self.student1, [(sf, Decimal("300"))], Decimal("300"))
        with tenant_context(self.school):
            self.assertEqual(get_amount_paid(sf), Decimal("600"))
            self.assertEqual(get_outstanding_balance(sf), Decimal("400"))

    def test_one_payment_multiple_fee_heads(self):
        sf1 = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            other_head = FeeHead.objects.create(name="Transport FE Test")
        sf2 = self._assign_fee(self.student1, amount_due=Decimal("300"), fee_head=other_head)
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf1, Decimal("500")), (sf2, Decimal("300"))], Decimal("800"))
        self.assertEqual(resp.status_code, 201, resp.data)
        with tenant_context(self.school):
            self.assertEqual(get_outstanding_balance(sf1), Decimal("0"))
            self.assertEqual(get_outstanding_balance(sf2), Decimal("0"))

    def test_overallocation_rejected(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("100"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf, Decimal("150"))], Decimal("150"))
        self.assertEqual(resp.status_code, 400)
        with tenant_context(self.school):
            self.assertEqual(get_outstanding_balance(sf), Decimal("100"))

    def test_allocation_sum_must_equal_payment_amount(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf, Decimal("100"))], Decimal("200"))
        self.assertEqual(resp.status_code, 400)

    def test_cannot_allocate_to_cancelled_fee(self):
        with tenant_context(self.school):
            sf = self._assign_fee(self.student1, amount_due=Decimal("100"))
            cancel_student_fee(sf, reason="withdrawn")
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf, Decimal("50"))], Decimal("50"))
        self.assertEqual(resp.status_code, 400)

    def test_cannot_allocate_to_another_students_fee(self):
        sf_other = self._assign_fee(self.student2, amount_due=Decimal("100"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf_other, Decimal("50"))], Decimal("50"))
        self.assertEqual(resp.status_code, 400)

    def test_record_payment_requires_permission(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("100"))
        client = self._client_as(self.random_staff_user)
        resp = self._record(client, self.student1, [(sf, Decimal("50"))], Decimal("50"))
        self.assertEqual(resp.status_code, 403)

    def test_receipt_number_generated(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("100"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = self._record(client, self.student1, [(sf, Decimal("100"))], Decimal("100"))
        self.assertTrue(resp.data["receipt_number"].startswith("RCPT-"))

    def test_record_payment_logs_audit_action(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("100"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        self._record(client, self.student1, [(sf, Decimal("100"))], Decimal("100"))
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="payment_recorded").exists())

    def test_service_level_over_allocation_race_guard(self):
        """Direct service-level test of the select_for_update race guard -
        two sequential attempts to allocate against the same (now-updated)
        outstanding balance must never both succeed past it."""
        sf = self._assign_fee(self.student1, amount_due=Decimal("100"))
        with tenant_context(self.school):
            record_payment(
                student=self.student1, amount=Decimal("100"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("100")}],
                recorded_by=self.finance_staff_member,
            )
            from rest_framework.exceptions import ValidationError as DRFValidationError

            with self.assertRaises(DRFValidationError):
                record_payment(
                    student=self.student1, amount=Decimal("1"), method="cash",
                    allocations=[{"student_fee_id": sf.id, "amount": Decimal("1")}],
                    recorded_by=self.finance_staff_member,
                )


class ReversePaymentTests(FeesFixtureMixin, TransactionTestCase):
    def test_reverse_creates_new_payment_never_edits_original(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
            original_created_at = payment.created_at
            reversal = reverse_payment(payment=payment, recorded_by=self.finance_staff_member, reason="error")

            payment.refresh_from_db()
            self.assertEqual(payment.status, "completed")
            self.assertEqual(payment.amount, Decimal("500"))
            self.assertEqual(payment.created_at, original_created_at)
            self.assertEqual(reversal.reverses_id, payment.id)
            self.assertEqual(reversal.status, "reversed")

    def test_reversal_restores_outstanding_balance(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
            self.assertEqual(get_outstanding_balance(sf), Decimal("0"))
            reverse_payment(payment=payment, recorded_by=self.finance_staff_member)
            self.assertEqual(get_outstanding_balance(sf), Decimal("500"))

    def test_double_reversal_rejected(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
            reverse_payment(payment=payment, recorded_by=self.finance_staff_member)
            from rest_framework.exceptions import ValidationError as DRFValidationError

            with self.assertRaises(DRFValidationError):
                reverse_payment(payment=payment, recorded_by=self.finance_staff_member)

    def test_reversing_a_reversal_rejected(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
            reversal = reverse_payment(payment=payment, recorded_by=self.finance_staff_member)
            from rest_framework.exceptions import ValidationError as DRFValidationError

            with self.assertRaises(DRFValidationError):
                reverse_payment(payment=reversal, recorded_by=self.finance_staff_member)

    def test_reverse_endpoint_requires_permission(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
        client = self._client_as(self.random_staff_user)
        resp = client.post(f"/api/fees/payments/{payment.id}/reverse/", {}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_reverse_logs_audit_action(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        client.post(f"/api/fees/payments/{payment.id}/reverse/", {}, HTTP_HOST=self.DOMAIN)
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="payment_reversed").exists())


class ImmutabilityTests(FeesFixtureMixin, TransactionTestCase):
    def test_no_patch_route_for_payments(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = client.patch(f"/api/fees/payments/{payment.id}/", {"amount": "1"}, HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

    def test_no_delete_route_for_payments(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            payment = record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = client.delete(f"/api/fees/payments/{payment.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 404)

    def test_payment_protect_prevents_student_deletion_with_history(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
            from django.db.models import ProtectedError

            with self.assertRaises(ProtectedError):
                self.student1.delete()


class StudentFeeAuthorizationTests(FeesFixtureMixin, TransactionTestCase):
    def test_student_can_view_own_fees_with_permission(self):
        self._assign_fee(self.student1)
        self._give_role_only(self.student1_user, ["view_own_fees"])
        client = self._client_as(self.student1_user)
        resp = client.get(f"/api/fees/students/{self.student1.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_student_denied_without_view_own_fees_permission(self):
        self._assign_fee(self.student1)
        client = self._client_as(self.student1_user)  # default student role, zero perms
        resp = client.get(f"/api/fees/students/{self.student1.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_view_another_students_fees(self):
        self._assign_fee(self.student2)
        self._give_role_only(self.student1_user, ["view_own_fees"])
        client = self._client_as(self.student1_user)
        resp = client.get(f"/api/fees/students/{self.student2.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_staff_with_view_fees_can_view_any_student(self):
        self._assign_fee(self.student1)
        self._give_role_only(self.finance_user, ["view_fees"])
        client = self._client_as(self.finance_user)
        resp = client.get(f"/api/fees/students/{self.student1.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_staff_without_view_fees_denied(self):
        self._assign_fee(self.student1)
        client = self._client_as(self.random_staff_user)
        resp = client.get(f"/api/fees/students/{self.student1.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_owner_bypasses_via_hasPermission_owner_rule(self):
        self._assign_fee(self.student1)
        client = self._client_as(self.owner_user)
        resp = client.get(f"/api/fees/students/{self.student1.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_service_function_directly(self):
        """
        HasPermission.has_permission expects a DRF Request (it reads
        request.query_params), not a bare Django WSGIRequest - use
        APIRequestFactory so this unit test exercises the same request
        shape the real views receive.
        """
        with tenant_context(self.school):
            from rest_framework.request import Request
            from rest_framework.test import APIRequestFactory

            self._give_role_only(self.student1_user, ["view_own_fees"])
            rf = APIRequestFactory()
            django_request = rf.get("/")
            django_request.user = self.student1_user
            django_request.tenant = self.school
            request = Request(django_request)
            request.user = self.student1_user
            self.assertTrue(user_can_view_student_finances(request, self.student1))


class ParentFeesAuthorizationTests(FeesFixtureMixin, TransactionTestCase):
    def test_parent_can_view_own_child_fees(self):
        self._assign_fee(self.student1)
        self._give_role_only(self.parent1_user, ["view_child_fees"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_parent_a_cannot_view_parent_b_child_fees(self):
        self._assign_fee(self.student2)
        self._give_role_only(self.parent1_user, ["view_child_fees"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student2.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_nonexistent_and_unrelated_student_indistinguishable(self):
        self._assign_fee(self.student2)
        self._give_role_only(self.parent1_user, ["view_child_fees"])
        client = self._client_as(self.parent1_user)
        nonexistent = client.get(
            f"/api/parent-portal/children/{uuid_module.uuid4()}/fees/", HTTP_HOST=self.DOMAIN
        )
        unrelated = client.get(
            f"/api/parent-portal/children/{self.student2.id}/fees/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(nonexistent.status_code, unrelated.status_code)
        self.assertEqual(nonexistent.data, unrelated.data)

    def test_removing_relation_revokes_fee_access(self):
        self._assign_fee(self.student1)
        self._give_role_only(self.parent1_user, ["view_child_fees"])
        client = self._client_as(self.parent1_user)
        ok = client.get(f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(ok.status_code, 200)

        with tenant_context(self.school):
            StudentParentRelation.objects.filter(student=self.student1, parent=self.parent1).delete()

        again = client.get(f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(again.status_code, 403)

    def test_non_parent_cannot_call_child_fees_endpoint(self):
        self._assign_fee(self.student1)
        client = self._client_as(self.random_staff_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_parent_without_view_child_fees_permission_denied(self):
        self._assign_fee(self.student1)
        client = self._client_as(self.parent1_user)  # default parent role, zero perms
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_owner_has_no_bypass_for_parent_fee_endpoint(self):
        self._assign_fee(self.student1)
        client = self._client_as(self.owner_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_parent_fee_summary_reflects_payment(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        with tenant_context(self.school):
            record_payment(
                student=self.student1, amount=Decimal("400"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("400")}],
                recorded_by=self.finance_staff_member,
            )
        self._give_role_only(self.parent1_user, ["view_child_fees"])
        client = self._client_as(self.parent1_user)
        resp = client.get(f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Decimal(str(resp.data["total_outstanding"])), Decimal("600"))


class TenantIsolationTests(FeesFixtureMixin, TransactionTestCase):
    def test_cross_tenant_student_denied_on_staff_endpoint(self):
        self._give_role_only(self.finance_user, ["view_fees"])
        client = self._client_as(self.finance_user)
        resp = client.get(
            f"/api/fees/students/{self.other_tenant_student.id}/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 404)

    def test_cross_tenant_student_denied_on_parent_endpoint(self):
        self._give_role_only(self.parent1_user, ["view_child_fees"])
        client = self._client_as(self.parent1_user)
        resp = client.get(
            f"/api/parent-portal/children/{self.other_tenant_student.id}/fees/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 403)

    def test_fee_heads_isolated_between_tenants(self):
        with tenant_context(self.school):
            FeeHead.objects.create(name="School1OnlyHead")
        with tenant_context(self.school2):
            self.assertFalse(FeeHead.objects.filter(name="School1OnlyHead").exists())


class OutstandingReportTests(FeesFixtureMixin, TransactionTestCase):
    def test_report_lists_students_with_outstanding_balance(self):
        self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)
        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)

    def test_report_excludes_fully_paid_fees(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("500"))
        with tenant_context(self.school):
            record_payment(
                student=self.student1, amount=Decimal("500"), method="cash",
                allocations=[{"student_fee_id": sf.id, "amount": Decimal("500")}],
                recorded_by=self.finance_staff_member,
            )
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)
        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["count"], 0)

    def test_report_requires_permission(self):
        client = self._client_as(self.random_staff_user)
        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)


class EndToEndScenarioTest(FeesFixtureMixin, TransactionTestCase):
    def test_full_lifecycle_finance_to_parent(self):
        self._give_role_only(
            self.finance_user, ["manage_fee_structures", "collect_payments", "view_fees"]
        )
        finance_client = self._client_as(self.finance_user)

        with tenant_context(self.school):
            head_id = str(self.fee_head.id)

        structure_resp = finance_client.post(
            "/api/fees/structures/",
            {"fee_head": head_id, "academic_year": "2026", "amount": "1200.00", "frequency": "annual"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(structure_resp.status_code, 201, structure_resp.data)
        structure_id = structure_resp.data["id"]

        assign_resp = finance_client.post(
            f"/api/fees/students/{self.student1.id}/assign/",
            {"fee_structure": structure_id, "academic_year": "2026"},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(assign_resp.status_code, 201, assign_resp.data)
        fee_id = assign_resp.data["id"]

        payment_resp = finance_client.post(
            "/api/fees/payments/",
            {
                "student": str(self.student1.id), "amount": "1200.00", "method": "cash",
                "allocations": [{"student_fee": fee_id, "amount": "1200.00"}],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )
        self.assertEqual(payment_resp.status_code, 201, payment_resp.data)
        receipt_number = payment_resp.data["receipt_number"]
        self.assertTrue(receipt_number)

        receipt_resp = finance_client.get(
            f"/api/fees/payments/{payment_resp.data['id']}/receipt/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(receipt_resp.status_code, 200)
        self.assertEqual(receipt_resp.data["receipt_number"], receipt_number)

        self._give_role_only(self.parent1_user, ["view_child_fees"])
        parent_client = self._client_as(self.parent1_user)
        parent_resp = parent_client.get(
            f"/api/parent-portal/children/{self.student1.id}/fees/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(parent_resp.status_code, 200)
        self.assertEqual(Decimal(str(parent_resp.data["total_outstanding"])), Decimal("0"))
        self.assertEqual(len(parent_resp.data["payments"]), 1)

        # Authorized linked parent can view child's receipt
        parent_receipt_resp = parent_client.get(
            f"/api/fees/payments/{payment_resp.data['id']}/receipt/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(parent_receipt_resp.status_code, 200)
        self.assertEqual(parent_receipt_resp.data["receipt_number"], receipt_number)

        # Unlinked parent is strictly forbidden from viewing another student's receipt
        self._give_role_only(self.parent2_user, ["view_child_fees"])
        parent2_client = self._client_as(self.parent2_user)
        parent2_receipt_resp = parent2_client.get(
            f"/api/fees/payments/{payment_resp.data['id']}/receipt/", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(parent2_receipt_resp.status_code, 403)



class AllocationAggregationTests(FeesFixtureMixin, TransactionTestCase):
    """
    Phase 9B: get_total_allocated() must return identical results whether
    called on a plain (unannotated) StudentFee or one annotated via
    annotate_with_allocation_total() - and must not issue one aggregate
    query per StudentFee when a queryset is annotated up front.
    """

    def _record(self, client, student, allocations, amount, method="cash"):
        return client.post(
            "/api/fees/payments/",
            {
                "student": str(student.id), "amount": str(amount), "method": method,
                "allocations": [{"student_fee": str(a[0].id), "amount": str(a[1])} for a in allocations],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )

    def test_no_allocations_matches_annotated_and_unannotated(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        with tenant_context(self.school):
            plain = StudentFee.objects.get(id=sf.id)
            annotated = annotate_with_allocation_total(StudentFee.objects.filter(id=sf.id)).get()

            self.assertEqual(get_total_allocated(plain), Decimal("0"))
            self.assertEqual(get_total_allocated(annotated), Decimal("0"))
            self.assertEqual(get_amount_paid(plain), Decimal("0"))
            self.assertEqual(get_outstanding_balance(plain), Decimal("1000"))
            self.assertEqual(get_outstanding_balance(annotated), Decimal("1000"))

    def test_one_allocation_matches_annotated_and_unannotated(self):
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        self._record(client, self.student1, [(sf, Decimal("400"))], Decimal("400"))

        with tenant_context(self.school):
            plain = StudentFee.objects.get(id=sf.id)
            annotated = annotate_with_allocation_total(StudentFee.objects.filter(id=sf.id)).get()

            self.assertEqual(get_total_allocated(plain), Decimal("400"))
            self.assertEqual(get_total_allocated(annotated), Decimal("400"))
            self.assertEqual(get_outstanding_balance(plain), Decimal("600"))
            self.assertEqual(get_outstanding_balance(annotated), Decimal("600"))

    def test_multiple_allocations_including_reversal_matches(self):
        """Mirrors ReversePaymentTests - a reversal's allocation is negative,
        so the net total must come out the same whether annotated or not."""
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        pay_resp = self._record(client, self.student1, [(sf, Decimal("500"))], Decimal("500"))
        with tenant_context(self.school):
            payment = Payment.objects.get(id=pay_resp.data["id"])
            reverse_payment(payment=payment, recorded_by=self.finance_staff_member)

            plain = StudentFee.objects.get(id=sf.id)
            annotated = annotate_with_allocation_total(StudentFee.objects.filter(id=sf.id)).get()

            self.assertEqual(get_total_allocated(plain), Decimal("0"))
            self.assertEqual(get_total_allocated(annotated), Decimal("0"))
            self.assertEqual(get_outstanding_balance(plain), Decimal("1000"))
            self.assertEqual(get_outstanding_balance(annotated), Decimal("1000"))

    def test_unannotated_instance_always_recomputes_fresh_no_stale_cache(self):
        """Deliberately NOT memoized on a plain instance: get_outstanding_balance()
        called again on the SAME Python object after a later write against the
        same row (through a separate query/call, e.g. a reversal) must reflect
        the new state, not a stale value from the first call. This is the
        exact scenario ReversePaymentTests.test_reversal_restores_outstanding_balance
        already covers end-to-end; this test isolates it at the service-function
        level and documents why get_total_allocated() must not cache here."""
        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        pay_resp = self._record(client, self.student1, [(sf, Decimal("300"))], Decimal("300"))

        with tenant_context(self.school):
            plain = StudentFee.objects.get(id=sf.id)
            self.assertEqual(get_outstanding_balance(plain), Decimal("700"))

            payment = Payment.objects.get(id=pay_resp.data["id"])
            reverse_payment(payment=payment, recorded_by=self.finance_staff_member)

            # Re-checking the SAME `plain` instance must see the reversal,
            # not the value cached from the call above.
            self.assertEqual(get_outstanding_balance(plain), Decimal("1000"))

    def test_multiple_student_fees_annotated_in_one_query_not_per_row(self):
        """The core N+1 fix: N annotated StudentFee rows must not cost N
        aggregate queries - the annotation computes all of them in the
        same query that fetches the rows."""
        fees = [self._assign_fee(self.student1, amount_due=Decimal("100")) for _ in range(5)]
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        # Allocate a different amount to each fee so a mixed-up Sum would be caught.
        for i, sf in enumerate(fees):
            self._record(client, self.student1, [(sf, Decimal(10 * (i + 1)))], Decimal(10 * (i + 1)))

        with tenant_context(self.school):
            qs = annotate_with_allocation_total(
                StudentFee.objects.filter(id__in=[f.id for f in fees]).order_by("amount_due", "id")
            )
            with CaptureQueriesContext(connection) as ctx:
                rows = list(qs)
                totals = [get_outstanding_balance(r) for r in rows]

        # get_outstanding_balance() must not add one query per row on top of
        # the single annotated fetch - allow a little headroom (e.g. a
        # connection/session query) rather than asserting a brittle exact count.
        self.assertLessEqual(len(ctx.captured_queries), 2)
        self.assertEqual(
            sorted(float(t) for t in totals),
            sorted(100 - 10 * (i + 1) for i in range(5)),
        )


class OutstandingReportOptimizationTests(FeesFixtureMixin, TransactionTestCase):
    """
    Phase 9B: OutstandingReportView must return the exact same response it
    did before the optimization, and must not issue one allocation
    aggregate query per StudentFee row.
    """

    def _record(self, client, student, allocations, amount, method="cash"):
        return client.post(
            "/api/fees/payments/",
            {
                "student": str(student.id), "amount": str(amount), "method": method,
                "allocations": [{"student_fee": str(a[0].id), "amount": str(a[1])} for a in allocations],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )

    def test_response_unchanged_with_partial_payment_and_section_filter(self):
        sf1 = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._assign_fee(self.student2, amount_due=Decimal("500"))
        self._give_role_only(self.finance_user, ["collect_payments", "view_financial_reports"])
        client = self._client_as(self.finance_user)
        self._record(client, self.student1, [(sf1, Decimal("300"))], Decimal("300"))

        resp = client.get(
            f"/api/fees/reports/outstanding/?section={self.section_a.id}", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 2)
        by_student = {row["student"]: row for row in resp.data["results"]}
        self.assertEqual(Decimal(str(by_student[str(self.student1.id)]["outstanding"])), Decimal("700"))
        self.assertEqual(Decimal(str(by_student[str(self.student2.id)]["outstanding"])), Decimal("500"))

    def test_query_count_does_not_scale_with_fee_count(self):
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)

        for _ in range(3):
            self._assign_fee(self.student1, amount_due=Decimal("100"))
        with CaptureQueriesContext(connection) as small_batch:
            resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

        for _ in range(15):
            self._assign_fee(self.student2, amount_due=Decimal("100"))
        with CaptureQueriesContext(connection) as large_batch:
            resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

        # 18 fees vs 3 fees must not cost anywhere close to 6x the queries -
        # the old per-row aggregate would scale roughly linearly with fee count.
        self.assertLess(len(large_batch.captured_queries), len(small_batch.captured_queries) + 5)


class OutstandingReportPaginationTests(FeesFixtureMixin, TransactionTestCase):
    """
    Phase 9C: OutstandingReportView must be genuinely server-paginated -
    pagination/count operate on the OUTSTANDING dataset (filtered at the
    database level), not on the raw StudentFee set with Python-side
    filtering applied after slicing.
    """

    def _record(self, client, student, allocations, amount, method="cash"):
        return client.post(
            "/api/fees/payments/",
            {
                "student": str(student.id), "amount": str(amount), "method": method,
                "allocations": [{"student_fee": str(a[0].id), "amount": str(a[1])} for a in allocations],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )

    def test_pagination_operates_on_outstanding_dataset_not_raw_fees(self):
        """raw fees: 30, outstanding: 12, page_size: 5. Page 1/2/3 together
        must cover exactly the 12 outstanding fees (5, 5, 2), never any of
        the 18 fully-paid ones, and a 4th page must not exist."""
        self._give_role_only(self.finance_user, ["collect_payments", "view_financial_reports"])
        client = self._client_as(self.finance_user)

        outstanding_heads = []
        for i in range(30):
            with tenant_context(self.school):
                head = FeeHead.objects.create(name=f"PagTest Head {i}")
            sf = self._assign_fee(self.student1, amount_due=Decimal("100"), fee_head=head)
            if i < 18:
                resp = self._record(client, self.student1, [(sf, Decimal("100"))], Decimal("100"))
                self.assertEqual(resp.status_code, 201, resp.data)
            else:
                outstanding_heads.append(head.name)

        self.assertEqual(len(outstanding_heads), 12)

        seen_heads = []
        for page, expected_len in ((1, 5), (2, 5), (3, 2)):
            resp = client.get(
                f"/api/fees/reports/outstanding/?page_size=5&page={page}", HTTP_HOST=self.DOMAIN
            )
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(resp.data["count"], 12)
            self.assertEqual(len(resp.data["results"]), expected_len)
            for row in resp.data["results"]:
                self.assertIn(row["fee_head"], outstanding_heads)
                self.assertGreater(Decimal(str(row["outstanding"])), 0)
            seen_heads.extend(row["fee_head"] for row in resp.data["results"])

        self.assertEqual(sorted(seen_heads), sorted(outstanding_heads))

        resp4 = client.get("/api/fees/reports/outstanding/?page_size=5&page=4", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp4.status_code, 404)

    def test_standard_pagination_envelope_and_page_size_respected(self):
        """Default page_size (20) bounds results even when far more
        outstanding records exist; count reflects the full outstanding set."""
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)

        for _ in range(25):
            self._assign_fee(self.student1, amount_due=Decimal("50"))

        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        for key in ("count", "next", "previous", "results"):
            self.assertIn(key, resp.data)
        self.assertEqual(resp.data["count"], 25)
        self.assertEqual(len(resp.data["results"]), 20)  # StandardResultsPagination default
        self.assertIsNotNone(resp.data["next"])
        self.assertIsNone(resp.data["previous"])

        resp2 = client.get("/api/fees/reports/outstanding/?page=2", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(len(resp2.data["results"]), 5)
        self.assertIsNone(resp2.data["next"])
        self.assertIsNotNone(resp2.data["previous"])

    def test_academic_year_filter_preserved_with_pagination(self):
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)

        self._assign_fee(self.student1, amount_due=Decimal("200"), academic_year="2026")
        self._assign_fee(self.student1, amount_due=Decimal("300"), academic_year="2027")

        resp = client.get(
            "/api/fees/reports/outstanding/?academic_year=2026", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(resp.data["results"][0]["academic_year"], "2026")

    def test_reversal_makes_fee_outstanding_again_in_paginated_report(self):
        """Financial correctness through the new SQL-level filter: a fully
        paid fee is excluded; after its payment is reversed, it must
        reappear as outstanding."""
        self._give_role_only(
            self.finance_user, ["collect_payments", "view_financial_reports"]
        )
        client = self._client_as(self.finance_user)

        sf = self._assign_fee(self.student1, amount_due=Decimal("400"))
        pay_resp = self._record(client, self.student1, [(sf, Decimal("400"))], Decimal("400"))
        self.assertEqual(pay_resp.status_code, 201, pay_resp.data)

        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["count"], 0)

        with tenant_context(self.school):
            payment = Payment.objects.get(id=pay_resp.data["id"])
            reverse_payment(payment=payment, recorded_by=self.finance_staff_member)

        resp2 = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp2.data["count"], 1)
        self.assertEqual(Decimal(str(resp2.data["results"][0]["outstanding"])), Decimal("400"))

    def test_partial_allocation_across_multiple_payments_still_outstanding(self):
        self._give_role_only(
            self.finance_user, ["collect_payments", "view_financial_reports"]
        )
        client = self._client_as(self.finance_user)

        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._record(client, self.student1, [(sf, Decimal("300"))], Decimal("300"))
        self._record(client, self.student1, [(sf, Decimal("200"))], Decimal("200"))

        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(Decimal(str(resp.data["results"][0]["outstanding"])), Decimal("500"))

    def test_annotation_path_still_used_not_per_row_query(self):
        """Phase 9B regression guard, re-verified under the new pagination
        query shape: allocation totals come from the SQL-level annotation,
        not one aggregate query per StudentFee."""
        self._give_role_only(self.finance_user, ["collect_payments", "view_financial_reports"])
        client = self._client_as(self.finance_user)

        for _ in range(8):
            self._assign_fee(self.student1, amount_due=Decimal("100"))

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 8)

        # One aggregate-per-row would show up as 8+ separate SELECTs against
        # paymentallocation beyond the small, fixed set this endpoint issues
        # (the paginated SELECT, the COUNT, and - since Phase 9C-F - the
        # total_outstanding_amount aggregate).
        allocation_selects = [
            q for q in ctx.captured_queries
            if "paymentallocation" in q["sql"].lower() and "select" in q["sql"].lower()
        ]
        self.assertLessEqual(len(allocation_selects), 3)


class OutstandingReportTotalAggregateTests(FeesFixtureMixin, TransactionTestCase):
    """
    Phase 9C-F: `total_outstanding_amount` must represent the SUM of every
    matching outstanding fee - not the current page - and must be computed
    by the database, from the same filtered dataset as `count`/`results`.
    """

    def _record(self, client, student, allocations, amount, method="cash"):
        return client.post(
            "/api/fees/payments/",
            {
                "student": str(student.id), "amount": str(amount), "method": method,
                "allocations": [{"student_fee": str(a[0].id), "amount": str(a[1])} for a in allocations],
            },
            HTTP_HOST=self.DOMAIN, format="json",
        )

    def test_total_is_independent_of_page_and_page_size(self):
        """12 outstanding fees of 100 each -> total 1200, identical on
        every page at page_size=5, and identical again at page_size=20."""
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)

        for _ in range(12):
            self._assign_fee(self.student1, amount_due=Decimal("100"))

        for page in (1, 2, 3):
            resp = client.get(
                f"/api/fees/reports/outstanding/?page_size=5&page={page}", HTTP_HOST=self.DOMAIN
            )
            self.assertEqual(resp.status_code, 200, resp.data)
            self.assertEqual(Decimal(str(resp.data["total_outstanding_amount"])), Decimal("1200"))

        resp_full = client.get("/api/fees/reports/outstanding/?page_size=20", HTTP_HOST=self.DOMAIN)
        self.assertEqual(Decimal(str(resp_full.data["total_outstanding_amount"])), Decimal("1200"))

    def test_total_respects_academic_year_and_section_filters(self):
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)

        self._assign_fee(self.student1, amount_due=Decimal("300"), academic_year="2026")
        self._assign_fee(self.student1, amount_due=Decimal("500"), academic_year="2027")

        resp_2026 = client.get(
            "/api/fees/reports/outstanding/?academic_year=2026", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(Decimal(str(resp_2026.data["total_outstanding_amount"])), Decimal("300"))

        resp_all = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(Decimal(str(resp_all.data["total_outstanding_amount"])), Decimal("800"))

        # student2 is also in section_a; filtering by section must include both.
        self._assign_fee(self.student2, amount_due=Decimal("200"))
        resp_section = client.get(
            f"/api/fees/reports/outstanding/?section={self.section_a.id}", HTTP_HOST=self.DOMAIN
        )
        self.assertEqual(Decimal(str(resp_section.data["total_outstanding_amount"])), Decimal("1000"))

    def test_fully_paid_records_excluded_from_count_and_total(self):
        self._give_role_only(self.finance_user, ["collect_payments", "view_financial_reports"])
        client = self._client_as(self.finance_user)

        sf_paid = self._assign_fee(self.student1, amount_due=Decimal("400"))
        self._record(client, self.student1, [(sf_paid, Decimal("400"))], Decimal("400"))
        self._assign_fee(self.student1, amount_due=Decimal("250"))

        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.data["count"], 1)
        self.assertEqual(Decimal(str(resp.data["total_outstanding_amount"])), Decimal("250"))

    def test_total_uses_net_allocation_across_multiple_payments(self):
        self._give_role_only(self.finance_user, ["collect_payments", "view_financial_reports"])
        client = self._client_as(self.finance_user)

        sf = self._assign_fee(self.student1, amount_due=Decimal("1000"))
        self._record(client, self.student1, [(sf, Decimal("300"))], Decimal("300"))
        self._record(client, self.student1, [(sf, Decimal("200"))], Decimal("200"))

        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(Decimal(str(resp.data["total_outstanding_amount"])), Decimal("500"))

    def test_reversal_changes_the_aggregate(self):
        self._give_role_only(self.finance_user, ["collect_payments", "view_financial_reports"])
        client = self._client_as(self.finance_user)

        sf = self._assign_fee(self.student1, amount_due=Decimal("600"))
        pay_resp = self._record(client, self.student1, [(sf, Decimal("600"))], Decimal("600"))
        self.assertEqual(pay_resp.status_code, 201, pay_resp.data)

        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(Decimal(str(resp.data["total_outstanding_amount"])), Decimal("0"))

        with tenant_context(self.school):
            payment = Payment.objects.get(id=pay_resp.data["id"])
            reverse_payment(payment=payment, recorded_by=self.finance_staff_member)

        resp2 = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(Decimal(str(resp2.data["total_outstanding_amount"])), Decimal("600"))

    def test_zero_result_report_has_zero_total(self):
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)

        resp = client.get("/api/fees/reports/outstanding/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 0)
        self.assertEqual(resp.data["results"], [])
        self.assertEqual(Decimal(str(resp.data["total_outstanding_amount"])), Decimal("0"))

    def test_total_aggregate_is_not_per_row_query(self):
        """The total must be one SQL aggregate, not N aggregate queries for
        N StudentFee rows - re-verified alongside the Phase 9B/9C guard."""
        self._give_role_only(self.finance_user, ["view_financial_reports"])
        client = self._client_as(self.finance_user)

        for _ in range(10):
            self._assign_fee(self.student1, amount_due=Decimal("50"))

        with CaptureQueriesContext(connection) as ctx:
            resp = client.get("/api/fees/reports/outstanding/?page_size=3", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["count"], 10)
        self.assertEqual(Decimal(str(resp.data["total_outstanding_amount"])), Decimal("500"))

        allocation_selects = [
            q for q in ctx.captured_queries
            if "paymentallocation" in q["sql"].lower() and "select" in q["sql"].lower()
        ]
        # Fixed cost regardless of row count: paginated SELECT, COUNT, total aggregate.
        self.assertLessEqual(len(allocation_selects), 3)


class OnlinePaymentDomainAndGatewayTests(FeesFixtureMixin, TransactionTestCase):
    """
    Tests for TenantPaymentGatewayConfig credentials resolution, encryption at rest,
    and eSewa v2 EPAY cryptographic signature verification.
    """

    def test_tenant_gateway_config_encryption_at_rest(self):
        with tenant_context(self.school):
            config = TenantPaymentGatewayConfig.objects.create(
                gateway="esewa",
                merchant_code="SCHOOL_ESEWA_01",
                is_active=True,
            )
            config.set_secret("super_secret_merchant_key_123")
            config.save()

            # The stored DB field must not be plaintext
            raw_db_val = TenantPaymentGatewayConfig.objects.values_list("encrypted_secret", flat=True).get(id=config.id)
            self.assertNotEqual(raw_db_val, "super_secret_merchant_key_123")
            self.assertFalse("super_secret" in raw_db_val)

            # Decryption returns the original secret
            reloaded = TenantPaymentGatewayConfig.objects.get(id=config.id)
            self.assertEqual(reloaded.get_secret(), "super_secret_merchant_key_123")

    def test_tenant_credentials_precedence(self):
        with tenant_context(self.school):
            TenantPaymentGatewayConfig.objects.create(
                gateway="esewa",
                merchant_code="TENANT_CUSTOM_MERCHANT",
                encrypted_secret="",
            )
            cfg = TenantPaymentGatewayConfig.objects.get(gateway="esewa")
            cfg.set_secret("custom_secret_abc")
            cfg.save()

            creds = get_gateway_credentials("esewa")
            self.assertTrue(creds["is_tenant_custom"])
            self.assertEqual(creds["merchant_code"], "TENANT_CUSTOM_MERCHANT")
            self.assertEqual(creds["secret_key"], "custom_secret_abc")

    def test_inactive_tenant_gateway_fails_closed_when_fallback_disabled(self):
        with tenant_context(self.school):
            TenantPaymentGatewayConfig.objects.create(
                gateway="esewa",
                merchant_code="INACTIVE_MERCHANT",
                is_active=False,
                allow_global_fallback=False,
            )
            with self.assertRaises(PaymentConfigurationError) as cm:
                get_gateway_credentials("esewa")
            self.assertIn("disabled for this tenant", str(cm.exception))

    def test_global_fallback_when_no_tenant_config(self):
        with tenant_context(self.school):
            with self.settings(
                ESEWA_PRODUCT_CODE="GLOBAL_EPAYTEST",
                ESEWA_CLIENT_SECRET="global_secret_key_xyz",
                FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK=True,
            ):
                creds = get_gateway_credentials("esewa")
                self.assertFalse(creds["is_tenant_custom"])
                self.assertEqual(creds["merchant_code"], "GLOBAL_EPAYTEST")
                self.assertEqual(creds["secret_key"], "global_secret_key_xyz")

    def test_global_fallback_disabled_raises_error(self):
        with tenant_context(self.school):
            with self.settings(FEES_ALLOW_GLOBAL_GATEWAY_FALLBACK=False):
                with self.assertRaises(PaymentConfigurationError) as cm:
                    get_gateway_credentials("esewa")
                self.assertIn("global fallback is disabled", str(cm.exception))

    def test_esewa_v2_signature_generation_and_verification(self):
        secret_key = "8gBm/:&EnhH.1/q"
        message = "total_amount=100.00,transaction_uuid=11-201-13,product_code=EPAYTEST"
        adapter = EsewaGatewayAdapter()
        sig = adapter.generate_signature(secret_key, message)
        self.assertTrue(isinstance(sig, str))
        self.assertGreater(len(sig), 20)

        # Verification with matching parameters
        import base64
        import json
        payload_dict = {
            "transaction_code": "TX-999888",
            "status": "COMPLETE",
            "total_amount": "100.00",
            "transaction_uuid": "11-201-13",
            "product_code": "EPAYTEST",
            "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code",
        }
        signed_msg = ",".join(f"{f}={payload_dict[f]}" for f in payload_dict["signed_field_names"].split(","))
        payload_dict["signature"] = adapter.generate_signature(secret_key, signed_msg)

        encoded_data = base64.b64encode(json.dumps(payload_dict).encode("utf-8")).decode("utf-8")

        with tenant_context(self.school):
            with self.settings(ESEWA_PRODUCT_CODE="EPAYTEST", ESEWA_CLIENT_SECRET=secret_key):
                order = OnlinePaymentOrder(
                    amount=Decimal("100.00"),
                    gateway_order_id="11-201-13",
                    gateway="esewa",
                )
                res = adapter.verify_callback(order, {"data": encoded_data})
                self.assertTrue(res.is_valid, res.error_message)
                self.assertEqual(res.gateway_reference, "TX-999888")
                self.assertEqual(res.verified_amount, Decimal("100.00"))

    def test_esewa_v2_tampered_payload_rejected(self):
        secret_key = "8gBm/:&EnhH.1/q"
        adapter = EsewaGatewayAdapter()

        import base64
        import json
        payload_dict = {
            "transaction_code": "TX-999888",
            "status": "COMPLETE",
            "total_amount": "100.00",
            "transaction_uuid": "11-201-13",
            "product_code": "EPAYTEST",
            "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code",
        }
        signed_msg = ",".join(f"{f}={payload_dict[f]}" for f in payload_dict["signed_field_names"].split(","))
        payload_dict["signature"] = adapter.generate_signature(secret_key, signed_msg)
        # Tamper amount without recalculating signature
        payload_dict["total_amount"] = "500.00"

        encoded_data = base64.b64encode(json.dumps(payload_dict).encode("utf-8")).decode("utf-8")

        with tenant_context(self.school):
            with self.settings(ESEWA_PRODUCT_CODE="EPAYTEST", ESEWA_CLIENT_SECRET=secret_key):
                order = OnlinePaymentOrder(
                    amount=Decimal("500.00"),
                    gateway_order_id="11-201-13",
                    gateway="esewa",
                )
                res = adapter.verify_callback(order, {"data": encoded_data})
                self.assertFalse(res.is_valid)
                self.assertIn("signature verification failed", res.error_message)


class OnlineFeeInitiationAndSettlementTests(FeesFixtureMixin, TransactionTestCase):
    """
    Tests for initiate_online_payment_order, settle_online_payment_order,
    interim cash settlement conflicts (Option B), and idempotency.
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.fee1 = assign_student_fee(
                student=self.student1,
                fee_head=self.fee_head,
                academic_year="2026",
                amount_due=Decimal("1000.00"),
            )
            # Configure tenant gateway credentials for test school
            cfg = TenantPaymentGatewayConfig.objects.create(
                gateway="esewa",
                merchant_code="TEST_SCHOOL_ESEWA",
                is_active=True,
            )
            cfg.set_secret("test_esewa_secret_key_888")
            cfg.save()

    def _generate_valid_esewa_callback(self, order, secret_key="test_esewa_secret_key_888", merchant_code="TEST_SCHOOL_ESEWA"):
        import base64
        import json
        adapter = EsewaGatewayAdapter()
        payload = {
            "transaction_code": f"TX-ESEWA-{uuid_module.uuid4().hex[:8].upper()}",
            "status": "COMPLETE",
            "total_amount": str(order.amount),
            "transaction_uuid": order.gateway_order_id,
            "product_code": merchant_code,
            "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code",
        }
        msg = ",".join(f"{f}={payload[f]}" for f in payload["signed_field_names"].split(","))
        payload["signature"] = adapter.generate_signature(secret_key, msg)
        return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    def test_initiate_online_payment_order_success(self):
        with tenant_context(self.school):
            order, payload = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("500.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("500.00")}],
                gateway="esewa",
                created_by=self.student1_user,
                return_url="https://feestest.localhost/fees/payment-response",
                failure_url="https://feestest.localhost/fees/payment-response?failed=1",
            )
            self.assertEqual(order.status, "pending")
            self.assertEqual(order.amount, Decimal("500.00"))
            self.assertEqual(order.student, self.student1)
            self.assertEqual(len(order.allocations_snapshot), 1)
            self.assertEqual(order.allocations_snapshot[0]["student_fee_id"], str(self.fee1.id))
            self.assertEqual(order.allocations_snapshot[0]["amount"], "500.00")

            # Payload checks
            self.assertEqual(payload.gateway, "esewa")
            self.assertEqual(payload.form_parameters["product_code"], "TEST_SCHOOL_ESEWA")
            self.assertEqual(payload.form_parameters["amount"], "500.00")
            self.assertTrue("signature" in payload.form_parameters)

    def test_initiate_order_invalid_amount_or_allocations_rejected(self):
        from rest_framework.exceptions import ValidationError
        with tenant_context(self.school):
            # Negative amount
            with self.assertRaises(ValidationError):
                initiate_online_payment_order(
                    student=self.student1,
                    amount=Decimal("-100"),
                    allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("-100")}],
                )

            # Sum mismatch
            with self.assertRaises(ValidationError):
                initiate_online_payment_order(
                    student=self.student1,
                    amount=Decimal("500"),
                    allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("300")}],
                )

            # Allocation exceeds outstanding balance (1000)
            with self.assertRaises(ValidationError):
                initiate_online_payment_order(
                    student=self.student1,
                    amount=Decimal("1500"),
                    allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("1500")}],
                )

            # Fee belongs to another student
            fee2 = assign_student_fee(
                student=self.student2,
                fee_head=self.fee_head,
                academic_year="2026",
                amount_due=Decimal("500.00"),
            )
            with self.assertRaises(ValidationError):
                initiate_online_payment_order(
                    student=self.student1,
                    amount=Decimal("500"),
                    allocations=[{"student_fee_id": fee2.id, "amount": Decimal("500")}],
                )

    def test_settle_online_payment_order_successful_atomic_allocation(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("600.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("600.00")}],
                gateway="esewa",
                created_by=self.student1_user,
            )

            callback_data = self._generate_valid_esewa_callback(order)
            result = settle_online_payment_order(
                order_id_or_gateway_order_id=order.id,
                raw_callback_payload={"data": callback_data},
            )

            self.assertEqual(result["status"], "success")
            order.refresh_from_db()
            self.assertEqual(order.status, "success")
            self.assertIsNotNone(order.payment)
            self.assertEqual(order.payment.amount, Decimal("600.00"))
            self.assertEqual(order.payment.method, "online")
            self.assertTrue(order.payment.receipt_number.startswith("RCPT-"))
            self.assertEqual(order.payment.gateway_reference, order.gateway_reference)

            # Outstanding balance of fee1 drops from 1000 to 400
            self.fee1.refresh_from_db()
            self.assertEqual(get_outstanding_balance(self.fee1), Decimal("400.00"))
            self.assertEqual(get_amount_paid(self.fee1), Decimal("600.00"))

    def test_settle_online_payment_order_idempotent_duplicate_callback(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("400.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("400.00")}],
                gateway="esewa",
            )
            callback_data = self._generate_valid_esewa_callback(order)

            # First settlement
            res1 = settle_online_payment_order(
                order_id_or_gateway_order_id=order.id,
                raw_callback_payload={"data": callback_data},
            )
            self.assertEqual(res1["status"], "success")
            first_payment_id = res1["payment"].id

            # Second settlement with identical callback (simulating browser reload / retry webhook)
            res2 = settle_online_payment_order(
                order_id_or_gateway_order_id=order.id,
                raw_callback_payload={"data": callback_data},
            )
            self.assertEqual(res2["status"], "already_completed")
            self.assertEqual(res2["payment"].id, first_payment_id)

            # Check that Payment count did NOT increase
            self.assertEqual(Payment.objects.filter(student=self.student1).count(), 1)
            self.assertEqual(PaymentAllocation.objects.filter(student_fee=self.fee1).count(), 1)
            self.fee1.refresh_from_db()
            self.assertEqual(get_outstanding_balance(self.fee1), Decimal("600.00"))

    def test_settle_interim_cash_settlement_conflict_requires_reconciliation(self):
        """
        OPTION B Verification:
        1. Parent initiates online payment of 1000 for Tuition.
        2. Student pays 700 cash at desk in the interim. Outstanding drops to 300.
        3. eSewa callback arrives for 1000.
        4. Allocation (1000) exceeds outstanding (300).
        5. Invariant protected: NO broken Payment created.
        6. Order transitions to 'reconciliation_required', preserving ref_id and reason.
        """
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("1000.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("1000.00")}],
                gateway="esewa",
            )

            # Cash payment recorded at desk
            record_payment(
                student=self.student1,
                amount=Decimal("700.00"),
                method="cash",
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("700.00")}],
                recorded_by=self.finance_staff_member,
                reference_note="Cash at counter",
            )
            self.fee1.refresh_from_db()
            self.assertEqual(get_outstanding_balance(self.fee1), Decimal("300.00"))

            # eSewa callback for 1000 arrives
            callback_data = self._generate_valid_esewa_callback(order)
            result = settle_online_payment_order(
                order_id_or_gateway_order_id=order.id,
                raw_callback_payload={"data": callback_data},
            )

            # Must require reconciliation, NOT create invalid payment
            self.assertEqual(result["status"], "reconciliation_required")
            self.assertIn("exceeds current outstanding", result["reason"])

            order.refresh_from_db()
            self.assertEqual(order.status, "reconciliation_required")
            self.assertIsNone(order.payment)  # No payment linked!
            self.assertTrue(len(order.gateway_reference) > 0)  # Preserved ref_id!
            self.assertTrue(len(order.reconciliation_reason) > 0)

            # Fee outstanding balance remains exactly 300 (not corrupted or negative)
            self.fee1.refresh_from_db()
            self.assertEqual(get_outstanding_balance(self.fee1), Decimal("300.00"))
            self.assertEqual(get_amount_paid(self.fee1), Decimal("700.00"))

            # Only 1 payment exists (the cash one)
            self.assertEqual(Payment.objects.filter(student=self.student1).count(), 1)

    def test_settle_interim_fee_cancellation_requires_reconciliation(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("500.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("500.00")}],
                gateway="esewa",
            )

            # Fee cancelled in interim
            cancel_student_fee(self.fee1, reason="Fee waived by principal")
            self.fee1.refresh_from_db()
            self.assertEqual(self.fee1.status, "cancelled")

            callback_data = self._generate_valid_esewa_callback(order)
            result = settle_online_payment_order(
                order_id_or_gateway_order_id=order.id,
                raw_callback_payload={"data": callback_data},
            )

            self.assertEqual(result["status"], "reconciliation_required")
            self.assertIn("cancelled", result["reason"])
            order.refresh_from_db()
            self.assertEqual(order.status, "reconciliation_required")
            self.assertIsNone(order.payment)

    def test_reconcile_online_payment_order_with_mock_gateway(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("250.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("250.00")}],
                gateway="mock",
            )
            self.assertEqual(order.status, "pending")

            res = reconcile_online_payment_order(order)
            self.assertEqual(res["status"], "success")

            order.refresh_from_db()
            self.assertEqual(order.status, "success")
            self.assertIsNotNone(order.payment)
            self.assertEqual(order.payment.amount, Decimal("250.00"))
            self.fee1.refresh_from_db()
            self.assertEqual(get_outstanding_balance(self.fee1), Decimal("750.00"))

    def test_tenant_isolation_orders(self):
        school_b = self._build_school(schema_name="school_b_fees", domain="schoolb.localhost")
        with tenant_context(school_b):
            prog = Program.objects.create(name="B High", code="BH")
            lvl = AcademicLevel.objects.create(program=prog, name="L1", order=1)
            sec = Section.objects.create(level=lvl, name="B1", capacity=30)
            prof_b = Profile.objects.create(first_name="Bob", last_name="Student")
            st_b = Student.objects.create(profile=prof_b, enrollment_id="ENR-B-1", status="active")
            StudentLevel.objects.create(
                student=st_b, level=lvl, section=sec, academic_year="2026", is_current=True
            )
            fh_b = FeeHead.objects.create(name="B Tuition")
            fee_b = assign_student_fee(
                student=st_b,
                fee_head=fh_b,
                academic_year="2026",
                amount_due=Decimal("500.00"),
            )
            cfg_b = TenantPaymentGatewayConfig.objects.create(
                gateway="esewa",
                merchant_code="SCHOOL_B_MERCHANT",
                is_active=True,
            )
            cfg_b.set_secret("secret_b_999")
            cfg_b.save()

            order_b, _ = initiate_online_payment_order(
                student=st_b,
                amount=Decimal("500.00"),
                allocations=[{"student_fee_id": fee_b.id, "amount": Decimal("500.00")}],
                gateway="esewa",
            )

        # In school A, order_b must not exist
        with tenant_context(self.school):
            from rest_framework.exceptions import ValidationError
            with self.assertRaises(ValidationError):
                settle_online_payment_order(
                    order_id_or_gateway_order_id=order_b.id,
                    raw_callback_payload={},
                )
            self.assertFalse(OnlinePaymentOrder.objects.filter(id=order_b.id).exists())


class OnlinePaymentAPITests(FeesFixtureMixin, TransactionTestCase):
    """
    Integration tests for Online Fee Payment REST API endpoints:
    - POST /api/fees/online/initiate/
    - POST /api/parent-portal/children/<id>/pay-fees/
    - POST /api/fees/online/verify/
    - GET /api/fees/online/callback/
    - GET /api/fees/online/orders/<id>/
    - GET /api/fees/online/orders/
    - POST /api/fees/online/orders/<id>/reconcile/
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.fee1 = assign_student_fee(
                student=self.student1,
                fee_head=self.fee_head,
                academic_year="2026",
                amount_due=Decimal("1000.00"),
            )
            cfg = TenantPaymentGatewayConfig.objects.create(
                gateway="esewa",
                merchant_code="TEST_SCHOOL_ESEWA",
                is_active=True,
            )
            cfg.set_secret("test_esewa_secret_key_888")
            cfg.save()

    def _generate_valid_esewa_callback(self, order, secret_key="test_esewa_secret_key_888", merchant_code="TEST_SCHOOL_ESEWA"):
        import base64
        import json
        adapter = EsewaGatewayAdapter()
        payload = {
            "transaction_code": f"TX-ESEWA-{uuid_module.uuid4().hex[:8].upper()}",
            "status": "COMPLETE",
            "total_amount": str(order.amount),
            "transaction_uuid": order.gateway_order_id,
            "product_code": merchant_code,
            "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code",
        }
        msg = ",".join(f"{f}={payload[f]}" for f in payload["signed_field_names"].split(","))
        payload["signature"] = adapter.generate_signature(secret_key, msg)
        return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    def test_student_initiate_online_payment_api_success(self):
        self._give_role_only(self.student1_user, ["pay_own_fees"])
        client = self._client_as(self.student1_user)

        data = {
            "student": str(self.student1.id),
            "amount": "500.00",
            "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "500.00"}],
            "return_url": "https://feestest.localhost/fees/payment-response",
            "failure_url": "https://feestest.localhost/fees/payment-response?failed=1",
        }
        resp = client.post("/api/fees/online/initiate/", data, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["order"]["amount"], "500.00")
        self.assertEqual(resp.data["order"]["status"], "pending")
        self.assertEqual(resp.data["gateway_payload"]["gateway"], "esewa")
        self.assertEqual(resp.data["gateway_payload"]["form_parameters"]["product_code"], "TEST_SCHOOL_ESEWA")
        self.assertTrue("signature" in resp.data["gateway_payload"]["form_parameters"])

    def test_student_initiate_without_pay_own_fees_denied(self):
        self._give_role_only(self.student1_user, ["view_own_fees"])
        client = self._client_as(self.student1_user)

        data = {
            "student": str(self.student1.id),
            "amount": "500.00",
            "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "500.00"}],
        }
        resp = client.post("/api/fees/online/initiate/", data, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_student_initiate_for_different_student_denied(self):
        self._give_role_only(self.student1_user, ["pay_own_fees"])
        client = self._client_as(self.student1_user)

        data = {
            "student": str(self.student2.id),
            "amount": "500.00",
            "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "500.00"}],
        }
        resp = client.post("/api/fees/online/initiate/", data, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

    def test_staff_initiate_online_payment_api_success(self):
        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)

        data = {
            "student": str(self.student1.id),
            "amount": "300.00",
            "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "300.00"}],
        }
        resp = client.post("/api/fees/online/initiate/", data, format="json", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["order"]["amount"], "300.00")

    def test_parent_portal_child_pay_fee_success(self):
        self._give_role_only(self.parent1_user, ["view_own_children", "pay_child_fees"])
        client = self._client_as(self.parent1_user)

        data = {
            "amount": "400.00",
            "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "400.00"}],
            "return_url": "https://feestest.localhost/parent-portal/fees/callback",
        }
        resp = client.post(
            f"/api/parent-portal/children/{self.student1.id}/pay-fees/",
            data,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["order"]["amount"], "400.00")
        self.assertEqual(str(resp.data["order"]["student"]), str(self.student1.id))
        self.assertEqual(resp.data["order"]["created_by_user_id"], str(self.parent1_user.id))

    def test_parent_portal_child_pay_fee_unrelated_child_denied(self):
        self._give_role_only(self.parent1_user, ["view_own_children", "pay_child_fees"])
        client = self._client_as(self.parent1_user)

        data = {
            "amount": "400.00",
            "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "400.00"}],
        }
        resp = client.post(
            f"/api/parent-portal/children/{self.student2.id}/pay-fees/",
            data,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.data["error"], "You do not have access to this child.")

    def test_parent_portal_child_pay_fee_without_permission_denied(self):
        self._give_role_only(self.parent1_user, ["view_own_children", "view_child_fees"])
        client = self._client_as(self.parent1_user)

        data = {
            "amount": "400.00",
            "gateway": "esewa",
            "allocations": [{"student_fee": str(self.fee1.id), "amount": "400.00"}],
        }
        resp = client.post(
            f"/api/parent-portal/children/{self.student1.id}/pay-fees/",
            data,
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 403)

    def test_online_payment_verify_api_success(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("600.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("600.00")}],
                gateway="esewa",
                created_by=self.student1_user,
            )

        callback_b64 = self._generate_valid_esewa_callback(order)
        client = APIClient()
        resp = client.post(
            "/api/fees/online/verify/",
            {"data": callback_b64},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "success")
        self.assertTrue(resp.data["receipt_number"])

        with tenant_context(self.school):
            order.refresh_from_db()
            self.assertEqual(order.status, "success")
            self.assertIsNotNone(order.payment)
            self.assertEqual(order.payment.amount, Decimal("600.00"))
            self.assertEqual(order.payment.receipt_number, resp.data["receipt_number"])

    def test_online_payment_verify_api_idempotent(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("600.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("600.00")}],
                gateway="esewa",
                created_by=self.student1_user,
            )

        callback_b64 = self._generate_valid_esewa_callback(order)
        client = APIClient()
        # First verification
        resp1 = client.post(
            "/api/fees/online/verify/",
            {"data": callback_b64},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(resp1.data["status"], "success")

        # Second verification (idempotent callback)
        with tenant_context(self.school):
            payment_count_before = Payment.objects.count()

        resp2 = client.post(
            "/api/fees/online/verify/",
            {"data": callback_b64},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.data["status"], "already_completed")
        self.assertEqual(resp2.data["receipt_number"], resp1.data["receipt_number"])

        with tenant_context(self.school):
            payment_count_after = Payment.objects.count()
            self.assertEqual(payment_count_before, payment_count_after)

    def test_online_payment_verify_api_tampered_signature_rejected(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("500.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("500.00")}],
                gateway="esewa",
            )

        # Forge signature with wrong secret
        tampered_b64 = self._generate_valid_esewa_callback(order, secret_key="forged_attacker_secret")
        client = APIClient()
        resp = client.post(
            "/api/fees/online/verify/",
            {"data": tampered_b64},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 400)
        with tenant_context(self.school):
            order.refresh_from_db()
            # An unverifiable callback must neither fail the order nor leave its payload behind.
            self.assertEqual(order.status, "pending")
            self.assertEqual(order.gateway_response, {})
            self.assertIsNone(order.payment)

    def test_online_payment_verify_api_interim_cash_settlement_conflict_option_b(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("500.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("500.00")}],
                gateway="esewa",
            )

            # Cash settlement at counter in interim reduces outstanding balance below 500
            record_payment(
                student=self.student1,
                amount=Decimal("800.00"),
                method="cash",
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("800.00")}],
                recorded_by=self.finance_staff_member,
            )
            self.fee1.refresh_from_db()
            self.assertEqual(get_outstanding_balance(self.fee1), Decimal("200.00"))

        callback_b64 = self._generate_valid_esewa_callback(order)
        client = APIClient()
        resp = client.post(
            "/api/fees/online/verify/",
            {"data": callback_b64},
            format="json",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "reconciliation_required")
        # Unauthenticated callers only get a fixed, generic reason; the allocation details stay with staff.
        self.assertEqual(resp.data["reason"], "Payment requires additional verification.")
        self.assertNotIn("outstanding", str(resp.data))

        with tenant_context(self.school):
            order.refresh_from_db()
            self.assertEqual(order.status, "reconciliation_required")
            self.assertIsNone(order.payment)
            self.assertTrue(order.gateway_reference)
            self.assertIn("exceeds current outstanding", order.reconciliation_reason)

    def test_online_payment_callback_get_endpoint(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("350.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("350.00")}],
                gateway="esewa",
            )

        callback_b64 = self._generate_valid_esewa_callback(order)
        client = APIClient()
        resp = client.get(
            f"/api/fees/online/callback/?data={callback_b64}",
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "success")

    def test_online_payment_order_detail_view_permissions(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("200.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("200.00")}],
                gateway="esewa",
                created_by=self.student1_user,
            )

        # Student1 sees own order
        self._give_role_only(self.student1_user, ["view_own_fees"])
        c_student = self._client_as(self.student1_user)
        resp = c_student.get(f"/api/fees/online/orders/{order.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], str(order.id))

        # Parent1 (linked to Student1) sees order
        self._give_role_only(self.parent1_user, ["view_child_fees"])
        c_parent1 = self._client_as(self.parent1_user)
        resp = c_parent1.get(f"/api/fees/online/orders/{order.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

        # Parent2 (linked to Student2) is forbidden
        self._give_role_only(self.parent2_user, ["view_child_fees"])
        c_parent2 = self._client_as(self.parent2_user)
        resp = c_parent2.get(f"/api/fees/online/orders/{order.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 403)

        # Staff with view_fees sees order
        self._give_role_only(self.finance_user, ["view_fees"])
        c_staff = self._client_as(self.finance_user)
        resp = c_staff.get(f"/api/fees/online/orders/{order.id}/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)

    def test_online_payment_order_list_view_scoping(self):
        with tenant_context(self.school):
            fee2 = assign_student_fee(
                student=self.student2,
                fee_head=self.fee_head,
                academic_year="2026",
                amount_due=Decimal("800.00"),
            )
            order1, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("100.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("100.00")}],
                gateway="esewa",
                created_by=self.student1_user,
            )
            order2, _ = initiate_online_payment_order(
                student=self.student2,
                amount=Decimal("200.00"),
                allocations=[{"student_fee_id": fee2.id, "amount": Decimal("200.00")}],
                gateway="esewa",
                created_by=self.parent2_user,
            )

        # Student1 sees only order1
        self._give_role_only(self.student1_user, ["view_own_fees"])
        c_student = self._client_as(self.student1_user)
        resp = c_student.get("/api/fees/online/orders/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        order_ids = [o["id"] for o in resp.data["results"]]
        self.assertIn(str(order1.id), order_ids)
        self.assertNotIn(str(order2.id), order_ids)

        # Parent2 sees only order2
        self._give_role_only(self.parent2_user, ["view_child_fees"])
        c_parent2 = self._client_as(self.parent2_user)
        resp = c_parent2.get("/api/fees/online/orders/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        order_ids = [o["id"] for o in resp.data["results"]]
        self.assertNotIn(str(order1.id), order_ids)
        self.assertIn(str(order2.id), order_ids)

        # Staff with view_fees sees both
        self._give_role_only(self.finance_user, ["view_fees"])
        c_staff = self._client_as(self.finance_user)
        resp = c_staff.get("/api/fees/online/orders/", HTTP_HOST=self.DOMAIN)
        self.assertEqual(resp.status_code, 200)
        order_ids = [o["id"] for o in resp.data["results"]]
        self.assertIn(str(order1.id), order_ids)
        self.assertIn(str(order2.id), order_ids)

    def test_online_payment_manual_reconcile_endpoint(self):
        with tenant_context(self.school):
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("300.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("300.00")}],
                gateway="mock",
            )
            self.assertEqual(order.status, "pending")

        self._give_role_only(self.finance_user, ["collect_payments"])
        client = self._client_as(self.finance_user)
        resp = client.post(
            f"/api/fees/online/orders/{order.id}/reconcile/",
            {},
            HTTP_HOST=self.DOMAIN,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["status"], "success")

        with tenant_context(self.school):
            order.refresh_from_db()
            self.assertEqual(order.status, "success")
            self.assertIsNotNone(order.payment)


class OnlinePaymentCeleryReconciliationTests(FeesFixtureMixin, TransactionTestCase):
    """
    Tests for the Celery periodic task reconcile_pending_online_payments().
    """

    def setUp(self):
        super().setUp()
        with tenant_context(self.school):
            self.fee1 = assign_student_fee(
                student=self.student1,
                fee_head=self.fee_head,
                academic_year="2026",
                amount_due=Decimal("1000.00"),
            )

    def test_reconcile_pending_online_payments_task(self):
        with tenant_context(self.school):
            # Order 1: Mock gateway completes upon status inquiry
            order1, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("300.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("300.00")}],
                gateway="mock",
            )

        summary = reconcile_pending_online_payments(batch_size=10, time_budget=10)

        self.assertGreaterEqual(summary["schemas_checked"], 1)
        self.assertEqual(summary["errors"], 0)
        self.assertEqual(summary["success"], 1)

        with tenant_context(self.school):
            order1.refresh_from_db()
            self.assertEqual(order1.status, "success")
            self.assertIsNotNone(order1.payment)

    def test_reconcile_task_handles_expired_orders(self):
        with tenant_context(self.school):
            from django.utils import timezone
            order, _ = initiate_online_payment_order(
                student=self.student1,
                amount=Decimal("200.00"),
                allocations=[{"student_fee_id": self.fee1.id, "amount": Decimal("200.00")}],
                gateway="esewa",
            )
            order.expires_at = timezone.now() - datetime.timedelta(minutes=30)
            order.save(update_fields=["expires_at"])

        from unittest.mock import patch
        from .gateways import GatewayStatusResult

        with patch.object(
            EsewaGatewayAdapter,
            "query_status",
            return_value=GatewayStatusResult(status="NOT_FOUND", error_message="Order not found"),
        ):
            summary = reconcile_pending_online_payments(batch_size=10, time_budget=10)

        with tenant_context(self.school):
            order.refresh_from_db()
            self.assertEqual(order.status, "expired")
            self.assertIn("expired without gateway confirmation", order.reconciliation_reason)
