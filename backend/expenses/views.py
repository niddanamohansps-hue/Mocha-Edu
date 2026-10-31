import csv
from datetime import date
from decimal import Decimal
import io

import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from roles.permissions import HasPermission
from .models import Expense, ExpenseCategory, PaymentAccount, CashbookEntry
from .serializers import (
    ExpenseCategorySerializer,
    PaymentAccountSerializer,
    ExpenseSerializer,
    ExpenseCancelSerializer,
    CashbookEntrySerializer,
)
from .services import get_day_book, get_income_vs_expense_summary


class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenseCategory.objects.all()
    serializer_param = ExpenseCategorySerializer
    serializer_class = ExpenseCategorySerializer

    def get_permissions(self):
        if self.request.method in ["GET", "HEAD", "OPTIONS"]:
            return [IsAuthenticated(), HasPermission("view_expenses")()]
        return [IsAuthenticated(), HasPermission("manage_expense_settings")()]


class PaymentAccountViewSet(viewsets.ModelViewSet):
    queryset = PaymentAccount.objects.all()
    serializer_class = PaymentAccountSerializer

    def get_permissions(self):
        if self.request.method in ["GET", "HEAD", "OPTIONS"]:
            return [IsAuthenticated(), HasPermission("view_expenses")()]
        return [IsAuthenticated(), HasPermission("manage_expense_settings")()]


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update"]:
            return [IsAuthenticated(), HasPermission("record_expenses")()]
        elif self.action in ["destroy", "cancel", "approve"]:
            return [IsAuthenticated(), HasPermission("approve_expenses")()]
        return [IsAuthenticated(), HasPermission("view_expenses")()]

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        """The scanned bill attached to this voucher, for anyone who may view expenses."""
        expense = self.get_object()
        if not expense.receipt_file:
            raise Http404("This voucher has no receipt.")
        filename = os.path.basename(expense.receipt_file.name)
        if getattr(settings, "USE_X_ACCEL_REDIRECT", False):
            response = HttpResponse()
            prefix = getattr(settings, "X_ACCEL_PREFIX", "/protected_media/").rstrip("/")
            response["X-Accel-Redirect"] = f"{prefix}/{expense.receipt_file.name}"
            response["Content-Disposition"] = f'inline; filename="{filename}"'
            return response
        try:
            return FileResponse(expense.receipt_file.open("rb"), filename=filename)
        except OSError:
            raise Http404("The receipt could not be read from storage.")

    def get_queryset(self):
        qs = Expense.objects.select_related("category", "payment_account").all()
        params = self.request.query_params

        category_id = params.get("category")
        if category_id:
            qs = qs.filter(category_id=category_id)

        account_id = params.get("payment_account")
        if account_id:
            qs = qs.filter(payment_account_id=account_id)

        payment_method = params.get("payment_method")
        if payment_method:
            qs = qs.filter(payment_method=payment_method)

        status_param = params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        from_date = params.get("from_date")
        if from_date:
            qs = qs.filter(expense_date__gte=from_date)

        to_date = params.get("to_date")
        if to_date:
            qs = qs.filter(expense_date__lte=to_date)

        search = params.get("search")
        if search:
            qs = qs.filter(
                models_search_q(search)
            )

        return qs

    def perform_destroy(self, instance):
        # Soft-cancel instead of hard delete to preserve financial audit trail
        instance.status = Expense.Status.CANCELLED
        instance.cancelled_at = timezone.now()
        instance.cancellation_reason = "Deleted by authorized user"
        instance.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        expense = self.get_object()
        if expense.status == Expense.Status.CANCELLED:
            return Response({"detail": "Expense is already cancelled."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = ExpenseCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        expense.status = Expense.Status.CANCELLED
        expense.cancelled_at = timezone.now()
        expense.cancellation_reason = serializer.validated_data["reason"]
        expense.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])

        return Response(ExpenseSerializer(expense).data)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        expense = self.get_object()
        if expense.status == Expense.Status.APPROVED:
            return Response({"detail": "Expense is already approved."}, status=status.HTTP_400_BAD_REQUEST)
        if expense.status == Expense.Status.CANCELLED:
            return Response({"detail": "Cancelled expenses cannot be approved."}, status=status.HTTP_400_BAD_REQUEST)

        expense.status = Expense.Status.APPROVED
        expense.approved_by_user_id = request.user.id if request.user else None
        expense.save(update_fields=["status", "approved_by_user_id", "updated_at"])

        return Response(ExpenseSerializer(expense).data)


