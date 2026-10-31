from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Sum, Q

from core.dates import school_today, school_zone

from .models import Expense, ExpenseCategory, PaymentAccount, CashbookEntry

CASH_METHODS = ["cash"]
BANK_METHODS = ["bank_transfer", "upi", "cheque", "online"]


def _day_start(day):
    """The instant a school-calendar day begins. The server stores times in UTC, so filtering a created_at on
    its UTC date would put early-morning entries on the wrong day."""
    return datetime.combine(day, time.min, tzinfo=school_zone())


def _lock_numbering(prefix):
    """Serialises number generation per school and prefix until the surrounding transaction ends, so two
    requests cannot both read the same "last" number and collide on the unique constraint."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", [f"{connection.schema_name}:{prefix}"])


def _local_time(moment):
    return moment.astimezone(school_zone()).strftime("%I:%M %p")


def _account_receives_fees(account):
    """Fee money has no account of its own, so it is credited to one account per kind: the default (or
    oldest) cash account takes cash fees and the default (or oldest) bank account takes every other method.
    With two bank accounts, crediting both would count the same payment twice."""
    if account.account_type not in (PaymentAccount.AccountType.CASH, PaymentAccount.AccountType.BANK):
        return False
    chosen = (
        PaymentAccount.objects.filter(account_type=account.account_type)
        .order_by("-is_default", "created_at", "id")
        .first()
    )
    return chosen is not None and chosen.pk == account.pk


def _fee_payments_for(account, start, end):
    """Payment rows (completed receipts and their reversals) credited to this account in [start, end)."""
    from fees.models import Payment as FeePayment

    if not _account_receives_fees(account):
        return FeePayment.objects.none()
    qs = FeePayment.objects.filter(status__in=["completed", "reversed"])
    if start is not None:
        qs = qs.filter(created_at__gte=start)
    if end is not None:
        qs = qs.filter(created_at__lt=end)
    if account.account_type == PaymentAccount.AccountType.CASH:
        return qs.filter(method__in=CASH_METHODS)
    return qs.filter(method__in=BANK_METHODS)


def _net_fee_amount(qs):
    """Money in minus money reversed. A reversal is its own row (status "reversed") with a positive amount; the
    receipt it undoes stays "completed", so both rows must be counted."""
    total = Decimal("0.00")
    for row in qs.order_by().values("status").annotate(total=Sum("amount")):
        total += row["total"] if row["status"] == "completed" else -row["total"]
    return total


def generate_voucher_number(target_date=None):
    """
    Generate sequential voucher number: EXP-YYYY-XXXX
    Call it inside transaction.atomic(): the lock it takes is held until that transaction ends.
    """
    year = (target_date or school_today()).year
    prefix = f"EXP-{year}-"
    _lock_numbering(prefix)
    last = (
        Expense.objects.filter(voucher_number__startswith=prefix)
        .order_by("-voucher_number")
        .values_list("voucher_number", flat=True)
        .first()
    )
    if not last:
        seq = 1
    else:
        try:
            seq = int(last.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:04d}"


def generate_entry_number(entry_type, target_date=None):
    """
    Generate sequential cashbook entry number: INC-YYYY-XXXX or TRF-YYYY-XXXX
    """
    year = (target_date or school_today()).year
    prefix_code = "INC" if entry_type == CashbookEntry.EntryType.INCOME else "TRF"
    prefix = f"{prefix_code}-{year}-"
    _lock_numbering(prefix)
    last = (
        CashbookEntry.objects.filter(entry_number__startswith=prefix)
        .order_by("-entry_number")
        .values_list("entry_number", flat=True)
        .first()
    )
    if not last:
        seq = 1
    else:
        try:
            seq = int(last.split("-")[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    return f"{prefix}{seq:04d}"


def get_account_opening_balance(account, target_date):
    """
    Compute account balance at start of target_date:
    Opening Balance configured on account
    + prior fee payments (if applicable)
    + prior direct income/transfers in
    - prior approved expenses
    - prior transfers out
    """
    base_opening = account.opening_balance or Decimal("0.00")

    # 1. Prior Fees
    prior_fees_sum = Decimal("0.00")
    try:
        prior_fees_sum = _net_fee_amount(_fee_payments_for(account, None, _day_start(target_date)))
    except ImportError:
        pass

    # 2. Prior Direct Income / Transfers In
    prior_in_sum = (
        CashbookEntry.objects.filter(to_account=account, entry_date__lt=target_date).aggregate(
            total=Sum("amount")
        )["total"]
        or Decimal("0.00")
    )

    # 3. Prior Expenses from this account
    prior_exp_sum = (
        Expense.objects.filter(
            payment_account=account, status=Expense.Status.APPROVED, expense_date__lt=target_date
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    # 4. Prior Transfers Out from this account
    prior_trans_out_sum = (
        CashbookEntry.objects.filter(
            from_account=account, entry_type=CashbookEntry.EntryType.TRANSFER, entry_date__lt=target_date
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    return base_opening + prior_fees_sum + prior_in_sum - prior_exp_sum - prior_trans_out_sum


def get_day_book(target_date=None, account_id=None):
    """
    Calculate complete Day Book ledger for a given date and account.
    Returns opening, total inflows, total outflows, closing balance,
    and the chronological list of all ledger entries with running balance.
    """
    if target_date is None:
        target_date = school_today()
    elif isinstance(target_date, str):
        target_date = datetime.strptime(target_date, "%Y-%m-%d").date()

    if account_id:
        account = PaymentAccount.objects.filter(id=account_id).first()
    else:
        account = PaymentAccount.objects.filter(is_default=True).first() or PaymentAccount.objects.first()

    if not account:
        return {
            "date": target_date.isoformat(),
            "account": None,
            "opening_balance": "0.00",
            "total_inflow": "0.00",
            "total_outflow": "0.00",
            "closing_balance": "0.00",
            "entries": [],
        }

    opening_bal = get_account_opening_balance(account, target_date)

    entries = []

    # 1. Student Fee Collections today
    try:
        fee_qs = _fee_payments_for(
            account, _day_start(target_date), _day_start(target_date + timedelta(days=1))
        ).select_related("student", "student__profile")

        for fp in fee_qs.order_by("created_at"):
            reversed_row = fp.status == "reversed"
            student_name = ""
            if fp.student and hasattr(fp.student, "profile"):
                student_name = f"{fp.student.profile.first_name} {fp.student.profile.last_name}".strip()
            entries.append({
                "id": str(fp.id),
                "timestamp": fp.created_at.isoformat(),
                "time_str": _local_time(fp.created_at),
                "type": "fee_reversal" if reversed_row else "fee_income",
                "type_display": "Fee Receipt Reversed" if reversed_row else "Student Fee Collection",
                "reference": fp.receipt_number,
                "description": (
                    f"Fee {'reversed for' if reversed_row else 'received from'} {student_name} ({fp.student.enrollment_id})"
                    if student_name
                    else f"Fee receipt {fp.receipt_number}"
                ),
                "inflow": 0.0 if reversed_row else float(fp.amount),
                "outflow": float(fp.amount) if reversed_row else 0.0,
                "payment_method": fp.method,
            })
    except ImportError:
        pass

    # 2. Direct Income & Transfers In today
    in_entries = (
        CashbookEntry.objects.filter(to_account=account, entry_date=target_date)
        .select_related("from_account")
        .order_by("created_at")
    )
    for ce in in_entries:
        if ce.entry_type == CashbookEntry.EntryType.INCOME:
            desc = f"Direct Income: {ce.source_or_payee}"
            type_disp = "Direct Income"
        else:
            from_name = ce.from_account.name if ce.from_account else "Unknown"
            desc = f"Transfer from {from_name} ({ce.source_or_payee})"
            type_disp = "Transfer Received"

        entries.append({
            "id": str(ce.id),
            "timestamp": ce.created_at.isoformat(),
            "time_str": _local_time(ce.created_at),
            "type": ce.entry_type,
            "type_display": type_disp,
            "reference": ce.entry_number,
            "description": f"{desc} - {ce.description}".strip(" -"),
            "inflow": float(ce.amount),
            "outflow": 0.0,
            "payment_method": ce.payment_method,
        })

    # 3. Expenses today from this account
    exp_entries = (
        Expense.objects.filter(
            payment_account=account, status=Expense.Status.APPROVED, expense_date=target_date
        )
        .select_related("category")
        .order_by("created_at")
    )
    for exp in exp_entries:
        entries.append({
            "id": str(exp.id),
            "timestamp": exp.created_at.isoformat(),
            "time_str": _local_time(exp.created_at),
            "type": "expense",
            "type_display": f"Expense: {exp.category.name}",
            "reference": exp.voucher_number,
            "description": f"Paid to {exp.paid_to} - {exp.description}".strip(" -"),
            "inflow": 0.0,
            "outflow": float(exp.amount),
            "payment_method": exp.payment_method,
        })

    # 4. Transfers Out today from this account
    out_transfers = (
        CashbookEntry.objects.filter(
            from_account=account, entry_type=CashbookEntry.EntryType.TRANSFER, entry_date=target_date
        )
        .select_related("to_account")
        .order_by("created_at")
    )
    for ot in out_transfers:
        to_name = ot.to_account.name if ot.to_account else "Unknown"
        entries.append({
            "id": str(ot.id),
            "timestamp": ot.created_at.isoformat(),
            "time_str": _local_time(ot.created_at),
            "type": "transfer_out",
            "type_display": "Transfer Sent (Contra)",
            "reference": ot.entry_number,
            "description": f"Transferred to {to_name} ({ot.source_or_payee})",
            "inflow": 0.0,
            "outflow": float(ot.amount),
            "payment_method": ot.payment_method,
        })

    # Sort all entries by timestamp
    entries.sort(key=lambda x: x["timestamp"])

    running = float(opening_bal)
    for e in entries:
        running = running + e["inflow"] - e["outflow"]
        e["running_balance"] = round(running, 2)

    total_inflow = sum(e["inflow"] for e in entries)
    total_outflow = sum(e["outflow"] for e in entries)
    closing_bal = float(opening_bal) + total_inflow - total_outflow

    return {
        "date": target_date.isoformat(),
        "account": {
            "id": str(account.id),
            "name": account.name,
            "account_type": account.account_type,
            "bank_name": account.bank_name,
            "account_number": account.account_number,
        },
        "opening_balance": f"{opening_bal:.2f}",
        "total_inflow": f"{total_inflow:.2f}",
        "total_outflow": f"{total_outflow:.2f}",
        "closing_balance": f"{closing_bal:.2f}",
        "entries": entries,
    }


def get_income_vs_expense_summary(from_date=None, to_date=None):
    """
    Financial performance overview over a period:
    Income (Fee collections + Direct income)
    Expenses (Operating expenses by category + Payroll + Inventory)
    Net Surplus / Deficit
    Monthly trend breakdown.
    """
    today = school_today()
    if not to_date:
        to_date = today
    elif isinstance(to_date, str):
        to_date = datetime.strptime(to_date, "%Y-%m-%d").date()

    if not from_date:
        # Default to start of current month
        from_date = to_date.replace(day=1)
    elif isinstance(from_date, str):
        from_date = datetime.strptime(from_date, "%Y-%m-%d").date()

    # 1. Fee Collections
    fee_income_total = Decimal("0.00")
    fees_by_method = []
    try:
        from fees.models import Payment as FeePayment
        fee_qs = FeePayment.objects.filter(
            status__in=["completed", "reversed"],
            created_at__gte=_day_start(from_date),
            created_at__lt=_day_start(to_date + timedelta(days=1)),
        )
        net_by_method = {}
        for row in fee_qs.order_by().values("method", "status").annotate(total=Sum("amount")):
            signed = row["total"] if row["status"] == "completed" else -row["total"]
            net_by_method[row["method"]] = net_by_method.get(row["method"], Decimal("0.00")) + signed
        fee_income_total = sum(net_by_method.values(), Decimal("0.00"))
        for method, total in sorted(net_by_method.items(), key=lambda kv: -kv[1]):
            fees_by_method.append({"method": method, "total": f"{total:.2f}"})
    except ImportError:
        pass

    # 2. Direct Non-Fee Income
    direct_income_total = (
        CashbookEntry.objects.filter(
            entry_type=CashbookEntry.EntryType.INCOME,
            entry_date__gte=from_date,
            entry_date__lte=to_date,
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal("0.00")
    )

    total_income = fee_income_total + direct_income_total

    # 3. Operating Expenses by Category
    expense_qs = Expense.objects.filter(
        status=Expense.Status.APPROVED,
        expense_date__gte=from_date,
        expense_date__lte=to_date,
    )
    operating_expenses_total = expense_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0.00")

    category_breakdown = []
    cat_agg = (
        expense_qs.values("category__id", "category__name", "category__code")
        .annotate(total=Sum("amount"))
        .order_by("-total")
    )
    for cat in cat_agg:
        amt = cat["total"] or Decimal("0.00")
        pct = (amt / operating_expenses_total * 100) if operating_expenses_total > 0 else Decimal("0.00")
        category_breakdown.append({
            "category_id": str(cat["category__id"]),
            "category_name": cat["category__name"],
            "category_code": cat["category__code"],
            "amount": f"{amt:.2f}",
            "percentage": round(float(pct), 1),
        })

    # 4. Payroll Total (if present)
    payroll_total = Decimal("0.00")
    try:
        from payroll.models import Payslip
        p_res = Payslip.objects.filter(
            run__status__in=["approved", "paid"],
            run__period_end__gte=from_date,
            run__period_start__lte=to_date,
        ).aggregate(total=Sum("net_amount"))["total"]
        if p_res:
            payroll_total = p_res
    except ImportError:
        pass

    # 5. Inventory Purchases Total (if present)
    inventory_purchases_total = Decimal("0.00")
    try:
        from inventory.models import Purchase
        pur_qs = Purchase.objects.filter(
            status="received", purchase_date__gte=from_date, purchase_date__lte=to_date
        )
        pur_res = pur_qs.aggregate(total=Sum("total_cost"))["total"]
        if pur_res:
            inventory_purchases_total = pur_res
    except ImportError:
        pass

    total_expenses = operating_expenses_total + payroll_total + inventory_purchases_total
    net_surplus = total_income - total_expenses

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "total_income": f"{total_income:.2f}",
        "fee_income": f"{fee_income_total:.2f}",
        "direct_income": f"{direct_income_total:.2f}",
        "fees_by_method": fees_by_method,
        "total_expenses": f"{total_expenses:.2f}",
        "operating_expenses": f"{operating_expenses_total:.2f}",
        "payroll_expenses": f"{payroll_total:.2f}",
        "inventory_expenses": f"{inventory_purchases_total:.2f}",
        "net_surplus": f"{net_surplus:.2f}",
        "category_breakdown": category_breakdown,
    }

