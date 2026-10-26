from django.conf import settings as django_settings
from rest_framework import serializers

from core.dates import school_today

from . import services
from .models import Book, BookCategory, BookCopy, Fine, LibrarySettings, Loan


def person_name(profile):
    return f"{profile.first_name} {profile.last_name}".strip()


class BookCategorySerializer(serializers.ModelSerializer):
    books_count = serializers.SerializerMethodField()

    class Meta:
        model = BookCategory
        fields = ("id", "name", "books_count", "created_at")
        read_only_fields = ("id", "created_at")

    def get_books_count(self, category):
        return category.books.count()

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the category name.")
        return value


class BookSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")
    copies_total = serializers.SerializerMethodField()
    copies_available = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = ("id", "title", "author", "isbn", "category", "category_name", "publisher", "publication_year",
                  "shelf_location", "price", "description", "is_active", "copies_total", "copies_available",
                  "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def get_copies_total(self, book):
        return sum(1 for c in book.copies.all() if c.status != BookCopy.Status.WITHDRAWN)

    def get_copies_available(self, book):
        return sum(1 for c in book.copies.all() if c.status == BookCopy.Status.AVAILABLE)

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Enter the title.")
        return value

    def validate_isbn(self, value):
        return value.replace("-", "").replace(" ", "").upper()

    def validate_publication_year(self, value):
        if value is not None and not 1000 <= value <= school_today().year + 1:
            raise serializers.ValidationError("Enter a real year.")
        return value


class BookCopySerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title", read_only=True)
    borrower_name = serializers.SerializerMethodField()

    class Meta:
        model = BookCopy
        fields = ("id", "book", "book_title", "accession_number", "status", "notes", "borrower_name", "created_at")
        read_only_fields = ("id", "created_at")

    def get_borrower_name(self, copy):
        loan = next((l for l in copy.loans.all() if l.returned_on is None), None)
        if loan is None:
            return ""
        return person_name((loan.student or loan.staff).profile)

    def validate_accession_number(self, value):
        value = value.strip().upper()
        if not value:
            raise serializers.ValidationError("Enter the accession number.")
        return value

    def validate_status(self, value):
        # Issued and lost come only from lending a book or reporting it lost.
        current = getattr(self.instance, "status", None)
        if value != current and value not in (BookCopy.Status.AVAILABLE, BookCopy.Status.WITHDRAWN):
            raise serializers.ValidationError("A copy becomes issued or lost through the loan, not by editing it.")
        if self.instance is not None and current == BookCopy.Status.ISSUED and value != current:
            raise serializers.ValidationError("This copy is out on loan. Take the book back first.")
        return value

    def validate_book(self, book):
        if self.instance is not None and book.pk != self.instance.book_id:
            raise serializers.ValidationError("A copy cannot be moved to another title.")
        return book


class LoanSerializer(serializers.ModelSerializer):
    book = serializers.UUIDField(source="copy.book_id", read_only=True)
    book_title = serializers.CharField(source="copy.book.title", read_only=True)
    accession_number = serializers.CharField(source="copy.accession_number", read_only=True)
    borrower_type = serializers.SerializerMethodField()
    borrower_name = serializers.SerializerMethodField()
    borrower_ref = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    is_overdue = serializers.SerializerMethodField()
    days_overdue = serializers.SerializerMethodField()
    projected_fine = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = ("id", "copy", "book", "book_title", "accession_number", "student", "staff", "borrower_type",
                  "borrower_name", "borrower_ref", "issued_on", "due_on", "returned_on", "outcome", "renewals",
                  "is_open", "is_overdue", "days_overdue", "projected_fine", "created_at")
        read_only_fields = fields

    def _who(self, loan):
        return loan.student or loan.staff

    def get_borrower_type(self, loan):
        return "student" if loan.student_id else "staff"

    def get_borrower_name(self, loan):
        return person_name(self._who(loan).profile)

    def get_borrower_ref(self, loan):
        who = self._who(loan)
        return who.enrollment_id if loan.student_id else who.employee_id

    def get_is_open(self, loan):
        return loan.returned_on is None

    def get_days_overdue(self, loan):
        if loan.returned_on is not None:
            return max(0, (loan.returned_on - loan.due_on).days)
        return max(0, (school_today() - loan.due_on).days)

    def get_is_overdue(self, loan):
        return loan.returned_on is None and school_today() > loan.due_on

    def get_projected_fine(self, loan):
        return f"{services.projected_fine(loan):.2f}" if loan.returned_on is None else "0.00"


class IssueInputSerializer(serializers.Serializer):
    copy = serializers.UUIDField()
    student = serializers.UUIDField(required=False, allow_null=True)
    staff = serializers.UUIDField(required=False, allow_null=True)
    issued_on = serializers.DateField(required=False)

    def validate(self, attrs):
        from staff.models import StaffMember
        from students.models import Student

        copy = BookCopy.objects.filter(pk=attrs["copy"]).first()
        if copy is None:
            raise serializers.ValidationError({"copy": "Copy not found."})
        student = staff = None
        if attrs.get("student"):
            student = Student.objects.filter(pk=attrs["student"]).first()
            if student is None:
                raise serializers.ValidationError({"student": "Student not found."})
        if attrs.get("staff"):
            staff = StaffMember.objects.filter(pk=attrs["staff"]).first()
            if staff is None:
                raise serializers.ValidationError({"staff": "Staff member not found."})
        return {"copy": copy, "student": student, "staff": staff, "issued_on": attrs.get("issued_on")}


class CloseInputSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)


class FineSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="loan.copy.book.title", read_only=True)
    borrower_type = serializers.SerializerMethodField()
    borrower_name = serializers.SerializerMethodField()
    borrower_ref = serializers.SerializerMethodField()

    class Meta:
        model = Fine
        fields = ("id", "loan", "book_title", "borrower_type", "borrower_name", "borrower_ref", "kind", "amount",
                  "days_overdue", "status", "student_fee", "waive_reason", "resolved_at", "created_at")
        read_only_fields = fields

    def _who(self, fine):
        return fine.loan.student or fine.loan.staff

    def get_borrower_type(self, fine):
        return "student" if fine.loan.student_id else "staff"

    def get_borrower_name(self, fine):
        return person_name(self._who(fine).profile)

    def get_borrower_ref(self, fine):
        who = self._who(fine)
        return who.enrollment_id if fine.loan.student_id else who.employee_id


class WaiveInputSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=255)


class LibrarySettingsSerializer(serializers.Serializer):
    student_loan_days = serializers.IntegerField(required=False, min_value=1, max_value=365)
    staff_loan_days = serializers.IntegerField(required=False, min_value=1, max_value=365)
    student_max_books = serializers.IntegerField(required=False, min_value=1, max_value=50)
    staff_max_books = serializers.IntegerField(required=False, min_value=1, max_value=50)
    max_renewals = serializers.IntegerField(required=False, min_value=0, max_value=20)
    fine_per_day = serializers.DecimalField(required=False, max_digits=8, decimal_places=2, min_value=0)

    def validate(self, attrs):
        unknown = sorted(set(self.initial_data) - set(LibrarySettings.EDITABLE_FIELDS))
        if unknown:
            raise serializers.ValidationError({"non_field_errors": [f"Unknown or read-only field(s): {', '.join(unknown)}."]})
        if not attrs:
            raise serializers.ValidationError({"non_field_errors": ["No fields supplied."]})
        return attrs

    def to_representation(self, instance):
        data = instance.editable_values()
        data["fine_per_day"] = f"{data['fine_per_day']:.2f}"
        data["is_default"] = instance._state.adding
        data["currency"] = getattr(django_settings, "LIBRARY_CURRENCY", "INR")
        return data
