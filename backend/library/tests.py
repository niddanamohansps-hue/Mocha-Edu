"""Library: catalogue, lending (limits, one open loan per copy), returns, renewals, lost books, fines billed
into Fees, settings, reports and permissions.

Creates tenant schemas and uses real threads for the race cases, so it needs a disposable PostgreSQL
database and is meant to be run only in an isolated test stage.
"""
import threading
import uuid
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, connection, connections, transaction
from django.test import TransactionTestCase
from django_tenants.utils import tenant_context
from rest_framework import serializers
from rest_framework.test import APIClient

from academics.models import AcademicLevel, Program, Section
from accounts.models import User
from core.models import AuditLog
from fees.models import FeeHead, StudentFee
from organizations.models import Domain, Organization
from profiles.models import Profile
from core.dates import school_today
from roles.constants import SYSTEM_PERMISSIONS
from roles.models import Permission, Role, UserRole
from staff.models import StaffMember
from students.models import Student, StudentLevel

from . import services
from .models import Book, BookCategory, BookCopy, Fine, LibrarySettings, Loan

D = Decimal
PASSWORD = "Pass1234!"
BASE = "/api/library"
Status = BookCopy.Status


def today():
    return school_today()  # the same school-calendar day the library code uses


def ago(days):
    return today() - timedelta(days=days)


class LibraryFixture(TransactionTestCase):
    SCHEMA_A, DOMAIN_A = "lib_a", "lib-a.localhost"
    SCHEMA_B, DOMAIN_B = "lib_b", "lib-b.localhost"

    def _cleanup(self):
        connection.set_schema_to_public()
        for school in Organization.objects.filter(schema_name__in=[self.SCHEMA_A, self.SCHEMA_B]):
            school.delete(force_drop=True)
        User.objects.filter(username__startswith="lib_").delete()

    def _school(self, schema, domain):
        connection.set_schema_to_public()
        school = Organization.objects.create(schema_name=schema, name=schema)
        Domain.objects.create(domain=domain, tenant=school, is_primary=True)
        return school

    def _user(self, name, school, *, role_slug=None, codenames=None):
        connection.set_schema_to_public()
        user = User.objects.create_user(username=f"lib_{name}", email=f"lib_{name}@lib.test", password=PASSWORD)
        with tenant_context(school):
            Profile.objects.create(user_id=user.id, first_name=name, last_name="User")
            if role_slug:
                role = Role.objects.get(slug=role_slug)
            else:
                slug = f"lib-{uuid.uuid4().hex[:10]}"
                role = Role.objects.create(name=slug, slug=slug, is_system_role=False)
                role.permissions.set(Permission.objects.filter(codename__in=codenames or []))
            UserRole.objects.create(user=user, role=role)
        return user

    def _call(self, user, method, path, data=None, host=None):
        client = APIClient()
        if user is not None:
            client.force_authenticate(user=user)
        return getattr(client, method)(f"{BASE}/{path}", data, format="json", HTTP_HOST=host or self.DOMAIN_A)

    @staticmethod
    def rows(response):
        data = response.data
        return data["results"] if isinstance(data, dict) and "results" in data else data

    # --- builders (direct, in the school's schema) ---------------------------------------------------------
    def book(self, title="Maths 5", price=None, **kw):
        with tenant_context(self.school):
            return Book.objects.create(title=title, price=None if price is None else D(price), **kw)

    def copy(self, book=None, accession="ACC-1", **kw):
        book = book or self.book()
        with tenant_context(self.school):
            return BookCopy.objects.create(book=book, accession_number=accession, **kw)

    def student(self, enrollment, first="Kid", enrolled=True, status="active"):
        with tenant_context(self.school):
            student = Student.objects.create(
                profile=Profile.objects.create(first_name=first, last_name=enrollment), enrollment_id=enrollment, status=status
            )
            if enrolled:
                StudentLevel.objects.create(student=student, level=self.level, section=self.section, academic_year="2026", is_current=True)
            return student

    def teacher(self, employee_id="E-L-1", active=True):
        with tenant_context(self.school):
            return StaffMember.objects.create(
                profile=Profile.objects.create(first_name="Sita", last_name=employee_id),
                employee_id=employee_id, designation="Teacher", is_active=active,
            )

    def settings(self, **values):
        with tenant_context(self.school):
            LibrarySettings.update_singleton(**values)

    def lend(self, copy, student=None, staff=None, on=None):
        with tenant_context(self.school):
            return services.issue_book(copy=copy, student=student, staff=staff, issued_on=on, user_id=self.owner.id)

    def give_back(self, loan, on=None):
        with tenant_context(self.school):
            return services.return_book(loan=loan, returned_on=on, user_id=self.owner.id)

    def fresh(self, obj):
        with tenant_context(self.school):
            return type(obj).objects.get(pk=obj.pk)

    def setUp(self):
        self.addCleanup(self._cleanup)
        self._cleanup()
        self.school = self._school(self.SCHEMA_A, self.DOMAIN_A)
        self.school_b = self._school(self.SCHEMA_B, self.DOMAIN_B)
        self.owner = self._user("owner", self.school, role_slug="owner")
        with tenant_context(self.school):
            program = Program.objects.create(name="School", code="SCH")
            self.level = AcademicLevel.objects.create(program=program, name="Grade 5", order=1)
            self.section = Section.objects.create(level=self.level, name="A", capacity=40)


