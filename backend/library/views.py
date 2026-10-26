from django.db import connection, transaction
from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.tenant_access import IsTenantMember
from core.audit import log_action
from core.dates import school_today
from core.pagination import StandardResultsPagination
from roles.permissions import HasPermission

from . import services
from .models import Book, BookCategory, BookCopy, Fine, LibrarySettings, Loan
from .serializers import (
    BookCategorySerializer,
    BookCopySerializer,
    BookSerializer,
    CloseInputSerializer,
    FineSerializer,
    IssueInputSerializer,
    LibrarySettingsSerializer,
    LoanSerializer,
    WaiveInputSerializer,
)

VIEW = "view_library"
MANAGE = "manage_library"
LEND = "lend_library_books"
FINES = "manage_library_fines"

BORROWER_SEARCH = [
    "student__enrollment_id", "student__profile__first_name", "student__profile__last_name",
    "staff__employee_id", "staff__profile__first_name", "staff__profile__last_name",
    "copy__accession_number", "copy__book__title",
]


class LibraryBaseViewSet(viewsets.GenericViewSet):
    """Nothing here is available without a library permission; a school's data never shows in another school
    (each school has its own schema)."""

    pagination_class = StandardResultsPagination
    READ_ACTIONS = ("list", "retrieve")
    WRITE_PERMISSION = MANAGE

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def get_permissions(self):
        permission = VIEW if self.action in self.READ_ACTIONS else self.WRITE_PERMISSION
        return [IsAuthenticated(), HasPermission(permission)]


class CrudViewSet(LibraryBaseViewSet, viewsets.ModelViewSet):
    audit_name = ""
    in_use_message = "This record is in use and cannot be deleted."

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, action=f"{self.audit_name}_created", model_name=type(obj).__name__, object_id=obj.pk)

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, action=f"{self.audit_name}_updated", model_name=type(obj).__name__, object_id=obj.pk)

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        model_name, pk = type(obj).__name__, obj.pk
        try:
            obj.delete()
        except ProtectedError:
            return Response({"error": self.in_use_message}, status=status.HTTP_409_CONFLICT)
        log_action(request, action=f"{self.audit_name}_deleted", model_name=model_name, object_id=pk)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BookCategoryViewSet(CrudViewSet):
    serializer_class = BookCategorySerializer
    queryset = BookCategory.objects.all()
    audit_name = "book_category"
    in_use_message = "Books use this category. Move them to another category first."
    pagination_class = None


class BookViewSet(CrudViewSet):
    serializer_class = BookSerializer
    queryset = Book.objects.select_related("category").prefetch_related("copies")
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["category", "is_active"]
    search_fields = ["title", "author", "isbn", "copies__accession_number"]
    audit_name = "book"
    in_use_message = "This book has copies in the catalogue and cannot be deleted. Switch it off instead."

    def get_queryset(self):
        queryset = super().get_queryset().distinct()
        if self.request.query_params.get("available") == "true":
            queryset = queryset.filter(copies__status=BookCopy.Status.AVAILABLE, is_active=True)
        return queryset


