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
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
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
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                            <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Opening Balance</div>
                            <div className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                                ₹{dayBook?.opening_balance || "0.00"}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">At start of day</div>
                        </div>
                        <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-emerald-100 dark:border-emerald-950/40 shadow-sm">
                            <div className="text-xs font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-1">
                                <ArrowDownRight className="h-3.5 w-3.5" /> Total Inflow (+)
                            </div>
                            <div className="text-2xl font-bold text-emerald-600 dark:text-emerald-400 mt-1">
                                +₹{dayBook?.total_inflow || "0.00"}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">Fees + Direct Income</div>
                        </div>
                        <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-rose-100 dark:border-rose-950/40 shadow-sm">
                            <div className="text-xs font-medium text-rose-600 dark:text-rose-400 flex items-center gap-1">
                                <ArrowUpRight className="h-3.5 w-3.5" /> Total Outflow (-)
                            </div>
                            <div className="text-2xl font-bold text-rose-600 dark:text-rose-400 mt-1">
                                -₹{dayBook?.total_outflow || "0.00"}
                            </div>
                            <div className="text-xs text-slate-400 mt-1">Petty Expenses + Transfers</div>
                        </div>
                        <div className="p-4 bg-indigo-50/50 dark:bg-indigo-950/20 rounded-xl border border-indigo-200 dark:border-indigo-800 shadow-sm">
                            <div className="text-xs font-medium text-indigo-700 dark:text-indigo-300">
                                Closing Cash in Hand
                            </div>
                            <div className="text-2xl font-bold text-indigo-700 dark:text-indigo-300 mt-1">
                                ₹{dayBook?.closing_balance || "0.00"}
                            </div>
                            <div className="text-xs text-indigo-500/80 mt-1">Drawer count at end of day</div>
                        </div>
                    </div>

                    {/* Day Book Ledger Table */}
                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-slate-50/75 dark:bg-slate-900/60">
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Time</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Type</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Voucher / Receipt #</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Particulars / Description</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Payment Mode</TableHead>
                                    <TableHead className="text-xs font-bold text-right text-emerald-600 dark:text-emerald-400">Inflow (₹)</TableHead>
                                    <TableHead className="text-xs font-bold text-right text-rose-600 dark:text-rose-400">Outflow (₹)</TableHead>
                                    <TableHead className="text-xs font-bold text-right text-slate-700 dark:text-slate-300">Running Balance</TableHead>
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
                                            <TableCell className="text-slate-500 whitespace-nowrap text-xs font-mono">
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
                                            <TableCell className="text-right font-semibold text-xs text-emerald-600 dark:text-emerald-400">
                                                {item.inflow > 0 ? `+₹${item.inflow.toFixed(2)}` : "—"}
                                            </TableCell>
                                            <TableCell className="text-right font-semibold text-xs text-rose-600 dark:text-rose-400">
                                                {item.outflow > 0 ? `-₹${item.outflow.toFixed(2)}` : "—"}
                                            </TableCell>
                                            <TableCell className="text-right font-mono font-bold text-xs text-slate-900 dark:text-slate-100">
                                                ₹{item.running_balance.toFixed(2)}
                                            </TableCell>
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
                    <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-slate-50 dark:bg-slate-900/50 rounded-xl border border-slate-200 dark:border-slate-800">
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="relative">
                                <Search className="h-4 w-4 absolute left-3 top-2.5 text-slate-400" />
                                <input
                                    type="text"
                                    placeholder="Search payee, voucher #..."
                                    value={voucherSearch}
                                    onChange={(e) => setVoucherSearch(e.target.value)}
                                    className="pl-9 pr-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-indigo-500 w-60"
                                />
                            </div>
                            <select
                                value={voucherCategory}
                                onChange={(e) => setVoucherCategory(e.target.value)}
                                className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-slate-100"
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
                                className="px-3 py-1.5 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-sm text-slate-900 dark:text-slate-100"
                            >
                                <option value="">All Statuses</option>
                                <option value="approved">Approved</option>
                                <option value="draft">Draft</option>
                                <option value="cancelled">Cancelled</option>
                            </select>
                        </div>
                        <div className="text-xs text-slate-500">
                            {vouchers.length} vouchers recorded
                        </div>
                    </div>

                    {/* Vouchers Table */}
                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-slate-50/75 dark:bg-slate-900/60">
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Voucher #</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Date</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Category</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Paid To (Beneficiary)</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Account / Mode</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Amount (₹)</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Status</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 text-right">Actions</TableHead>
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
                                            <TableCell className="font-bold text-xs text-slate-900 dark:text-slate-100 font-mono">
                                                ₹{parseFloat(v.amount).toFixed(2)}
                                            </TableCell>
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
                                            <TableCell className="text-right space-x-1.5">
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
                                            </TableCell>
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
            {isExpenseModalOpen && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                            Record Expense Voucher
                        </h2>
                        <form onSubmit={handleCreateExpense} className="space-y-3.5">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Category *
                                    </label>
                                    <select
                                        required
                                        value={expenseForm.category}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, category: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="">Select Category</option>
                                        {categories.map((c) => (
                                            <option key={c.id} value={c.id}>
                                                {c.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Account *
                                    </label>
                                    <select
                                        value={expenseForm.payment_account}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, payment_account: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="">Default Cash Counter</option>
                                        {accounts.map((a) => (
                                            <option key={a.id} value={a.id}>
                                                {a.name} ({a.account_type})
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Amount (₹) *
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        required
                                        placeholder="0.00"
                                        value={expenseForm.amount}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, amount: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                    </input>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Date *
                                    </label>
                                    <input
                                        type="date"
                                        required
                                        value={expenseForm.expense_date}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, expense_date: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                    Paid To (Beneficiary / Vendor) *
                                </label>
                                <input
                                    type="text"
                                    required
                                    placeholder="e.g. HP Petrol Pump, Local Electrician, Stationery Press"
                                    value={expenseForm.paid_to}
                                    onChange={(e) => setExpenseForm({ ...expenseForm, paid_to: e.target.value })}
                                    className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Payment Mode
                                    </label>
                                    <select
                                        value={expenseForm.payment_method}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, payment_method: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="cash">Cash</option>
                                        <option value="upi">UPI / QR</option>
                                        <option value="cheque">Cheque</option>
                                        <option value="bank_transfer">Bank Transfer / NEFT</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Bill / Ref Number
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="Invoice # or UTR"
                                        value={expenseForm.reference_number}
                                        onChange={(e) => setExpenseForm({ ...expenseForm, reference_number: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                    Description / Purpose
                                </label>
                                <textarea
                                    rows={2}
                                    placeholder="Details or item breakdown..."
                                    value={expenseForm.description}
                                    onChange={(e) => setExpenseForm({ ...expenseForm, description: e.target.value })}
                                    className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                />
                            </div>
                            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                                <button
                                    type="button"
                                    onClick={() => setIsExpenseModalOpen(false)}
                                    className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium"
                                >
                                    Save Voucher
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* MODAL 2: CASH ENTRY / TRANSFER */}
            {isCashEntryModalOpen && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                            Record Cash Entry or Contra Transfer
                        </h2>
                        <form onSubmit={handleCreateCashEntry} className="space-y-3.5">
                            <div>
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                    Entry Type *
                                </label>
                                <select
                                    value={cashEntryForm.entry_type}
                                    onChange={(e) => setCashEntryForm({ ...cashEntryForm, entry_type: e.target.value as any })}
                                    className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm font-semibold"
                                >
                                    <option value="income">Direct Income (Non-Fee: Prospectus, uniform sale, etc.)</option>
                                    <option value="transfer">Account Transfer / Contra (Cash to Bank or Bank to Cash)</option>
                                </select>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Amount (₹) *
                                    </label>
                                    <input
                                        type="number"
                                        step="0.01"
                                        required
                                        placeholder="0.00"
                                        value={cashEntryForm.amount}
                                        onChange={(e) => setCashEntryForm({ ...cashEntryForm, amount: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Date *
                                    </label>
                                    <input
                                        type="date"
                                        required
                                        value={cashEntryForm.entry_date}
                                        onChange={(e) => setCashEntryForm({ ...cashEntryForm, entry_date: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            {cashEntryForm.entry_type === "transfer" && (
                                <div className="grid grid-cols-2 gap-3">
                                    <div>
                                        <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                            From Account *
                                        </label>
                                        <select
                                            required
                                            value={cashEntryForm.from_account}
                                            onChange={(e) => setCashEntryForm({ ...cashEntryForm, from_account: e.target.value })}
                                            className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                        >
                                            <option value="">Select Source</option>
                                            {accounts.map((a) => (
                                                <option key={a.id} value={a.id}>
                                                    {a.name}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                    <div>
                                        <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                            To Account *
                                        </label>
                                        <select
                                            required
                                            value={cashEntryForm.to_account}
                                            onChange={(e) => setCashEntryForm({ ...cashEntryForm, to_account: e.target.value })}
                                            className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                        >
                                            <option value="">Select Destination</option>
                                            {accounts.map((a) => (
                                                <option key={a.id} value={a.id}>
                                                    {a.name}
                                                </option>
                                            ))}
                                        </select>
                                    </div>
                                </div>
                            )}
                            {cashEntryForm.entry_type === "income" && (
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Receiving Account *
                                    </label>
                                    <select
                                        required
                                        value={cashEntryForm.to_account}
                                        onChange={(e) => setCashEntryForm({ ...cashEntryForm, to_account: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="">Select Account</option>
                                        {accounts.map((a) => (
                                            <option key={a.id} value={a.id}>
                                                {a.name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            )}
                            <div>
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                    {cashEntryForm.entry_type === "income" ? "Income Source *" : "Payee / Slip Reference *"}
                                </label>
                                <input
                                    type="text"
                                    required
                                    placeholder={
                                        cashEntryForm.entry_type === "income"
                                            ? "e.g. Prospectus Sales, Scrap newspaper sale"
                                            : "e.g. SBI Bank Deposit Slip #450"
                                    }
                                    value={cashEntryForm.source_or_payee}
                                    onChange={(e) => setCashEntryForm({ ...cashEntryForm, source_or_payee: e.target.value })}
                                    className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                />
                            </div>
                            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                                <button
                                    type="button"
                                    onClick={() => setIsCashEntryModalOpen(false)}
                                    className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium"
                                >
                                    Save Entry
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* MODAL 3: CANCEL VOUCHER */}
            {isCancelModalOpen && voucherToCancel && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                            <XCircle className="h-5 w-5 text-rose-600" />
                            Cancel Voucher {voucherToCancel.voucher_number}
                        </h2>
                        <p className="text-sm text-slate-500">
                            Cancelling this voucher will reverse its deduction from the cashbook. Please enter a mandatory reason.
                        </p>
                        <div>
                            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                Cancellation Reason *
                            </label>
                            <input
                                type="text"
                                required
                                placeholder="e.g. Duplicate bill, incorrect amount, wrong category"
                                value={cancelReason}
                                onChange={(e) => setCancelReason(e.target.value)}
                                className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                            />
                        </div>
                        <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                            <button
                                type="button"
                                onClick={() => setIsCancelModalOpen(false)}
                                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                            >
                                Back
                            </button>
                            <button
                                type="button"
                                onClick={handleCancelVoucher}
                                className="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm font-medium"
                            >
                                Confirm Cancellation
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}

