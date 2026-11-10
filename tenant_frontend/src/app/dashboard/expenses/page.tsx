"use client";

import React, { useState } from "react";
import {
    Wallet,
    Receipt,
    Calendar,
    ArrowDownRight,
    ArrowUpRight,
    Plus,
    Download,
    CheckCircle2,
    XCircle,
    Building2,
    Filter,
    Search,
    CreditCard,
    DollarSign,
    Layers,
    ChevronRight,
    AlertCircle,
    FileText,
} from "lucide-react";
import {
    useExpenses,
    useExpenseCategories,
    usePaymentAccounts,
    useDayBook,
    useIncomeVsExpenseSummary,
    useCreateExpense,
    useCancelExpense,
    useApproveExpense,
    useCreateCashbookEntry,
    useCreateExpenseCategory,
    useCreatePaymentAccount,
    Expense,
} from "@/hooks/useExpenses";
import { usePermissions } from "@/providers/PermissionProvider";
import { formatIndianCurrency } from "@/lib/currency";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
    Dialog,
    DialogContent,
    DialogBody,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { FormGrid, FormFieldWrapper } from "@/components/ui/form-layout";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeadNumeric,
    TableHeader,
    TableRow,
    TableCellNumeric,
    TableCellAction,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";

export default function ExpensesPage() {
    const { can } = usePermissions();

    const [activeTab, setActiveTab] = useState<"daybook" | "vouchers" | "analytics" | "setup">("daybook");

    // Day Book filters
    const [selectedDate, setSelectedDate] = useState<string>(new Date().toISOString().split("T")[0]);
    const [selectedAccount, setSelectedAccount] = useState<string>("");

    // Voucher filters
    const [voucherCategory, setVoucherCategory] = useState<string>("");
    const [voucherStatus, setVoucherStatus] = useState<string>("");
    const [voucherSearch, setVoucherSearch] = useState<string>("");

    // Analytics filters
    const [analyticsFrom, setAnalyticsFrom] = useState<string>(() => {
        const d = new Date();
        return new Date(d.getFullYear(), d.getMonth(), 1).toISOString().split("T")[0];
    });
    const [analyticsTo, setAnalyticsTo] = useState<string>(new Date().toISOString().split("T")[0]);

    // Modals
    const [isExpenseModalOpen, setIsExpenseModalOpen] = useState(false);
    const [isCashEntryModalOpen, setIsCashEntryModalOpen] = useState(false);
    const [isCancelModalOpen, setIsCancelModalOpen] = useState(false);
    const [voucherToCancel, setVoucherToCancel] = useState<Expense | null>(null);
    const [cancelReason, setCancelReason] = useState("");

    const [isCategoryModalOpen, setIsCategoryModalOpen] = useState(false);
    const [isAccountModalOpen, setIsAccountModalOpen] = useState(false);

    // Queries
    const { data: categories = [], isLoading: isLoadingCategories } = useExpenseCategories();
    const { data: accounts = [], isLoading: isLoadingAccounts } = usePaymentAccounts();

    const effectiveAccount = selectedAccount || (accounts.find((a) => a.is_default)?.id ?? accounts[0]?.id ?? "");

    const { data: dayBook, isLoading: isLoadingDayBook } = useDayBook(selectedDate, effectiveAccount);
    const { data: vouchers = [], isLoading: isLoadingVouchers } = useExpenses({
        category: voucherCategory || undefined,
        status: voucherStatus || undefined,
        search: voucherSearch || undefined,
    });
    const { data: analytics, isLoading: isLoadingAnalytics } = useIncomeVsExpenseSummary(analyticsFrom, analyticsTo);

    // Mutations
    const createExpense = useCreateExpense();
    const cancelExpense = useCancelExpense();
    const approveExpense = useApproveExpense();
    const createCashEntry = useCreateCashbookEntry();
    const createCategory = useCreateExpenseCategory();
    const createAccount = useCreatePaymentAccount();

    // Form states
    const [expenseForm, setExpenseForm] = useState({
        category: "",
        payment_account: "",
        amount: "",
        expense_date: new Date().toISOString().split("T")[0],
        payment_method: "cash",
        paid_to: "",
        reference_number: "",
        description: "",
        status: "approved",
    });

    const [cashEntryForm, setCashEntryForm] = useState({
        entry_type: "income" as "income" | "transfer",
        amount: "",
        entry_date: new Date().toISOString().split("T")[0],
        from_account: "",
        to_account: "",
        source_or_payee: "",
        payment_method: "cash",
        reference_number: "",
        description: "",
    });

    const [categoryForm, setCategoryForm] = useState({
        name: "",
        code: "",
        description: "",
    });

    const [accountForm, setAccountForm] = useState({
        name: "",
        account_type: "cash" as "cash" | "bank" | "other",
        bank_name: "",
        account_number: "",
        ifsc_code: "",
        opening_balance: "0.00",
        is_default: false,
    });

    const handleCreateExpense = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!expenseForm.category || !expenseForm.amount || !expenseForm.paid_to) return;
        await createExpense.mutateAsync({
            category: expenseForm.category,
            payment_account: expenseForm.payment_account || undefined,
            amount: expenseForm.amount,
            expense_date: expenseForm.expense_date,
            payment_method: expenseForm.payment_method as any,
            paid_to: expenseForm.paid_to,
            reference_number: expenseForm.reference_number,
            description: expenseForm.description,
            status: expenseForm.status as any,
        });
        setIsExpenseModalOpen(false);
        setExpenseForm({
            category: "",
            payment_account: "",
            amount: "",
            expense_date: new Date().toISOString().split("T")[0],
            payment_method: "cash",
            paid_to: "",
            reference_number: "",
            description: "",
            status: "approved",
        });
    };

    const handleCreateCashEntry = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!cashEntryForm.amount || !cashEntryForm.source_or_payee) return;
        await createCashEntry.mutateAsync({
            entry_type: cashEntryForm.entry_type,
            amount: cashEntryForm.amount,
            entry_date: cashEntryForm.entry_date,
            from_account: cashEntryForm.entry_type === "transfer" ? cashEntryForm.from_account : undefined,
            to_account: cashEntryForm.to_account || undefined,
            source_or_payee: cashEntryForm.source_or_payee,
            payment_method: cashEntryForm.payment_method,
            reference_number: cashEntryForm.reference_number,
            description: cashEntryForm.description,
        });
        setIsCashEntryModalOpen(false);
        setCashEntryForm({
            entry_type: "income",
            amount: "",
            entry_date: new Date().toISOString().split("T")[0],
            from_account: "",
            to_account: "",
            source_or_payee: "",
            payment_method: "cash",
            reference_number: "",
            description: "",
        });
    };

    const handleCancelVoucher = async () => {
        if (!voucherToCancel || !cancelReason.trim()) return;
        await cancelExpense.mutateAsync({ id: voucherToCancel.id, reason: cancelReason.trim() });
        setIsCancelModalOpen(false);
        setVoucherToCancel(null);
        setCancelReason("");
    };

    const handleCreateCategory = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!categoryForm.name.trim() || !categoryForm.code.trim()) return;
        await createCategory.mutateAsync({
            name: categoryForm.name.trim(),
            code: categoryForm.code.trim().toUpperCase(),
            description: categoryForm.description.trim() || undefined,
        });
        setIsCategoryModalOpen(false);
        setCategoryForm({ name: "", code: "", description: "" });
    };

    const handleCreateAccount = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!accountForm.name.trim()) return;
        await createAccount.mutateAsync({
            name: accountForm.name.trim(),
            account_type: accountForm.account_type,
            bank_name: accountForm.bank_name.trim() || undefined,
            account_number: accountForm.account_number.trim() || undefined,
            ifsc_code: accountForm.ifsc_code.trim() || undefined,
            opening_balance: accountForm.opening_balance || "0.00",
            is_default: accountForm.is_default,
        });
        setIsAccountModalOpen(false);
        setAccountForm({
            name: "",
            account_type: "cash",
            bank_name: "",
            account_number: "",
            ifsc_code: "",
            opening_balance: "0.00",
            is_default: false,
        });
    };

    const handleExportCsv = () => {
        window.open(
            `/api/expenses/reports/export/?from_date=${analyticsFrom}&to_date=${analyticsTo}`,
            "_blank"
        );
    };

    return (
        <div className="p-6 max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
                        <Wallet className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        Expenses & School Cashbook
                    </h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Daily cash drawer reconciliation, operational expense vouchers, and cost center reports.
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2.5">
                    {can("record_expenses") && (
                        <>
                            <button
                                onClick={() => setIsExpenseModalOpen(true)}
                                className="inline-flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors cursor-pointer"
                            >
                                <Plus className="h-4 w-4" />
                                Record Expense
                            </button>
                            <button
                                onClick={() => setIsCashEntryModalOpen(true)}
                                className="inline-flex items-center gap-1.5 px-4 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer"
                            >
                                <ArrowDownRight className="h-4 w-4 text-emerald-600" />
                                Cash Entry / Transfer
                            </button>
                        </>
                    )}
                    <button
                        onClick={handleExportCsv}
                        className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-sm font-medium rounded-lg transition-colors cursor-pointer"
                        title="Download CSV for CA / Auditor"
                    >
                        <Download className="h-4 w-4" />
                        Export
                    </button>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-slate-200 dark:border-slate-800 space-x-8">
                <button
                    onClick={() => setActiveTab("daybook")}
                    className={`pb-3 text-sm font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
                        activeTab === "daybook"
                            ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400"
                            : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    }`}
                >
                    <Calendar className="h-4 w-4" />
                    Daily Cashbook (Day Book)
                </button>
                <button
                    onClick={() => setActiveTab("vouchers")}
                    className={`pb-3 text-sm font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
                        activeTab === "vouchers"
                            ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400"
                            : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    }`}
                >
                    <Receipt className="h-4 w-4" />
                    Expense Vouchers
                </button>
                <button
                    onClick={() => setActiveTab("analytics")}
                    className={`pb-3 text-sm font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
                        activeTab === "analytics"
                            ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400"
                            : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    }`}
                >
                    <FileText className="h-4 w-4" />
                    Income vs. Expense
                </button>
                <button
                    onClick={() => setActiveTab("setup")}
                    className={`pb-3 text-sm font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
                        activeTab === "setup"
                            ? "border-indigo-600 text-indigo-600 dark:text-indigo-400 dark:border-indigo-400"
                            : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400 dark:hover:text-slate-200"
                    }`}
                >
                    <Layers className="h-4 w-4" />
                    Cost Centers & Accounts
                </button>
            </div>

            {/* TAB 1: DAILY CASHBOOK (DAY BOOK) */}
            {activeTab === "daybook" && (
                <div className="space-y-6">
                    {/* Filters Bar */}
                    <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800">
                        <div className="flex flex-wrap items-center gap-4">
                            <div className="flex items-center gap-2">
                                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Date:</label>
                                <input
                                    type="date"
                                    value={selectedDate}
                                    onChange={(e) => setSelectedDate(e.target.value)}
                                    className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                />
                            </div>
                            <div className="flex items-center gap-2">
                                <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Account:</label>
                                <select
                                    value={effectiveAccount}
                                    onChange={(e) => setSelectedAccount(e.target.value)}
                                    className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm font-medium text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                                >
                                    {accounts.map((acc) => (
                                        <option key={acc.id} value={acc.id}>
                                            {acc.name} ({acc.account_type.toUpperCase()})
                                        </option>
                                    ))}
                                </select>
                            </div>
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                            Showing ledger transactions for {selectedDate}
                        </div>
                    </div>

                    {/* Summary Balance Cards */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-2.5 sm:gap-4">
                        <div className="p-3 sm:p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                            <div className="text-[11px] sm:text-xs font-medium text-slate-500 dark:text-slate-400 truncate">Opening Balance</div>
                            <div className="text-lg sm:text-2xl font-bold text-slate-900 dark:text-slate-100 mt-0.5 sm:mt-1 truncate">
                                ₹{dayBook?.opening_balance || "0.00"}
                            </div>
                            <div className="text-[10px] sm:text-xs text-slate-400 mt-0.5 sm:mt-1 truncate">At start of day</div>
                        </div>
                        <div className="p-3 sm:p-4 bg-white dark:bg-slate-800 rounded-xl border border-emerald-100 dark:border-emerald-950/40 shadow-sm">
                            <div className="text-[11px] sm:text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1 truncate">
                                <ArrowDownRight className="h-3 w-3 sm:h-3.5 sm:w-3.5 shrink-0" /> Total Inflow (+)
                            </div>
                            <div className="text-lg sm:text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-0.5 sm:mt-1 truncate">
                                +₹{dayBook?.total_inflow || "0.00"}
                            </div>
                            <div className="text-[10px] sm:text-xs text-slate-400 mt-0.5 sm:mt-1 truncate">Fees + Direct Income</div>
                        </div>
                        <div className="p-3 sm:p-4 bg-white dark:bg-slate-800 rounded-xl border border-rose-100 dark:border-rose-950/40 shadow-sm">
                            <div className="text-[11px] sm:text-xs font-medium text-rose-600 dark:text-rose-400 flex items-center gap-1 truncate">
                                <ArrowUpRight className="h-3 w-3 sm:h-3.5 sm:w-3.5 shrink-0" /> Total Outflow (-)
                            </div>
                            <div className="text-lg sm:text-2xl font-bold text-rose-600 dark:text-rose-400 mt-0.5 sm:mt-1 truncate">
                                -₹{dayBook?.total_outflow || "0.00"}
                            </div>
                            <div className="text-[10px] sm:text-xs text-slate-400 mt-0.5 sm:mt-1 truncate">Petty Expenses + Transfers</div>
                        </div>
                        <div className="p-3 sm:p-4 bg-indigo-50/50 dark:bg-indigo-950/20 rounded-xl border border-indigo-200 dark:border-indigo-800 shadow-sm">
                            <div className="text-[11px] sm:text-xs font-medium text-indigo-700 dark:text-indigo-300 truncate">
                                Closing Cash in Hand
                            </div>
                            <div className="text-lg sm:text-2xl font-bold text-indigo-700 dark:text-indigo-300 mt-0.5 sm:mt-1 truncate">
                                ₹{dayBook?.closing_balance || "0.00"}
                            </div>
                            <div className="text-[10px] sm:text-xs text-indigo-500/80 mt-0.5 sm:mt-1 truncate">Drawer count at end of day</div>
                        </div>
                    </div>

                    {/* Day Book Ledger Table */}
                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="pl-4">Time</TableHead>
                                    <TableHead>Type</TableHead>
                                    <TableHead>Voucher / Receipt #</TableHead>
                                    <TableHead>Particulars / Description</TableHead>
                                    <TableHead>Payment Mode</TableHead>
                                    <TableHeadNumeric className="text-emerald-600 dark:text-emerald-400">Inflow (₹)</TableHeadNumeric>
                                    <TableHeadNumeric className="text-rose-600 dark:text-rose-400">Outflow (₹)</TableHeadNumeric>
                                    <TableHeadNumeric className="pr-4">Running Balance</TableHeadNumeric>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {isLoadingDayBook ? (
                                    <TableRow>
                                        <TableCell colSpan={8} className="py-12 text-center text-xs text-slate-400">
                                            Loading Day Book ledger...
                                        </TableCell>
                                    </TableRow>
                                ) : !dayBook?.entries || dayBook.entries.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={8} className="py-12 text-center text-xs text-slate-400">
                                            No financial movements recorded for this account on {selectedDate}.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    dayBook.entries.map((item, idx) => (
                                        <TableRow key={idx} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                            <TableCell className="text-slate-500 whitespace-nowrap text-xs font-mono pl-4">
                                                {item.time_str}
                                            </TableCell>
                                            <TableCell className="whitespace-nowrap">
                                                <Badge
                                                    className={
                                                        item.inflow > 0
                                                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300/80 text-[10px]"
                                                            : "bg-rose-50 text-rose-700 dark:bg-rose-950 dark:text-rose-300 border border-rose-300/80 text-[10px]"
                                                    }
                                                >
                                                    {item.type_display}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">
                                                {item.reference}
                                            </TableCell>
                                            <TableCell className="text-slate-900 dark:text-slate-100 font-medium text-xs max-w-md truncate">
                                                {item.description}
                                            </TableCell>
                                            <TableCell className="text-slate-500 text-xs uppercase font-mono">
                                                {item.payment_method}
                                            </TableCell>
                                            <TableCellNumeric className="text-emerald-600 dark:text-emerald-400 font-semibold">
                                                {item.inflow > 0 ? `+₹${item.inflow.toFixed(2)}` : "—"}
                                            </TableCellNumeric>
                                            <TableCellNumeric className="text-rose-600 dark:text-rose-400 font-semibold">
                                                {item.outflow > 0 ? `-₹${item.outflow.toFixed(2)}` : "—"}
                                            </TableCellNumeric>
                                            <TableCellNumeric className="pr-4 font-bold text-slate-900 dark:text-slate-100">
                                                ₹{item.running_balance.toFixed(2)}
                                            </TableCellNumeric>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </TableShell>
                </div>
            )}

            {/* TAB 2: EXPENSE VOUCHERS */}
            {activeTab === "vouchers" && (
                <div className="space-y-6">
                    {/* Filters */}
                    <div className="flex flex-wrap items-center justify-between gap-3 p-3.5 bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-2xs">
                        <div className="flex flex-wrap items-center gap-2.5">
                            <div className="relative">
                                <Search className="h-3.5 w-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                <Input
                                    type="search"
                                    placeholder="Search payee, voucher #..."
                                    value={voucherSearch}
                                    onChange={(e) => setVoucherSearch(e.target.value)}
                                    className="pl-8.5 h-9 text-xs w-60 rounded-xl border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                                />
                            </div>
                            <select
                                value={voucherCategory}
                                onChange={(e) => setVoucherCategory(e.target.value)}
                                className="h-9 px-3 text-xs font-medium bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-700 dark:text-slate-200 focus:outline-hidden focus:ring-1 focus:ring-sky-500"
                            >
                                <option value="">All Categories</option>
                                {categories.map((c) => (
                                    <option key={c.id} value={c.id}>
                                        {c.name}
                                    </option>
                                ))}
                            </select>
                            <select
                                value={voucherStatus}
                                onChange={(e) => setVoucherStatus(e.target.value)}
                                className="h-9 px-3 text-xs font-medium bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl text-slate-700 dark:text-slate-200 focus:outline-hidden focus:ring-1 focus:ring-sky-500"
                            >
                                <option value="">All Statuses</option>
                                <option value="approved">Approved</option>
                                <option value="draft">Draft</option>
                                <option value="cancelled">Cancelled</option>
                            </select>
                            {(voucherSearch || voucherCategory || voucherStatus) && (
                                <Button
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                        setVoucherSearch("");
                                        setVoucherCategory("");
                                        setVoucherStatus("");
                                    }}
                                    className="h-9 px-2 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-xl"
                                >
                                    Reset
                                </Button>
                            )}
                        </div>
                        <div className="text-xs text-slate-500 font-medium">
                            {vouchers.length} vouchers recorded
                        </div>
                    </div>

                    {/* Vouchers Table */}
                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow>
                                    <TableHead className="pl-4">Voucher #</TableHead>
                                    <TableHead>Date</TableHead>
                                    <TableHead>Category</TableHead>
                                    <TableHead>Paid To (Beneficiary)</TableHead>
                                    <TableHead>Account / Mode</TableHead>
                                    <TableHeadNumeric>Amount (₹)</TableHeadNumeric>
                                    <TableHead>Status</TableHead>
                                    <TableHead className="text-right pr-4">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {isLoadingVouchers ? (
                                    <TableRow>
                                        <TableCell colSpan={8} className="py-12 text-center text-xs text-slate-400">
                                            Loading expense vouchers...
                                        </TableCell>
                                    </TableRow>
                                ) : vouchers.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={8} className="py-12 text-center text-xs text-slate-400">
                                            No expense vouchers found matching the filter criteria.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    vouchers.map((v) => (
                                        <TableRow key={v.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                            <TableCell className="font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400">
                                                {v.voucher_number}
                                            </TableCell>
                                            <TableCell className="text-slate-600 dark:text-slate-300 whitespace-nowrap text-xs font-mono">
                                                {v.expense_date}
                                            </TableCell>
                                            <TableCell>
                                                <Badge variant="outline" className="text-[11px] font-semibold bg-slate-50 text-slate-700 border-slate-200">
                                                    {v.category_name}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-slate-900 dark:text-slate-100 font-medium text-xs">
                                                <div>{v.paid_to}</div>
                                                {v.description && (
                                                    <div className="text-[11px] text-slate-400 truncate max-w-xs mt-0.5">{v.description}</div>
                                                )}
                                            </TableCell>
                                            <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                                                <div>{v.payment_account_name || "Cash Counter"}</div>
                                                <span className="uppercase text-[10px] text-slate-400 font-mono">{v.payment_method}</span>
                                            </TableCell>
                                            <TableCellNumeric className="font-bold text-xs text-slate-900 dark:text-slate-100 font-mono">
                                                ₹{parseFloat(v.amount).toFixed(2)}
                                            </TableCellNumeric>
                                            <TableCell>
                                                <Badge
                                                    className={
                                                        v.status === "approved"
                                                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300/80 text-[10px]"
                                                            : v.status === "draft"
                                                            ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300 border border-amber-300/80 text-[10px]"
                                                            : "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 text-[10px] line-through"
                                                    }
                                                >
                                                    {v.status.toUpperCase()}
                                                </Badge>
                                            </TableCell>
                                            <TableCellAction className="pr-4 space-x-1.5">
                                                {v.status === "draft" && can("approve_expenses") && (
                                                    <Button
                                                        variant="outline"
                                                        size="sm"
                                                        onClick={() => approveExpense.mutate(v.id)}
                                                        className="h-8 px-2.5 text-xs text-emerald-600 hover:text-emerald-700 border-emerald-200 hover:bg-emerald-50 cursor-pointer font-semibold"
                                                    >
                                                        Approve
                                                    </Button>
                                                )}
                                                {v.status !== "cancelled" && can("approve_expenses") && (
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() => {
                                                            setVoucherToCancel(v);
                                                            setIsCancelModalOpen(true);
                                                        }}
                                                        className="h-8 px-2.5 text-xs text-rose-600 hover:text-rose-700 cursor-pointer font-semibold"
                                                    >
                                                        Cancel
                                                    </Button>
                                                )}
                                            </TableCellAction>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </TableShell>
                </div>
            )}

            {/* TAB 3: INCOME VS EXPENSE ANALYTICS */}
            {activeTab === "analytics" && (
                <div className="space-y-6">
                    {/* Period Selector */}
                    <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800">
                        <div className="flex items-center gap-3">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Period:</span>
                            <input
                                type="date"
                                value={analyticsFrom}
                                onChange={(e) => setAnalyticsFrom(e.target.value)}
                                className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                            />
                            <span className="text-slate-400">to</span>
                            <input
                                type="date"
                                value={analyticsTo}
                                onChange={(e) => setAnalyticsTo(e.target.value)}
                                className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                            />
                        </div>
                        <div className="text-xs text-slate-500">
                            Showing financial balance sheet from {analyticsFrom} to {analyticsTo}
                        </div>
                    </div>

                    {/* KPI Stats */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <div className="p-5 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Total Income Inflow
                            </div>
                            <div className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400 mt-2">
                                ₹{analytics?.total_income || "0.00"}
                            </div>
                            <div className="text-xs text-slate-400 mt-2 flex justify-between">
                                <span>Fee Collections: ₹{analytics?.fee_income || "0.00"}</span>
                                <span>Direct Income: ₹{analytics?.direct_income || "0.00"}</span>
                            </div>
                        </div>
                        <div className="p-5 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Total Expenses Outflow
                            </div>
                            <div className="text-3xl font-extrabold text-rose-600 dark:text-rose-400 mt-2">
                                ₹{analytics?.total_expenses || "0.00"}
                            </div>
                            <div className="text-xs text-slate-400 mt-2 flex justify-between">
                                <span>Operating: ₹{analytics?.operating_expenses || "0.00"}</span>
                                <span>Payroll: ₹{analytics?.payroll_expenses || "0.00"}</span>
                            </div>
                        </div>
                        <div className="p-5 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                Net Operating Surplus / Deficit
                            </div>
                            <div
                                className={`text-3xl font-extrabold mt-2 ${
                                    parseFloat(analytics?.net_surplus || "0") >= 0
                                        ? "text-indigo-600 dark:text-indigo-400"
                                        : "text-rose-600 dark:text-rose-400"
                                }`}
                            >
                                ₹{analytics?.net_surplus || "0.00"}
                            </div>
                            <div className="text-xs text-slate-400 mt-2">
                                {parseFloat(analytics?.net_surplus || "0") >= 0 ? "Operating Surplus" : "Operating Deficit"}
                            </div>
                        </div>
                    </div>

                    {/* Cost Center Breakdown */}
                    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-6 shadow-sm">
                        <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100 mb-4">
                            Operational Expenses by Cost Center
                        </h3>
                        {!analytics?.category_breakdown || analytics.category_breakdown.length === 0 ? (
                            <div className="py-8 text-center text-slate-400">
                                No approved expenses in this time period.
                            </div>
                        ) : (
                            <div className="space-y-4">
                                {analytics.category_breakdown.map((cat) => (
                                    <div key={cat.category_id} className="space-y-1.5">
                                        <div className="flex justify-between text-sm">
                                            <span className="font-medium text-slate-800 dark:text-slate-200">
                                                {cat.category_name} ({cat.category_code})
                                            </span>
                                            <span className="font-semibold text-slate-900 dark:text-slate-100">
                                                ₹{cat.amount} ({cat.percentage}%)
                                            </span>
                                        </div>
                                        <div className="w-full h-2.5 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-indigo-600 rounded-full"
                                                style={{ width: `${Math.min(cat.percentage, 100)}%` }}
                                            />
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {/* TAB 4: SETUP (COST CENTERS & ACCOUNTS) */}
            {activeTab === "setup" && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* Cost Centers / Categories */}
                    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 shadow-sm space-y-4">
                        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-700">
                            <div>
                                <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                                    Expense Categories (Cost Centers)
                                </h3>
                                <p className="text-xs text-slate-500">Categories used to group operational expenses</p>
                            </div>
                            {can("manage_expense_settings") && (
                                <button
                                    onClick={() => setIsCategoryModalOpen(true)}
                                    className="p-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 rounded-lg text-slate-700 dark:text-slate-200 text-xs font-medium cursor-pointer"
                                >
                                    <Plus className="h-4 w-4" />
                                </button>
                            )}
                        </div>
                        <div className="space-y-2">
                            {categories.map((c) => (
                                <div
                                    key={c.id}
                                    className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg flex items-center justify-between"
                                >
                                    <div>
                                        <div className="font-medium text-sm text-slate-900 dark:text-slate-100">
                                            {c.name}
                                        </div>
                                        <div className="text-xs text-slate-400">{c.description}</div>
                                    </div>
                                    <span className="font-mono text-xs px-2 py-0.5 bg-indigo-50 dark:bg-indigo-950/40 text-indigo-700 dark:text-indigo-400 rounded">
                                        {c.code}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* Payment Accounts */}
                    <div className="bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 p-5 shadow-sm space-y-4">
                        <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-700">
                            <div>
                                <h3 className="text-base font-semibold text-slate-900 dark:text-slate-100">
                                    Payment Accounts
                                </h3>
                                <p className="text-xs text-slate-500">Cash drawer and school bank accounts</p>
                            </div>
                            {can("manage_expense_settings") && (
                                <button
                                    onClick={() => setIsAccountModalOpen(true)}
                                    className="p-1.5 bg-slate-100 hover:bg-slate-200 dark:bg-slate-700 dark:hover:bg-slate-600 rounded-lg text-slate-700 dark:text-slate-200 text-xs font-medium cursor-pointer"
                                >
                                    <Plus className="h-4 w-4" />
                                </button>
                            )}
                        </div>
                        <div className="space-y-2">
                            {accounts.map((a) => (
                                <div
                                    key={a.id}
                                    className="p-3 bg-slate-50 dark:bg-slate-900/50 rounded-lg flex items-center justify-between"
                                >
                                    <div>
                                        <div className="font-medium text-sm text-slate-900 dark:text-slate-100 flex items-center gap-2">
                                            {a.name}
                                            {a.is_default && (
                                                <span className="text-[10px] px-1.5 py-0.2 bg-emerald-100 text-emerald-800 rounded">
                                                    Default
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-xs text-slate-400">
                                            {a.bank_name ? `${a.bank_name} - ${a.account_number}` : "Physical Counter Drawer"}
                                        </div>
                                    </div>
                                    <span className="text-xs font-semibold uppercase px-2 py-0.5 bg-slate-200 dark:bg-slate-700 rounded">
                                        {a.account_type}
                                    </span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL 1: RECORD EXPENSE */}
            <Dialog open={isExpenseModalOpen} onOpenChange={setIsExpenseModalOpen}>
                <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<Receipt className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />}
                        title="Record Expense Voucher"
                        subtitle="Create an official expense entry and link to account."
                        onClose={() => setIsExpenseModalOpen(false)}
                    />
                    <form onSubmit={handleCreateExpense} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormGrid>
                                <FormFieldWrapper label="Category" htmlFor="exp-category" required>
                                    <select
                                        id="exp-category"
                                        required
                                        value={expenseForm.category}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, category: e.target.value })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="">Select Category</option>
                                        {categories.map((c) => (
                                            <option key={c.id} value={c.id}>
                                                {c.name}
                                            </option>
                                        ))}
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Payment Account" htmlFor="exp-account">
                                    <select
                                        id="exp-account"
                                        value={expenseForm.payment_account}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, payment_account: e.target.value })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="">Default Cash Counter</option>
                                        {accounts.map((a) => (
                                            <option key={a.id} value={a.id}>
                                                {a.name} ({a.account_type})
                                            </option>
                                        ))}
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Amount (₹)" htmlFor="exp-amount" required>
                                    <Input
                                        id="exp-amount"
                                        type="number"
                                        step="0.01"
                                        required
                                        placeholder="0.00"
                                        value={expenseForm.amount}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, amount: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Date" htmlFor="exp-date" required>
                                    <Input
                                        id="exp-date"
                                        type="date"
                                        required
                                        value={expenseForm.expense_date}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, expense_date: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Paid To (Beneficiary / Vendor)" htmlFor="exp-paid-to" required colSpan={2}>
                                    <Input
                                        id="exp-paid-to"
                                        type="text"
                                        required
                                        placeholder="e.g. HP Petrol Pump, Local Electrician, Stationery Press"
                                        value={expenseForm.paid_to}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, paid_to: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Payment Mode" htmlFor="exp-mode">
                                    <select
                                        id="exp-mode"
                                        value={expenseForm.payment_method}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, payment_method: e.target.value })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="cash">Cash</option>
                                        <option value="upi">UPI / QR</option>
                                        <option value="cheque">Cheque</option>
                                        <option value="bank_transfer">Bank Transfer / NEFT</option>
                                        <option value="other">Other</option>
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Bill / Ref Number" htmlFor="exp-ref">
                                    <Input
                                        id="exp-ref"
                                        type="text"
                                        placeholder="Invoice # or UTR"
                                        value={expenseForm.reference_number}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, reference_number: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Description / Purpose" htmlFor="exp-desc" colSpan={2}>
                                    <Textarea
                                        id="exp-desc"
                                        rows={2}
                                        placeholder="Details or item breakdown..."
                                        value={expenseForm.description}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, description: e.target.value })}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsExpenseModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={createExpense.isPending}
                            >
                                {createExpense.isPending ? "Saving..." : "Save Voucher"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* MODAL 2: CASH ENTRY / TRANSFER */}
            <Dialog open={isCashEntryModalOpen} onOpenChange={setIsCashEntryModalOpen}>
                <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<ArrowDownRight className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />}
                        title="Record Cash Entry or Contra Transfer"
                        subtitle="Direct non-fee income or account-to-account funds transfer."
                        onClose={() => setIsCashEntryModalOpen(false)}
                    />
                    <form onSubmit={handleCreateCashEntry} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormGrid>
                                <FormFieldWrapper label="Entry Type" htmlFor="cash-entry-type" required colSpan={2}>
                                    <select
                                        id="cash-entry-type"
                                        value={cashEntryForm.entry_type}
                                        onChange={(e) => setCashEntryForm({ ...cashEntryForm, entry_type: e.target.value as any })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm font-semibold shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="income">Direct Income (Non-Fee: Prospectus, uniform sale, etc.)</option>
                                        <option value="transfer">Account Transfer / Contra (Cash to Bank or Bank to Cash)</option>
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Amount (₹)" htmlFor="cash-amount" required>
                                    <Input
                                        id="cash-amount"
                                        type="number"
                                        step="0.01"
                                        required
                                        placeholder="0.00"
                                        value={cashEntryForm.amount}
                                        onChange={(e) => setCashEntryForm({ ...cashEntryForm, amount: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Date" htmlFor="cash-date" required>
                                    <Input
                                        id="cash-date"
                                        type="date"
                                        required
                                        value={cashEntryForm.entry_date}
                                        onChange={(e) => setCashEntryForm({ ...cashEntryForm, entry_date: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                {cashEntryForm.entry_type === "transfer" && (
                                    <>
                                        <FormFieldWrapper label="From Account" htmlFor="cash-from" required>
                                            <select
                                                id="cash-from"
                                                required
                                                value={cashEntryForm.from_account}
                                                onChange={(e) => setCashEntryForm({ ...cashEntryForm, from_account: e.target.value })}
                                                className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                            >
                                                <option value="">Select Source</option>
                                                {accounts.map((a) => (
                                                    <option key={a.id} value={a.id}>
                                                        {a.name}
                                                    </option>
                                                ))}
                                            </select>
                                        </FormFieldWrapper>
                                        <FormFieldWrapper label="To Account" htmlFor="cash-to" required>
                                            <select
                                                id="cash-to"
                                                required
                                                value={cashEntryForm.to_account}
                                                onChange={(e) => setCashEntryForm({ ...cashEntryForm, to_account: e.target.value })}
                                                className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                            >
                                                <option value="">Select Destination</option>
                                                {accounts.map((a) => (
                                                    <option key={a.id} value={a.id}>
                                                        {a.name}
                                                    </option>
                                                ))}
                                            </select>
                                        </FormFieldWrapper>
                                    </>
                                )}
                                {cashEntryForm.entry_type === "income" && (
                                    <FormFieldWrapper label="Receiving Account" htmlFor="cash-recv-acct" required colSpan={2}>
                                        <select
                                            id="cash-recv-acct"
                                            required
                                            value={cashEntryForm.to_account}
                                            onChange={(e) => setCashEntryForm({ ...cashEntryForm, to_account: e.target.value })}
                                            className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                        >
                                            <option value="">Select Account</option>
                                            {accounts.map((a) => (
                                                <option key={a.id} value={a.id}>
                                                    {a.name}
                                                </option>
                                            ))}
                                        </select>
                                    </FormFieldWrapper>
                                )}
                                <FormFieldWrapper
                                    label={cashEntryForm.entry_type === "income" ? "Income Source" : "Payee / Slip Reference"}
                                    htmlFor="cash-source"
                                    required
                                    colSpan={2}
                                >
                                    <Input
                                        id="cash-source"
                                        type="text"
                                        required
                                        placeholder={
                                            cashEntryForm.entry_type === "income"
                                                ? "e.g. Prospectus Sales, Scrap newspaper sale"
                                                : "e.g. SBI Bank Deposit Slip #450"
                                        }
                                        value={cashEntryForm.source_or_payee}
                                        onChange={(e) => setCashEntryForm({ ...cashEntryForm, source_or_payee: e.target.value })}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsCashEntryModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={createCashEntry.isPending}
                            >
                                {createCashEntry.isPending ? "Saving..." : "Save Entry"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* MODAL 3: CANCEL VOUCHER */}
            <Dialog open={isCancelModalOpen && !!voucherToCancel} onOpenChange={setIsCancelModalOpen}>
                <DialogContent className="max-w-md max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<XCircle className="w-5 h-5 text-rose-600" />}
                        title={`Cancel Voucher ${voucherToCancel?.voucher_number || ""}`}
                        subtitle="Reverses cashbook deduction with an audit reason."
                        onClose={() => setIsCancelModalOpen(false)}
                    />
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                        <p className="text-xs text-slate-500">
                            Cancelling this voucher will reverse its deduction from the cashbook. Please enter a mandatory reason.
                        </p>
                        <FormFieldWrapper label="Cancellation Reason" htmlFor="cancel-reason" required>
                            <Input
                                id="cancel-reason"
                                type="text"
                                required
                                placeholder="e.g. Duplicate bill, incorrect amount, wrong category"
                                value={cancelReason}
                                onChange={(e) => setCancelReason(e.target.value)}
                            />
                        </FormFieldWrapper>
                    </DialogBody>
                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setIsCancelModalOpen(false)}
                        >
                            Back
                        </Button>
                        <Button
                            type="button"
                            variant="destructive"
                            onClick={handleCancelVoucher}
                            disabled={cancelExpense.isPending || !cancelReason.trim()}
                        >
                            {cancelExpense.isPending ? "Cancelling..." : "Confirm Cancellation"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* MODAL 4: ADD EXPENSE CATEGORY */}
            <Dialog open={isCategoryModalOpen} onOpenChange={setIsCategoryModalOpen}>
                <DialogContent className="max-w-md max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<Layers className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />}
                        title="Add Expense Category"
                        subtitle="Define a cost center category to group operational expenses."
                        onClose={() => setIsCategoryModalOpen(false)}
                    />
                    <form onSubmit={handleCreateCategory} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormFieldWrapper label="Category Name" htmlFor="cat-name" required>
                                <Input
                                    id="cat-name"
                                    type="text"
                                    required
                                    placeholder="e.g. Printing & Stationery"
                                    value={categoryForm.name}
                                    onChange={(e) => setCategoryForm({ ...categoryForm, name: e.target.value })}
                                />
                            </FormFieldWrapper>
                            <FormFieldWrapper label="Code" htmlFor="cat-code" required helpText="Short uppercase identifier">
                                <Input
                                    id="cat-code"
                                    type="text"
                                    required
                                    placeholder="e.g. STAT"
                                    value={categoryForm.code}
                                    onChange={(e) => setCategoryForm({ ...categoryForm, code: e.target.value })}
                                />
                            </FormFieldWrapper>
                            <FormFieldWrapper label="Description" htmlFor="cat-desc">
                                <Textarea
                                    id="cat-desc"
                                    rows={2}
                                    placeholder="Optional description of expenses covered..."
                                    value={categoryForm.description}
                                    onChange={(e) => setCategoryForm({ ...categoryForm, description: e.target.value })}
                                />
                            </FormFieldWrapper>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsCategoryModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={createCategory.isPending || !categoryForm.name.trim() || !categoryForm.code.trim()}
                            >
                                {createCategory.isPending ? "Creating..." : "Create Category"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* MODAL 5: ADD PAYMENT ACCOUNT */}
            <Dialog open={isAccountModalOpen} onOpenChange={setIsAccountModalOpen}>
                <DialogContent className="max-w-md max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<Building2 className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />}
                        title="Add Payment Account"
                        subtitle="Configure cash drawer or school bank ledger account."
                        onClose={() => setIsAccountModalOpen(false)}
                    />
                    <form onSubmit={handleCreateAccount} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormFieldWrapper label="Account Name" htmlFor="acct-name" required>
                                <Input
                                    id="acct-name"
                                    type="text"
                                    required
                                    placeholder="e.g. SBI Main Operations"
                                    value={accountForm.name}
                                    onChange={(e) => setAccountForm({ ...accountForm, name: e.target.value })}
                                />
                            </FormFieldWrapper>
                            <FormFieldWrapper label="Account Type" htmlFor="acct-type" required>
                                <select
                                    id="acct-type"
                                    value={accountForm.account_type}
                                    onChange={(e) => setAccountForm({ ...accountForm, account_type: e.target.value as any })}
                                    className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                >
                                    <option value="cash">Cash Drawer</option>
                                    <option value="bank">Bank Account</option>
                                    <option value="other">Other / Digital Wallet</option>
                                </select>
                            </FormFieldWrapper>
                            {accountForm.account_type === "bank" && (
                                <>
                                    <FormFieldWrapper label="Bank Name" htmlFor="acct-bank">
                                        <Input
                                            id="acct-bank"
                                            type="text"
                                            placeholder="e.g. State Bank of India"
                                            value={accountForm.bank_name}
                                            onChange={(e) => setAccountForm({ ...accountForm, bank_name: e.target.value })}
                                        />
                                    </FormFieldWrapper>
                                    <FormFieldWrapper label="Account Number" htmlFor="acct-num">
                                        <Input
                                            id="acct-num"
                                            type="text"
                                            placeholder="e.g. 1234567890"
                                            value={accountForm.account_number}
                                            onChange={(e) => setAccountForm({ ...accountForm, account_number: e.target.value })}
                                        />
                                    </FormFieldWrapper>
                                    <FormFieldWrapper label="IFSC Code" htmlFor="acct-ifsc">
                                        <Input
                                            id="acct-ifsc"
                                            type="text"
                                            placeholder="e.g. SBIN0001234"
                                            value={accountForm.ifsc_code}
                                            onChange={(e) => setAccountForm({ ...accountForm, ifsc_code: e.target.value })}
                                        />
                                    </FormFieldWrapper>
                                </>
                            )}
                            <FormFieldWrapper label="Opening Balance (₹)" htmlFor="acct-balance">
                                <Input
                                    id="acct-balance"
                                    type="number"
                                    step="0.01"
                                    placeholder="0.00"
                                    value={accountForm.opening_balance}
                                    onChange={(e) => setAccountForm({ ...accountForm, opening_balance: e.target.value })}
                                />
                            </FormFieldWrapper>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsAccountModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="submit"
                                disabled={createAccount.isPending || !accountForm.name.trim()}
                            >
                                {createAccount.isPending ? "Creating..." : "Create Account"}
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    );
}