class CatalogueTests(LibraryFixture):
    def test_a_category_is_created_and_must_be_unique(self):
        self.assertEqual(self._call(self.owner, "post", "categories/", {"name": "Science"}).status_code, 201)
        self.assertEqual(self._call(self.owner, "post", "categories/", {"name": "Science"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", "categories/", {"name": "  "}).status_code, 400)

    def test_a_book_is_created_with_a_clean_isbn(self):
        resp = self._call(self.owner, "post", "books/", {"title": " Maths 5 ", "author": "A. Sharma", "isbn": "978-0-14-312854-0", "publication_year": 2019, "price": "450.00"})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual((resp.data["title"], resp.data["isbn"], resp.data["copies_total"]), ("Maths 5", "9780143128540", 0))

    def test_bad_book_input_is_refused(self):
        for payload in ({"title": " "}, {"title": "X", "price": "-1"}, {"title": "X", "publication_year": 999}, {"title": "X", "publication_year": 3000}):
            self.assertEqual(self._call(self.owner, "post", "books/", payload).status_code, 400, payload)

    def test_a_copy_is_created_with_an_upper_case_unique_accession_number(self):
        book = self.book()
        resp = self._call(self.owner, "post", "copies/", {"book": str(book.id), "accession_number": " acc-77 "})
        self.assertEqual((resp.status_code, resp.data["accession_number"], resp.data["status"]), (201, "ACC-77", "available"))
        self.assertEqual(self._call(self.owner, "post", "copies/", {"book": str(book.id), "accession_number": "ACC-77"}).status_code, 400)

    def test_a_copy_cannot_be_created_or_edited_into_issued_or_lost(self):
        book = self.book()
        for status in ("issued", "lost"):
            resp = self._call(self.owner, "post", "copies/", {"book": str(book.id), "accession_number": f"S-{status}", "status": status})
            self.assertEqual(resp.status_code, 400, status)
        copy = self.copy(book, "OK-1")
        self.assertEqual(self._call(self.owner, "patch", f"copies/{copy.id}/", {"status": "issued"}).status_code, 400)
        self.assertEqual(self._call(self.owner, "patch", f"copies/{copy.id}/", {"status": "withdrawn"}).status_code, 200)

    def test_a_copy_out_on_loan_cannot_be_edited_away(self):
        copy = self.copy()
        self.lend(copy, student=self.student("S1"))
        self.assertEqual(self._call(self.owner, "patch", f"copies/{copy.id}/", {"status": "withdrawn"}).status_code, 400)

    def test_a_copy_cannot_move_to_another_title(self):
        copy = self.copy(self.book("One"), "M-1")
        other = self.book("Two")
        self.assertEqual(self._call(self.owner, "patch", f"copies/{copy.id}/", {"book": str(other.id)}).status_code, 400)

    def test_a_lost_copy_can_be_put_back_when_found(self):
        copy = self.copy(status=Status.LOST)
        self.assertEqual(self._call(self.owner, "patch", f"copies/{copy.id}/", {"status": "available"}).status_code, 200)

    def test_copy_counts_on_the_book(self):
        book = self.book()
        self.copy(book, "C-1")
        self.copy(book, "C-2")
        self.copy(book, "C-3", status=Status.WITHDRAWN)
        self.lend(self.copy(book, "C-4"), student=self.student("S1"))
        row = self._call(self.owner, "get", f"books/{book.id}/").data
        self.assertEqual((row["copies_total"], row["copies_available"]), (3, 2))

    def test_search_and_the_available_filter(self):
        a, b = self.book("Algebra", author="Rao"), self.book("Biology", author="Sen")
        self.copy(a, "ALG-1")
        taken = self.copy(b, "BIO-1")
        self.lend(taken, student=self.student("S1"))
        self.assertEqual([r["title"] for r in self.rows(self._call(self.owner, "get", "books/?search=rao"))], ["Algebra"])
        self.assertEqual([r["title"] for r in self.rows(self._call(self.owner, "get", "books/?search=BIO-1"))], ["Biology"])
        self.assertEqual([r["title"] for r in self.rows(self._call(self.owner, "get", "books/?available=true"))], ["Algebra"])

    def test_things_in_use_are_refused_with_409_and_unused_ones_delete(self):
        with tenant_context(self.school):
            category = BookCategory.objects.create(name="Fiction")
        book = self.book(category=category)
        copy = self.copy(book)
        self.lend(copy, student=self.student("S1"))
        self.assertEqual(self._call(self.owner, "delete", f"categories/{category.id}/").status_code, 409)
        self.assertEqual(self._call(self.owner, "delete", f"books/{book.id}/").status_code, 409)
        self.assertEqual(self._call(self.owner, "delete", f"copies/{copy.id}/").status_code, 409)
        spare = self.copy(self.book("Spare"), "SP-1")
        self.assertEqual(self._call(self.owner, "delete", f"copies/{spare.id}/").status_code, 204)

    def test_changes_are_audited(self):
        resp = self._call(self.owner, "post", "books/", {"title": "Audited"})
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="book_created", object_id=resp.data["id"]).exists())


class PermissionTests(LibraryFixture):
    def setUp(self):
        super().setUp()
        self.viewer = self._user("viewer", self.school, codenames=["view_library"])
        self.cataloguer = self._user("cataloguer", self.school, codenames=["view_library", "manage_library"])
        self.lender = self._user("lender", self.school, codenames=["view_library", "lend_library_books"])
        self.cashier = self._user("cashier", self.school, codenames=["view_library", "manage_library_fines"])
        self.plain = self._user("plain", self.school, codenames=[])
        self.owner_b = self._user("owner_b", self.school_b, role_slug="owner")

    def test_the_four_permissions_exist_in_the_catalogue(self):
        codenames = {p["codename"] for p in SYSTEM_PERMISSIONS}
        self.assertTrue({"view_library", "manage_library", "lend_library_books", "manage_library_fines"} <= codenames)

    def test_a_person_with_no_library_permission_sees_nothing(self):
        for path in ("books/", "copies/", "categories/", "loans/", "fines/", "settings/", "summary/"):
            self.assertEqual(self._call(self.plain, "get", path).status_code, 403, path)
        self.assertIn(self._call(None, "get", "books/").status_code, (401, 403))

    def test_a_viewer_reads_but_cannot_change_anything(self):
        copy, student = self.copy(), self.student("S1")
        self.assertEqual(self._call(self.viewer, "get", "books/").status_code, 200)
        self.assertEqual(self._call(self.viewer, "post", "books/", {"title": "X"}).status_code, 403)
        self.assertEqual(self._call(self.viewer, "patch", "settings/", {"fine_per_day": "5"}).status_code, 403)
        self.assertEqual(self._call(self.viewer, "post", "loans/", {"copy": str(copy.id), "student": str(student.id)}).status_code, 403)

    def test_each_permission_opens_only_its_own_action(self):
        copy, student = self.copy(), self.student("S1")
        issue = {"copy": str(copy.id), "student": str(student.id)}
        self.assertEqual(self._call(self.cataloguer, "post", "books/", {"title": "Mine"}).status_code, 201)
        self.assertEqual(self._call(self.cataloguer, "post", "loans/", issue).status_code, 403)
        self.assertEqual(self._call(self.lender, "post", "books/", {"title": "No"}).status_code, 403)
        resp = self._call(self.lender, "post", "loans/", issue)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(self._call(self.lender, "post", f"loans/{resp.data['id']}/return/").status_code, 200)

    def test_fine_actions_need_the_fines_permission(self):
        self.settings(fine_per_day=D("2"))
        loan = self.lend(self.copy(), student=self.student("S1"), on=ago(20))
        _, fine = self.give_back(loan)
        for action, body in (("bill", None), ("waive", {"reason": "x"})):
            self.assertEqual(self._call(self.lender, "post", f"fines/{fine.id}/{action}/", body).status_code, 403, action)
        self.assertEqual(self._call(self.cashier, "post", f"fines/{fine.id}/bill/").status_code, 200)

    def test_another_school_never_sees_this_schools_data(self):
        self.book("Mine")
        mine = self._call(self.owner, "get", "books/")
        theirs = self._call(self.owner_b, "get", "books/", host=self.DOMAIN_B)
        self.assertEqual(len(self.rows(mine)), 1)
        self.assertEqual(self.rows(theirs), [])
        self.assertEqual(self._call(self.owner_b, "get", "books/").status_code, 403)


class LendingTests(LibraryFixture):
    def setUp(self):
        super().setUp()
        self.s1, self.s2 = self.student("S1"), self.student("S2")
        self.teacher1 = self.teacher()

    def test_a_student_loan_is_due_after_the_student_period(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(3))
        self.assertEqual((loan.due_on - loan.issued_on).days, 14)
        self.assertEqual(self.fresh(loan.copy).status, Status.ISSUED)

    def test_a_staff_loan_uses_the_staff_period(self):
        loan = self.lend(self.copy(), staff=self.teacher1)
        self.assertEqual((loan.due_on - loan.issued_on).days, 30)

    def test_periods_and_limits_follow_the_settings(self):
        self.settings(student_loan_days=7, student_max_books=1)
        loan = self.lend(self.copy(accession="A"), student=self.s1)
        self.assertEqual((loan.due_on - loan.issued_on).days, 7)
        with self.assertRaises(serializers.ValidationError):
            self.lend(self.copy(self.book("Other"), "B"), student=self.s1)

    def test_the_limit_on_books_out_is_per_borrower_type(self):
        for i in range(3):
            self.lend(self.copy(self.book(f"T{i}"), f"A{i}"), student=self.s1)
        with self.assertRaises(serializers.ValidationError):
            self.lend(self.copy(self.book("T9"), "A9"), student=self.s1)
        for i in range(5):
            self.lend(self.copy(self.book(f"U{i}"), f"B{i}"), staff=self.teacher1)
        with self.assertRaises(serializers.ValidationError):
            self.lend(self.copy(self.book("U9"), "B9"), staff=self.teacher1)

    def test_a_returned_book_no_longer_counts_against_the_limit(self):
        self.settings(student_max_books=1)
        loan = self.lend(self.copy(accession="A"), student=self.s1)
        self.give_back(loan)
        self.lend(self.copy(self.book("Next"), "B"), student=self.s1)

    def test_the_same_title_twice_is_refused(self):
        book = self.book()
        self.lend(self.copy(book, "A"), student=self.s1)
        with self.assertRaises(serializers.ValidationError):
            self.lend(self.copy(book, "B"), student=self.s1)
        self.lend(self.copy(book, "C"), student=self.s2)  # another borrower may hold a copy of the same title

    def test_exactly_one_borrower_is_required(self):
        copy = self.copy()
        for kwargs in ({}, {"student": self.s1, "staff": self.teacher1}):
            with self.assertRaises(serializers.ValidationError):
                self.lend(copy, **kwargs)

    def test_a_copy_that_is_not_available_cannot_be_lent(self):
        for status in (Status.ISSUED, Status.LOST, Status.WITHDRAWN):
            copy = self.copy(self.book(status), f"X-{status}", status=status)
            with self.assertRaises(serializers.ValidationError):
                self.lend(copy, student=self.s2)

    def test_a_copy_already_lent_cannot_be_lent_again(self):
        copy = self.copy()
        self.lend(copy, student=self.s1)
        with self.assertRaises(serializers.ValidationError):
            self.lend(copy, student=self.s2)

    def test_inactive_borrowers_and_switched_off_titles_are_refused(self):
        gone = self.student("GONE", status="withdrawn")
        left = self.teacher("E-L-2", active=False)
        off = self.book("Off", is_active=False)
        for kwargs, copy in (
            ({"student": gone}, self.copy(accession="A")),
            ({"staff": left}, self.copy(self.book("B"), "B")),
            ({"student": self.s1}, self.copy(off, "C")),
        ):
            with self.assertRaises(serializers.ValidationError):
                self.lend(copy, **kwargs)

    def test_a_future_issue_date_is_refused(self):
        with self.assertRaises(serializers.ValidationError):
            self.lend(self.copy(), student=self.s1, on=today() + timedelta(days=1))

    def test_lending_through_the_api(self):
        copy = self.copy()
        resp = self._call(self.owner, "post", "loans/", {"copy": str(copy.id), "student": str(self.s1.id)})
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            (resp.data["borrower_type"], resp.data["borrower_ref"], resp.data["book_title"], resp.data["is_open"]),
            ("student", "S1", "Maths 5", True),
        )
        again = self._call(self.owner, "post", "loans/", {"copy": str(copy.id), "staff": str(self.teacher1.id)})
        self.assertEqual(again.status_code, 400)
        missing = self._call(self.owner, "post", "loans/", {"copy": str(uuid.uuid4()), "student": str(self.s1.id)})
        self.assertEqual(missing.status_code, 400)
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="library_book_issued").exists())

    def test_loans_are_never_edited_or_deleted_through_the_api(self):
        loan = self.lend(self.copy(), student=self.s1)
        self.assertEqual(self._call(self.owner, "delete", f"loans/{loan.id}/").status_code, 405)
        self.assertEqual(self._call(self.owner, "patch", f"loans/{loan.id}/", {"due_on": "2030-01-01"}).status_code, 405)

    def test_two_librarians_lending_the_same_copy_at_once_cannot_both_succeed(self):
        copy = self.copy()
        outcomes = []

        def lend(student):
            try:
                with tenant_context(self.school):
                    services.issue_book(copy=copy, student=student)
                outcomes.append("ok")
            except serializers.ValidationError:
                outcomes.append("refused")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=lend, args=(s,)) for s in (self.s1, self.s2)]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(outcomes), ["ok", "refused"])
        with tenant_context(self.school):
            self.assertEqual(Loan.objects.filter(copy=copy, returned_on__isnull=True).count(), 1)

    def test_one_borrower_cannot_pass_the_limit_with_simultaneous_requests(self):
        self.settings(student_max_books=1)
        copies = [self.copy(self.book(f"R{i}"), f"R-{i}") for i in range(2)]
        outcomes = []

        def lend(copy):
            try:
                with tenant_context(self.school):
                    services.issue_book(copy=copy, student=self.s1)
                outcomes.append("ok")
            except serializers.ValidationError:
                outcomes.append("refused")
            finally:
                connections.close_all()

        threads = [threading.Thread(target=lend, args=(c,)) for c in copies]
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(sorted(outcomes), ["ok", "refused"])