def models_search_q(search):
    from django.db.models import Q
    return (
        Q(voucher_number__icontains=search)
        | Q(paid_to__icontains=search)
        | Q(reference_number__icontains=search)
        | Q(description__icontains=search)
    )


class CashbookEntryViewSet(viewsets.ModelViewSet):
    serializer_class = CashbookEntrySerializer

    def get_permissions(self):
        if self.action in ["create", "update", "partial_update", "destroy"]:
            return [IsAuthenticated(), HasPermission("record_expenses")()]
        return [IsAuthenticated(), HasPermission("view_expenses")()]

    def get_queryset(self):
        qs = CashbookEntry.objects.select_related("from_account", "to_account").all()
        params = self.request.query_params

        entry_type = params.get("entry_type")
        if entry_type:
            qs = qs.filter(entry_type=entry_type)

        from_date = params.get("from_date")
        if from_date:
            qs = qs.filter(entry_date__gte=from_date)

        to_date = params.get("to_date")
        if to_date:
            qs = qs.filter(entry_date__lte=to_date)

        return qs


class CashbookDayBookView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_expenses")()]

    def get(self, request):
        target_date = request.query_params.get("date")
        account_id = request.query_params.get("account_id")
        data = get_day_book(target_date, account_id)
        return Response(data)


class IncomeVsExpenseSummaryView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_expenses")()]

    def get(self, request):
        from_date = request.query_params.get("from_date")
        to_date = request.query_params.get("to_date")
        data = get_income_vs_expense_summary(from_date, to_date)
        return Response(data)


class ExpenseExportCsvView(APIView):
    def get_permissions(self):
        return [IsAuthenticated(), HasPermission("view_expenses")()]

    def get(self, request):
        expenses = Expense.objects.select_related("category", "payment_account").order_by("-expense_date")

        from_date = request.query_params.get("from_date")
        if from_date:
            expenses = expenses.filter(expense_date__gte=from_date)

        to_date = request.query_params.get("to_date")
        if to_date:
            expenses = expenses.filter(expense_date__lte=to_date)

        category_id = request.query_params.get("category")
        if category_id:
            expenses = expenses.filter(category_id=category_id)

        status_param = request.query_params.get("status")
        if status_param:
            expenses = expenses.filter(status=status_param)

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "VOUCHER_NO",
            "DATE_YYYY_MM_DD",
            "CATEGORY",
            "CATEGORY_CODE",
            "PAID_TO",
            "AMOUNT_INR",
            "PAYMENT_METHOD",
            "PAYMENT_ACCOUNT",
            "REFERENCE_NO",
            "STATUS",
            "DESCRIPTION",
            "CANCELLATION_REASON",
        ])

        for exp in expenses:
            writer.writerow([
                exp.voucher_number,
                exp.expense_date.isoformat(),
                exp.category.name if exp.category else "",
                exp.category.code if exp.category else "",
                exp.paid_to,
                f"{exp.amount:.2f}",
                exp.get_payment_method_display(),
                exp.payment_account.name if exp.payment_account else "",
                exp.reference_number or "",
                exp.status.capitalize(),
                exp.description or "",
                exp.cancellation_reason or "",
            ])

        response = HttpResponse(output.getvalue().encode("utf-8-sig"), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="school_expenses_export.csv"'
        return response

