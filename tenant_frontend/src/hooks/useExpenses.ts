import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";

export interface ExpenseCategory {
    id: string;
    name: string;
    code: string;
    description: string;
    is_active: boolean;
    sort_order: number;
    created_at?: string;
}

export interface PaymentAccount {
    id: string;
    name: string;
    account_type: "cash" | "bank" | "other";
    bank_name: string;
    account_number: string;
    ifsc_code: string;
    opening_balance: string;
    is_default: boolean;
    is_active: boolean;
    created_at?: string;
}

export interface Expense {
    id: string;
    voucher_number: string;
    category: string;
    category_name?: string;
    category_code?: string;
    payment_account?: string;
    payment_account_name?: string;
    amount: string;
    expense_date: string;
    payment_method: "cash" | "cheque" | "bank_transfer" | "upi" | "other";
    paid_to: string;
    reference_number: string;
    description: string;
    receipt_file?: string | null;
    status: "approved" | "draft" | "cancelled";
    cancelled_at?: string | null;
    cancellation_reason?: string;
    created_at: string;
}

export interface CashbookEntry {
    id: string;
    entry_number: string;
    entry_type: "income" | "transfer";
    amount: string;
    entry_date: string;
    from_account?: string;
    from_account_name?: string;
    to_account?: string;
    to_account_name?: string;
    source_or_payee: string;
    payment_method: string;
    reference_number: string;
    description: string;
    created_at: string;
}

export interface DayBookLedgerEntry {
    id: string;
    timestamp: string;
    time_str: string;
    type: string;
    type_display: string;
    reference: string;
    description: string;
    inflow: number;
    outflow: number;
    running_balance: number;
    payment_method: string;
}

export interface DayBookReport {
    date: string;
    account: {
        id: string;
        name: string;
        account_type: string;
        bank_name: string;
        account_number: string;
    } | null;
    opening_balance: string;
    total_inflow: string;
    total_outflow: string;
    closing_balance: string;
    entries: DayBookLedgerEntry[];
}

export interface CategoryBreakdown {
    category_id: string;
    category_name: string;
    category_code: string;
    amount: string;
    percentage: number;
}

export interface IncomeVsExpenseSummary {
    from_date: string;
    to_date: string;
    total_income: string;
    fee_income: string;
    direct_income: string;
    fees_by_method: Array<{ method: string; total: string }>;
    total_expenses: string;
    operating_expenses: string;
    payroll_expenses: string;
    inventory_expenses: string;
    net_surplus: string;
    category_breakdown: CategoryBreakdown[];
}

// -------------------------------------------------------------
// Hooks
// -------------------------------------------------------------

export function useExpenseCategories() {
    return useQuery<ExpenseCategory[]>({
        queryKey: ["expense-categories"],
        queryFn: async () => {
            const res = await axiosInstance.get("/expenses/categories/");
            return Array.isArray(res.data) ? res.data : (res.data.results || []);
        },
    });
}

export function usePaymentAccounts() {
    return useQuery<PaymentAccount[]>({
        queryKey: ["payment-accounts"],
        queryFn: async () => {
            const res = await axiosInstance.get("/expenses/accounts/");
            return Array.isArray(res.data) ? res.data : (res.data.results || []);
        },
    });
}

export function useExpenses(params?: {
    category?: string;
    payment_account?: string;
    payment_method?: string;
    status?: string;
    from_date?: string;
    to_date?: string;
    search?: string;
}) {
    return useQuery<Expense[]>({
        queryKey: ["expenses", params],
        queryFn: async () => {
            const res = await axiosInstance.get("/expenses/vouchers/", { params });
            return Array.isArray(res.data) ? res.data : (res.data.results || []);
        },
    });
}

export function useDayBook(date?: string, accountId?: string) {
    return useQuery<DayBookReport>({
        queryKey: ["day-book", date, accountId],
        queryFn: async () => {
            const res = await axiosInstance.get("/expenses/cashbook/day-book/", {
                params: { date, account_id: accountId },
            });
            return res.data;
        },
    });
}

export function useIncomeVsExpenseSummary(fromDate?: string, toDate?: string) {
    return useQuery<IncomeVsExpenseSummary>({
        queryKey: ["income-expense-summary", fromDate, toDate],
        queryFn: async () => {
            const res = await axiosInstance.get("/expenses/reports/summary/", {
                params: { from_date: fromDate, to_date: toDate },
            });
            return res.data;
        },
    });
}

export function useCreateExpense() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<Expense>) => {
            const res = await axiosInstance.post("/expenses/vouchers/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Expense voucher recorded successfully");
            qc.invalidateQueries({ queryKey: ["expenses"] });
            qc.invalidateQueries({ queryKey: ["day-book"] });
            qc.invalidateQueries({ queryKey: ["income-expense-summary"] });
        },
        onError: (err: any) => {
            const msg = err.response?.data?.detail || err.response?.data?.amount?.[0] || "Failed to record expense voucher";
            toast.error(msg);
        },
    });
}

export function useCancelExpense() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, reason }: { id: string; reason: string }) => {
            const res = await axiosInstance.post(`/expenses/vouchers/${id}/cancel/`, { reason });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Expense voucher cancelled");
            qc.invalidateQueries({ queryKey: ["expenses"] });
            qc.invalidateQueries({ queryKey: ["day-book"] });
            qc.invalidateQueries({ queryKey: ["income-expense-summary"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.detail || "Failed to cancel voucher");
        },
    });
}

export function useApproveExpense() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            const res = await axiosInstance.post(`/expenses/vouchers/${id}/approve/`);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Expense voucher approved");
            qc.invalidateQueries({ queryKey: ["expenses"] });
            qc.invalidateQueries({ queryKey: ["day-book"] });
            qc.invalidateQueries({ queryKey: ["income-expense-summary"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.detail || "Failed to approve voucher");
        },
    });
}

export function useCreateCashbookEntry() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<CashbookEntry>) => {
            const res = await axiosInstance.post("/expenses/cashbook/entries/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Cashbook entry saved successfully");
            qc.invalidateQueries({ queryKey: ["day-book"] });
            qc.invalidateQueries({ queryKey: ["income-expense-summary"] });
        },
        onError: (err: any) => {
            const msg = err.response?.data?.detail || err.response?.data?.to_account?.[0] || "Failed to record entry";
            toast.error(msg);
        },
    });
}

export function useCreateExpenseCategory() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: { name: string; code: string; description?: string }) => {
            const res = await axiosInstance.post("/expenses/categories/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Expense category created");
            qc.invalidateQueries({ queryKey: ["expense-categories"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.name?.[0] || "Failed to create category");
        },
    });
}

export function useCreatePaymentAccount() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<PaymentAccount>) => {
            const res = await axiosInstance.post("/expenses/accounts/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Payment account created");
            qc.invalidateQueries({ queryKey: ["payment-accounts"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.name?.[0] || "Failed to create account");
        },
    });
}