class ReturnTests(LibraryFixture):
    def setUp(self):
        super().setUp()
        self.s1 = self.student("S1")

    def test_a_return_frees_the_copy_and_closes_the_loan(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(5))
        closed, fine = self.give_back(loan)
        self.assertEqual((closed.returned_on, closed.outcome, fine), (today(), Loan.Outcome.RETURNED, None))
        self.assertEqual(self.fresh(loan.copy).status, Status.AVAILABLE)

    def test_a_loan_cannot_be_closed_twice(self):
        loan = self.lend(self.copy(), student=self.s1)
        self.give_back(loan)
        with self.assertRaises(serializers.ValidationError):
            self.give_back(loan)

    def test_dates_that_make_no_sense_are_refused(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(5))
        for when in (ago(6), today() + timedelta(days=1)):
            with self.assertRaises(serializers.ValidationError):
                self.give_back(loan, on=when)

    def test_a_late_return_costs_nothing_when_the_school_charges_no_fine(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(30))
        _, fine = self.give_back(loan)
        self.assertIsNone(fine)

    def test_a_late_return_is_fined_per_day_overdue(self):
        self.settings(fine_per_day=D("2.50"))
        loan = self.lend(self.copy(), student=self.s1, on=ago(20))  # due 6 days ago
        _, fine = self.give_back(loan)
        self.assertEqual((fine.days_overdue, fine.amount, fine.kind, fine.status), (6, D("15.00"), Fine.Kind.OVERDUE, Fine.Status.PENDING))

    def test_returning_on_the_due_date_or_early_is_free(self):
        self.settings(fine_per_day=D("5"))
        on_time = self.lend(self.copy(accession="A"), student=self.s1, on=ago(14))  # due today
        early = self.lend(self.copy(self.book("B"), "B"), student=self.s1, on=ago(2))
        self.assertIsNone(self.give_back(on_time)[1])
        self.assertIsNone(self.give_back(early)[1])

    def test_a_backdated_return_is_fined_only_to_that_date(self):
        self.settings(fine_per_day=D("1"))
        loan = self.lend(self.copy(), student=self.s1, on=ago(30))  # due 16 days ago
        _, fine = self.give_back(loan, on=ago(10))
        self.assertEqual((fine.days_overdue, fine.amount), (6, D("6.00")))

    def test_returning_through_the_api_shows_the_fine(self):
        self.settings(fine_per_day=D("2"))
        loan = self.lend(self.copy(), student=self.s1, on=ago(20))
        resp = self._call(self.owner, "post", f"loans/{loan.id}/return/")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual((resp.data["is_open"], resp.data["fine"]["amount"], resp.data["fine"]["status"]), (False, "12.00", "pending"))
        self.assertEqual(self._call(self.owner, "post", f"loans/{loan.id}/return/").status_code, 400)
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="library_book_returned").exists())

    def test_an_open_loan_shows_its_overdue_days_and_projected_fine(self):
        self.settings(fine_per_day=D("3"))
        loan = self.lend(self.copy(), student=self.s1, on=ago(20))
        row = self._call(self.owner, "get", f"loans/{loan.id}/").data
        self.assertEqual((row["is_overdue"], row["days_overdue"], row["projected_fine"]), (True, 6, "18.00"))


