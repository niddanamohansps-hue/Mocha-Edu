from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ExpenseCategoryViewSet,
    PaymentAccountViewSet,
    ExpenseViewSet,
    CashbookEntryViewSet,
    CashbookDayBookView,
    IncomeVsExpenseSummaryView,
    ExpenseExportCsvView,
)

router = DefaultRouter()
router.register(r"categories", ExpenseCategoryViewSet, basename="expense-categories")
router.register(r"accounts", PaymentAccountViewSet, basename="payment-accounts")
router.register(r"vouchers", ExpenseViewSet, basename="expenses")
router.register(r"cashbook/entries", CashbookEntryViewSet, basename="cashbook-entries")

urlpatterns = [
    path("cashbook/day-book/", CashbookDayBookView.as_view(), name="cashbook-day-book"),
    path("reports/summary/", IncomeVsExpenseSummaryView.as_view(), name="expense-income-summary"),
    path("reports/export/", ExpenseExportCsvView.as_view(), name="expense-export-csv"),
    path("", include(router.urls)),
]