class BookCopyViewSet(CrudViewSet):
    serializer_class = BookCopySerializer
    queryset = BookCopy.objects.select_related("book").prefetch_related("loans__student__profile", "loans__staff__profile")
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["book", "status"]
    search_fields = ["accession_number", "book__title"]
    audit_name = "book_copy"
    in_use_message = "This copy has been lent out and cannot be deleted. Mark it withdrawn instead."

    def update(self, request, *args, **kwargs):
        """Edit a copy with its row locked, like lending does, so an edit made while the book is being lent
        cannot write "available" back over "issued"."""
        partial = kwargs.pop("partial", False)
        with transaction.atomic():
            copy = BookCopy.objects.select_for_update().get(pk=self.get_object().pk)
            serializer = self.get_serializer(copy, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
        return Response(self.get_serializer(self.get_queryset().get(pk=copy.pk)).data)


class LoanViewSet(LibraryBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Lend with POST; ``{id}/return/``, ``{id}/renew/`` and ``{id}/lost/`` close or extend a loan. Loans are
    never edited or deleted."""

    serializer_class = LoanSerializer
    WRITE_PERMISSION = LEND
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["student", "staff", "copy"]
    search_fields = BORROWER_SEARCH

    def get_queryset(self):
        queryset = Loan.objects.select_related("copy__book", "student__profile", "staff__profile")
        params = self.request.query_params
        if params.get("state") == "open":
            queryset = queryset.filter(returned_on__isnull=True)
        elif params.get("state") == "closed":
            queryset = queryset.filter(returned_on__isnull=False)
        elif params.get("state") == "overdue":
            queryset = queryset.filter(returned_on__isnull=True, due_on__lt=school_today())
        return queryset

    def create(self, request):
        serializer = IssueInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = services.issue_book(user_id=request.user.id, **serializer.validated_data)
        log_action(
            request, action="library_book_issued", model_name="Loan", object_id=loan.pk,
            changes={"copy": str(loan.copy_id), "student": str(loan.student_id) if loan.student_id else None,
                     "staff": str(loan.staff_id) if loan.staff_id else None, "due_on": loan.due_on.isoformat()},
        )
        return Response(LoanSerializer(self.get_queryset().get(pk=loan.pk)).data, status=status.HTTP_201_CREATED)

    def _closing_input(self, request):
        serializer = CloseInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data.get("date")

    @action(detail=True, methods=["post"], url_path="return")
    def return_book(self, request, pk=None):
        loan = self.get_object()
        loan, fine = services.return_book(loan=loan, returned_on=self._closing_input(request), user_id=request.user.id)
        log_action(
            request, action="library_book_returned", model_name="Loan", object_id=loan.pk,
            changes={"returned_on": loan.returned_on.isoformat(), "fine": str(fine.amount) if fine else None},
        )
        data = LoanSerializer(self.get_queryset().get(pk=loan.pk)).data
        data["fine"] = FineSerializer(fine).data if fine else None
        return Response(data)

    @action(detail=True, methods=["post"])
    def lost(self, request, pk=None):
        loan = self.get_object()
        loan, fine = services.report_lost(loan=loan, on=self._closing_input(request), user_id=request.user.id)
        log_action(
            request, action="library_book_lost", model_name="Loan", object_id=loan.pk,
            changes={"fine": str(fine.amount) if fine else None},
        )
        data = LoanSerializer(self.get_queryset().get(pk=loan.pk)).data
        data["fine"] = FineSerializer(fine).data if fine else None
        return Response(data)

    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        loan = services.renew(loan=self.get_object(), user_id=request.user.id)
        log_action(request, action="library_loan_renewed", model_name="Loan", object_id=loan.pk, changes={"due_on": loan.due_on.isoformat()})
        return Response(LoanSerializer(self.get_queryset().get(pk=loan.pk)).data)


class FineViewSet(LibraryBaseViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """Fines raised by late or lost books. ``bill`` puts a student's fine into Fees, ``collect`` records a
    staff member's payment, ``waive`` cancels it with a reason."""

    serializer_class = FineSerializer
    WRITE_PERMISSION = FINES
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ["status", "kind"]
    search_fields = [
        "loan__student__enrollment_id", "loan__student__profile__first_name", "loan__student__profile__last_name",
        "loan__staff__employee_id", "loan__staff__profile__first_name", "loan__staff__profile__last_name",
        "loan__copy__book__title",
    ]

    def get_queryset(self):
        return Fine.objects.select_related("loan__copy__book", "loan__student__profile", "loan__staff__profile")

    def _done(self, request, fine, action_name, changes=None):
        log_action(request, action=action_name, model_name="Fine", object_id=fine.pk, changes=changes)
        return Response(FineSerializer(self.get_queryset().get(pk=fine.pk)).data)

    @action(detail=True, methods=["post"])
    def bill(self, request, pk=None):
        fine = services.bill_fine(fine=self.get_object(), user_id=request.user.id)
        return self._done(request, fine, "library_fine_billed", {"student_fee": str(fine.student_fee_id), "amount": str(fine.amount)})

    @action(detail=True, methods=["post"])
    def collect(self, request, pk=None):
        fine = services.collect_fine(fine=self.get_object(), user_id=request.user.id)
        return self._done(request, fine, "library_fine_collected", {"amount": str(fine.amount)})

    @action(detail=True, methods=["post"])
    def waive(self, request, pk=None):
        serializer = WaiveInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fine = services.waive_fine(fine=self.get_object(), reason=serializer.validated_data["reason"], user_id=request.user.id)
        return self._done(request, fine, "library_fine_waived", {"amount": str(fine.amount), "reason": fine.waive_reason})


class LibrarySettingsView(APIView):
    """GET/PATCH /api/library/settings/. GET never writes (no row yet returns the defaults)."""

    http_method_names = ["get", "patch", "head", "options"]

    def initial(self, request, *args, **kwargs):
        if connection.schema_name == "public":
            raise NotFound()
        super().initial(request, *args, **kwargs)

    def get_permissions(self):
        permission = MANAGE if self.request.method == "PATCH" else VIEW
        return [IsAuthenticated(), IsTenantMember(), HasPermission(permission)]

    def get(self, request):
        return Response(LibrarySettingsSerializer(LibrarySettings.load()).data)

    def patch(self, request):
        serializer = LibrarySettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance, previous = LibrarySettings.update_singleton(user_id=request.user.id, **serializer.validated_data)
        log_action(request, action="library_settings_changed", model_name="LibrarySettings", object_id=instance.id,
                   changes={"old": {k: str(v) for k, v in previous.items()}, "new": {k: str(v) for k, v in instance.editable_values().items()}})
        return Response(LibrarySettingsSerializer(instance).data)


class LibrarySummaryView(APIView):
    """The numbers for the library home page."""

    def get_permissions(self):
        return [IsAuthenticated(), HasPermission(VIEW)]

    def get(self, request):
        if connection.schema_name == "public":
            raise NotFound()
        today = school_today()
        copies = BookCopy.objects.aggregate(
            total=Count("id", filter=~Q(status=BookCopy.Status.WITHDRAWN)),
            available=Count("id", filter=Q(status=BookCopy.Status.AVAILABLE)),
            issued=Count("id", filter=Q(status=BookCopy.Status.ISSUED)),
            lost=Count("id", filter=Q(status=BookCopy.Status.LOST)),
        )
        return Response({
            "titles": Book.objects.filter(is_active=True).count(),
            "copies": copies,
            "open_loans": Loan.objects.filter(returned_on__isnull=True).count(),
            "overdue_loans": Loan.objects.filter(returned_on__isnull=True, due_on__lt=today).count(),
            "pending_fines": Fine.objects.filter(status=Fine.Status.PENDING).count(),
        })