class RenewalTests(LibraryFixture):
    def setUp(self):
        super().setUp()
        self.s1 = self.student("S1")

    def renew(self, loan):
        with tenant_context(self.school):
            return services.renew(loan=loan, user_id=self.owner.id)

    def test_a_renewal_adds_a_loan_period_to_the_due_date(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(10))
        renewed = self.renew(loan)
        self.assertEqual((renewed.due_on, renewed.renewals), (loan.due_on + timedelta(days=14), 1))

    def test_renewals_stop_at_the_limit(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(2))
        self.renew(loan)
        with self.assertRaises(serializers.ValidationError):
            self.renew(loan)
        self.settings(max_renewals=2)
        self.assertEqual(self.renew(loan).renewals, 2)

    def test_no_renewals_when_the_limit_is_zero(self):
        self.settings(max_renewals=0)
        loan = self.lend(self.copy(), student=self.s1)
        with self.assertRaises(serializers.ValidationError):
            self.renew(loan)

    def test_an_overdue_loan_cannot_be_renewed(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(20))
        with self.assertRaises(serializers.ValidationError):
            self.renew(loan)

    def test_a_closed_loan_cannot_be_renewed(self):
        loan = self.lend(self.copy(), student=self.s1)
        self.give_back(loan)
        with self.assertRaises(serializers.ValidationError):
            self.renew(loan)

    def test_renewing_through_the_api(self):
        loan = self.lend(self.copy(), student=self.s1, on=ago(2))
        resp = self._call(self.owner, "post", f"loans/{loan.id}/renew/")
        self.assertEqual((resp.status_code, resp.data["renewals"]), (200, 1))
        self.assertEqual(self._call(self.owner, "post", f"loans/{loan.id}/renew/").status_code, 400)


