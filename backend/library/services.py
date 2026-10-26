"""Library rules: lending, returning, renewing, lost books and fines.

Every change locks the rows it depends on first (the copy, the borrower, the loan), so two librarians cannot
lend the same copy at once, or push one borrower over their limit together. The database backs that up:
at most one open loan per copy. A student's fine is billed into ``fees.StudentFee`` (the Library head) so it is
paid and receipted in Fees; nothing here records a payment.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from core.dates import school_today
from fees.models import FeeHead
from fees.services import assign_student_fee
from staff.models import StaffMember
from students.models import Student

from .models import Book, BookCopy, Fine, LibrarySettings, Loan

FEE_HEAD_NAME = "Library"
Status = BookCopy.Status


def _limits(settings, *, is_student):
    if is_student:
        return settings.student_loan_days, settings.student_max_books
    return settings.staff_loan_days, settings.staff_max_books


def open_loans_of(*, student=None, staff=None):
    return Loan.objects.filter(returned_on__isnull=True, student=student) if student else Loan.objects.filter(returned_on__isnull=True, staff=staff)


# --- Lending -----------------------------------------------------------------------------------------------

@transaction.atomic
def issue_book(*, copy, student=None, staff=None, issued_on=None, user_id=None):
    """Lend ``copy`` to exactly one of ``student`` / ``staff``. The due date and the limit on books out come
    from the school's library settings, by borrower type."""
    if (student is None) == (staff is None):
        raise serializers.ValidationError({"borrower": "Choose exactly one borrower: a student or a staff member."})
    today = school_today()
    issued_on = issued_on or today
    if issued_on > today:
        raise serializers.ValidationError({"issued_on": "A book cannot be issued on a future date."})

    copy = BookCopy.objects.select_for_update().get(pk=copy.pk)
    book = Book.objects.get(pk=copy.book_id)
    if student is not None:
        borrower = Student.objects.select_for_update().get(pk=student.pk)
        active = borrower.status == "active"
    else:
        borrower = StaffMember.objects.select_for_update().get(pk=staff.pk)
        active = borrower.is_active
    if not active:
        raise serializers.ValidationError({"borrower": "Only an active student or staff member can borrow books."})
    if not book.is_active:
        raise serializers.ValidationError({"copy": "This title is switched off in the catalogue."})
    if copy.status != Status.AVAILABLE:
        raise serializers.ValidationError({"copy": f"This copy is not available (it is {copy.get_status_display().lower()})."})

    settings = LibrarySettings.load()
    loan_days, max_books = _limits(settings, is_student=student is not None)
    held = open_loans_of(student=borrower if student else None, staff=None if student else borrower)
    if held.count() >= max_books:
        raise serializers.ValidationError({"borrower": f"This borrower already has {max_books} books out, which is the limit."})
    if held.filter(copy__book_id=book.id).exists():
        raise serializers.ValidationError({"copy": "This borrower already has a copy of this book."})

    loan = Loan.objects.create(
        copy=copy, student=borrower if student else None, staff=None if student else borrower,
        issued_on=issued_on, due_on=issued_on + timedelta(days=loan_days), issued_by_user_id=user_id,
    )
    copy.status = Status.ISSUED
    copy.save(update_fields=["status", "updated_at"])
    return loan


def _open_loan_locked(loan):
    loan = Loan.objects.select_for_update().get(pk=loan.pk)
    if loan.returned_on is not None:
        raise serializers.ValidationError({"loan": "This loan is already closed."})
    return loan


def _check_close_date(loan, on):
    today = school_today()
    on = on or today
    if on > today:
        raise serializers.ValidationError({"date": "The date cannot be in the future."})
    if on < loan.issued_on:
        raise serializers.ValidationError({"date": "A book cannot come back before it was issued."})
    return on


@transaction.atomic
def return_book(*, loan, returned_on=None, user_id=None):
    """Close the loan and free the copy. A late return raises an overdue fine when the school charges one."""
    loan = _open_loan_locked(loan)
    returned_on = _check_close_date(loan, returned_on)
    copy = BookCopy.objects.select_for_update().get(pk=loan.copy_id)
    loan.returned_on, loan.outcome, loan.closed_by_user_id = returned_on, Loan.Outcome.RETURNED, user_id
    loan.save(update_fields=["returned_on", "outcome", "closed_by_user_id", "updated_at"])
    copy.status = Status.AVAILABLE
    copy.save(update_fields=["status", "updated_at"])

    fine = None
    days = (returned_on - loan.due_on).days
    rate = LibrarySettings.load().fine_per_day
    if days > 0 and rate > 0:
        fine = Fine.objects.create(loan=loan, kind=Fine.Kind.OVERDUE, amount=rate * days, days_overdue=days)
    return loan, fine