class LostBookTests(LibraryFixture):
    def setUp(self):
        super().setUp()
        self.s1 = self.student("S1")

    def lose(self, loan, **kw):
        with tenant_context(self.school):
            return services.report_lost(loan=loan, user_id=self.owner.id, **kw)

    def test_a_lost_book_closes_the_loan_and_takes_the_copy_out_of_circulation(self):
        loan = self.lend(self.copy(self.book(price="450")), student=self.s1)
        closed, fine = self.lose(loan)
        self.assertEqual((closed.outcome, closed.returned_on), (Loan.Outcome.LOST, today()))
        self.assertEqual(self.fresh(loan.copy).status, Status.LOST)
        self.assertEqual((fine.kind, fine.amount), (Fine.Kind.LOST, D("450.00")))

    def test_a_book_with_no_price_costs_nothing_when_lost(self):
        loan = self.lend(self.copy(), student=self.s1)
        self.assertIsNone(self.lose(loan)[1])

    def test_a_lost_copy_cannot_be_lent_and_its_loan_cannot_be_returned(self):
        loan = self.lend(self.copy(), student=self.s1)
        self.lose(loan)
        with self.assertRaises(serializers.ValidationError):
            self.give_back(loan)
        with self.assertRaises(serializers.ValidationError):
            self.lend(loan.copy, student=self.student("S2"))

    def test_reporting_lost_through_the_api(self):
        loan = self.lend(self.copy(self.book(price="100")), student=self.s1)
        resp = self._call(self.owner, "post", f"loans/{loan.id}/lost/")
        self.assertEqual((resp.status_code, resp.data["outcome"], resp.data["fine"]["amount"]), (200, "lost", "100.00"))
        with tenant_context(self.school):
            self.assertTrue(AuditLog.objects.filter(action="library_book_lost").exists())

    def test_a_loan_cannot_carry_two_fines_of_the_same_kind(self):
        self.settings(fine_per_day=D("1"))
        loan = self.lend(self.copy(), student=self.s1, on=ago(20))
        self.give_back(loan)
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Fine.objects.create(loan=loan, kind=Fine.Kind.OVERDUE, amount=D("1"))


class FineTests(LibraryFixture):
    def setUp(self):
        super().setUp()
        self.settings(fine_per_day=D("2"))
        self.s1 = self.student("S1")
        self.teacher1 = self.teacher()

    def fine_for(self, student=None, staff=None, accession="F-1", days=20):
        loan = self.lend(self.copy(self.book(accession), accession), student=student, staff=staff, on=ago(days))
        return self.give_back(loan)[1]

    def act(self, name, fine, **kw):
        with tenant_context(self.school):
            return getattr(services, name)(fine=fine, user_id=self.owner.id, **kw)

    def test_billing_a_student_fine_creates_a_library_fee_in_fees(self):
        fine = self.fine_for(student=self.s1)  # due 6 days ago: 12.00
        billed = self.act("bill_fine", fine)
        self.assertEqual((billed.status, billed.resolved_at is not None), (Fine.Status.BILLED, True))
        with tenant_context(self.school):
            fee = StudentFee.objects.get(pk=billed.student_fee_id)
            self.assertEqual((fee.fee_head.name, fee.amount_due, fee.student_id, fee.academic_year, fee.due_date), ("Library", D("12.00"), self.s1.id, "2026", today()))

    def test_a_fine_cannot_be_billed_twice(self):
        fine = self.fine_for(student=self.s1)
        self.act("bill_fine", fine)
        with self.assertRaises(serializers.ValidationError):
            self.act("bill_fine", fine)
        with tenant_context(self.school):
            self.assertEqual(StudentFee.objects.filter(fee_head__name="Library").count(), 1)

    def test_a_staff_fine_cannot_be_billed_in_fees_but_can_be_collected(self):
        fine = self.fine_for(staff=self.teacher1, days=40)  # due 10 days ago
        with self.assertRaises(serializers.ValidationError):
            self.act("bill_fine", fine)
        collected = self.act("collect_fine", fine)
        self.assertEqual(collected.status, Fine.Status.COLLECTED)

    def test_a_student_fine_cannot_be_collected_at_the_desk(self):
        fine = self.fine_for(student=self.s1)
        with self.assertRaises(serializers.ValidationError):
            self.act("collect_fine", fine)

    def test_waiving_needs_a_reason_and_closes_the_fine(self):
        fine = self.fine_for(student=self.s1)
        for reason in ("", "   "):
            with self.assertRaises(serializers.ValidationError):
                self.act("waive_fine", fine, reason=reason)
        waived = self.act("waive_fine", fine, reason="Book was in a flood")
        self.assertEqual((waived.status, waived.waive_reason), (Fine.Status.WAIVED, "Book was in a flood"))
        with self.assertRaises(serializers.ValidationError):
            self.act("bill_fine", fine)
        with tenant_context(self.school):
            self.assertEqual(StudentFee.objects.filter(fee_head__name="Library").count(), 0)

    def test_a_billed_fine_cannot_be_waived_here(self):
        fine = self.fine_for(student=self.s1)
        self.act("bill_fine", fine)
        with self.assertRaises(serializers.ValidationError):
            self.act("waive_fine", fine, reason="changed my mind")

    def test_a_student_without_a_class_cannot_be_billed(self):
        lone = self.student("LONE", enrolled=False)
        fine = self.fine_for(student=lone, accession="L-1")
        with self.assertRaises(serializers.ValidationError):
            self.act("bill_fine", fine)
        self.assertEqual(self.fresh(fine).status, Fine.Status.PENDING)

    def test_a_switched_off_library_fee_head_blocks_billing(self):
        fine = self.fine_for(student=self.s1)
        with tenant_context(self.school):
            FeeHead.objects.update_or_create(name="Library", defaults={"is_active": False})
        with self.assertRaises(serializers.ValidationError):
            self.act("bill_fine", fine)

    def test_fine_actions_through_the_api(self):
        billed = self.fine_for(student=self.s1, accession="A")
        waived = self.fine_for(student=self.student("S2"), accession="B")
        paid = self.fine_for(staff=self.teacher1, accession="C", days=40)
        r1 = self._call(self.owner, "post", f"fines/{billed.id}/bill/")
        self.assertEqual((r1.status_code, r1.data["status"], r1.data["student_fee"] is not None), (200, "billed", True))
        self.assertEqual(self._call(self.owner, "post", f"fines/{waived.id}/waive/", {}).status_code, 400)
        self.assertEqual(self._call(self.owner, "post", f"fines/{waived.id}/waive/", {"reason": "Kind"}).data["status"], "waived")
        self.assertEqual(self._call(self.owner, "post", f"fines/{paid.id}/collect/").data["status"], "collected")
        with tenant_context(self.school):
            actions = set(AuditLog.objects.values_list("action", flat=True))
        self.assertTrue({"library_fine_billed", "library_fine_waived", "library_fine_collected"} <= actions)

    def test_the_fine_list_filters_by_status_and_shows_who_owes(self):
        self.fine_for(student=self.s1, accession="A")
        done = self.fine_for(staff=self.teacher1, accession="B", days=40)
        self.act("collect_fine", done)
        pending = self.rows(self._call(self.owner, "get", "fines/?status=pending"))
        self.assertEqual([(r["borrower_type"], r["borrower_ref"], r["amount"]) for r in pending], [("student", "S1", "12.00")])
        self.assertEqual(len(self.rows(self._call(self.owner, "get", "fines/"))), 2)

    def test_fines_are_never_edited_or_deleted_through_the_api(self):
        fine = self.fine_for(student=self.s1)
        self.assertEqual(self._call(self.owner, "delete", f"fines/{fine.id}/").status_code, 405)
        self.assertEqual(self._call(self.owner, "patch", f"fines/{fine.id}/", {"amount": "1"}).status_code, 405)