@transaction.atomic
def report_lost(*, loan, on=None, user_id=None):
    """Close the loan as lost. The copy leaves circulation; the borrower is charged the book's price, if it has one."""
    loan = _open_loan_locked(loan)
    on = _check_close_date(loan, on)
    copy = BookCopy.objects.select_for_update().get(pk=loan.copy_id)
    loan.returned_on, loan.outcome, loan.closed_by_user_id = on, Loan.Outcome.LOST, user_id
    loan.save(update_fields=["returned_on", "outcome", "closed_by_user_id", "updated_at"])
    copy.status = Status.LOST
    copy.save(update_fields=["status", "updated_at"])

    fine = None
    price = Book.objects.get(pk=copy.book_id).price
    if price is not None and price > 0:
        fine = Fine.objects.create(loan=loan, kind=Fine.Kind.LOST, amount=price)
    return loan, fine


@transaction.atomic
def renew(*, loan, user_id=None):
    """Extend an open, not-yet-overdue loan by the borrower type's loan period, up to the renewal limit."""
    loan = _open_loan_locked(loan)
    settings = LibrarySettings.load()
    if school_today() > loan.due_on:
        raise serializers.ValidationError({"loan": "This book is overdue. Return it instead of renewing."})
    if loan.renewals >= settings.max_renewals:
        raise serializers.ValidationError({"loan": f"This loan has already been renewed {loan.renewals} time(s), which is the limit."})
    loan_days, _ = _limits(settings, is_student=loan.student_id is not None)
    loan.due_on = loan.due_on + timedelta(days=loan_days)
    loan.renewals += 1
    loan.save(update_fields=["due_on", "renewals", "updated_at"])
    return loan


# --- Fines -------------------------------------------------------------------------------------------------

def _pending_fine_locked(fine):
    fine = Fine.objects.select_for_update().select_related("loan").get(pk=fine.pk)
    if fine.status != Fine.Status.PENDING:
        raise serializers.ValidationError({"fine": f"This fine is already {fine.get_status_display().lower()}."})
    return fine


def _resolve(fine, status, user_id):
    fine.status, fine.resolved_by_user_id, fine.resolved_at = status, user_id, timezone.now()


@transaction.atomic
def bill_fine(*, fine, user_id=None):
    """Turn a student's fine into a Library fee in Fees, where it is paid and receipted."""
    fine = _pending_fine_locked(fine)
    student = fine.loan.student
    if student is None:
        raise serializers.ValidationError({"fine": "A staff member's fine is collected at the library, not billed in Fees."})
    current = student.enrollments.filter(is_current=True).first()
    if current is None:
        raise serializers.ValidationError({"fine": "This student is not enrolled in a class this year, so a fee cannot be created. Waive the fine or enrol the student first."})
    head, _ = FeeHead.objects.get_or_create(name=FEE_HEAD_NAME)
    if not head.is_active:
        raise serializers.ValidationError({"fine": "The Library fee head is switched off in Fees. Switch it on first."})
    fee = assign_student_fee(
        student=student, fee_head=head, academic_year=current.academic_year, amount_due=fine.amount,
        due_date=school_today(),
    )
    fine.student_fee = fee
    _resolve(fine, Fine.Status.BILLED, user_id)
    fine.save(update_fields=["student_fee", "status", "resolved_by_user_id", "resolved_at"])
    return fine


@transaction.atomic
def collect_fine(*, fine, user_id=None):
    """Record that a staff member's fine was paid at the library."""
    fine = _pending_fine_locked(fine)
    if fine.loan.staff_id is None:
        raise serializers.ValidationError({"fine": "A student's fine is billed in Fees so it is paid and receipted there. Use Bill in Fees."})
    _resolve(fine, Fine.Status.COLLECTED, user_id)
    fine.save(update_fields=["status", "resolved_by_user_id", "resolved_at"])
    return fine


@transaction.atomic
def waive_fine(*, fine, reason, user_id=None):
    fine = _pending_fine_locked(fine)
    reason = (reason or "").strip()
    if not reason:
        raise serializers.ValidationError({"reason": "Give the reason for waiving the fine."})
    fine.waive_reason = reason[:255]
    _resolve(fine, Fine.Status.WAIVED, user_id)
    fine.save(update_fields=["waive_reason", "status", "resolved_by_user_id", "resolved_at"])
    return fine


# --- Reports -----------------------------------------------------------------------------------------------

def overdue_loans(today=None):
    today = today or school_today()
    return Loan.objects.filter(returned_on__isnull=True, due_on__lt=today)


def projected_fine(loan, today=None):
    """What an open loan would cost if returned today (0 when the school charges no fine)."""
    today = today or school_today()
    days = (today - loan.due_on).days
    return Decimal("0") if days <= 0 else LibrarySettings.load().fine_per_day * days