class SettingsAndReportTests(LibraryFixture):
    def test_reading_settings_without_a_saved_row_returns_defaults_and_writes_nothing(self):
        resp = self._call(self.owner, "get", "settings/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            (resp.data["student_loan_days"], resp.data["staff_loan_days"], resp.data["student_max_books"], resp.data["staff_max_books"],
             resp.data["max_renewals"], resp.data["fine_per_day"], resp.data["is_default"]),
            (14, 30, 3, 5, 1, "0.00", True),
        )
        with tenant_context(self.school):
            self.assertEqual(LibrarySettings.objects.count(), 0)

    def test_settings_are_changed_and_audited(self):
        resp = self._call(self.owner, "patch", "settings/", {"student_loan_days": 10, "fine_per_day": "1.50"})
        self.assertEqual((resp.status_code, resp.data["student_loan_days"], resp.data["fine_per_day"], resp.data["is_default"]), (200, 10, "1.50", False))
        with tenant_context(self.school):
            self.assertEqual(LibrarySettings.objects.count(), 1)
            self.assertTrue(AuditLog.objects.filter(action="library_settings_changed").exists())

    def test_bad_settings_are_refused(self):
        for payload in ({}, {"nonsense": 1}, {"fine_per_day": "-1"}, {"student_loan_days": 0}, {"student_max_books": 0}, {"max_renewals": -1}):
            self.assertEqual(self._call(self.owner, "patch", "settings/", payload).status_code, 400, payload)

    def test_the_state_filter_and_the_summary(self):
        s1, s2, s3 = self.student("S1"), self.student("S2"), self.student("S3")
        late = self.lend(self.copy(self.book("Late"), "L"), student=s1, on=ago(20))
        self.lend(self.copy(self.book("Fresh"), "F"), student=s2)
        done = self.lend(self.copy(self.book("Done"), "D"), student=s3, on=ago(3))
        self.give_back(done)
        self.copy(self.book("Free"), "FR")
        self.copy(self.book("Gone"), "G", status=Status.LOST)
        ids = lambda q: [r["id"] for r in self.rows(self._call(self.owner, "get", f"loans/?state={q}"))]
        self.assertEqual(ids("overdue"), [str(late.id)])
        self.assertEqual(len(ids("open")), 2)
        self.assertEqual(ids("closed"), [str(done.id)])
        summary = self._call(self.owner, "get", "summary/").data
        self.assertEqual(summary["open_loans"], 2)
        self.assertEqual(summary["overdue_loans"], 1)
        self.assertEqual(summary["copies"], {"total": 5, "available": 2, "issued": 2, "lost": 1})

    def test_the_database_allows_only_one_open_loan_per_copy(self):
        copy, s1, s2 = self.copy(), self.student("S1"), self.student("S2")
        self.lend(copy, student=s1)
        with tenant_context(self.school):
            with self.assertRaises(IntegrityError):
                with transaction.atomic():
                    Loan.objects.create(copy=copy, student=s2, issued_on=today(), due_on=today())

    def test_the_database_requires_exactly_one_borrower_and_sane_dates(self):
        copy, s1, teacher = self.copy(), self.student("S1"), self.teacher()
        with tenant_context(self.school):
            for kwargs in (
                {},
                {"student": s1, "staff": teacher},
                {"student": s1, "issued_on": today(), "due_on": ago(1)},
                {"student": s1, "issued_on": today(), "due_on": today(), "returned_on": ago(1)},
            ):
                values = {"issued_on": today(), "due_on": today(), **kwargs}
                with self.assertRaises(IntegrityError):
                    with transaction.atomic():
                        Loan.objects.create(copy=copy, **values)
