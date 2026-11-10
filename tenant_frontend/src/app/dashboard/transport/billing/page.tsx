"use client";

import { useState } from "react";
import {
    Receipt,
    Calendar,
    Search,
    X,
    Users,
    Coins,
    CheckCircle2,
    AlertCircle,
    Bus,
    MapPin,
    ArrowRight,
    Loader2,
    Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { Pagination } from "@/components/ui/pagination";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { monthValue } from "@/components/dashboard/transport/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useBills, useRunBilling } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { BillRunResult } from "@/types/Transport";
import { formatIndianCurrency } from "@/lib/currency";

const PAGE_SIZE = 20;

function formatMonthLabel(monthStr: string) {
    try {
        const [year, month] = monthStr.split("-").map(Number);
        const date = new Date(year, month - 1, 1);
        return date.toLocaleDateString("en-US", { month: "long", year: "numeric" });
    } catch {
        return monthStr;
    }
}

export default function TransportBillingPage() {
    const { can } = usePermissions();
    const canBill = can("bill_transport");

    const [month, setMonth] = useState(() => monthValue());
    const [dueDate, setDueDate] = useState("");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");

    const [confirming, setConfirming] = useState(false);
    const [result, setResult] = useState<BillRunResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const run = useRunBilling();
    const { data, isLoading, isError, refetch } = useBills({ page, month, search });

    const bills = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    if (!can("view_transport")) {
        return <ErrorState message="You do not have permission to view transport." />;
    }

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Receipt className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Monthly Transport Billing Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Batch recurring transport fee generation, invoice synchronization, and monthly student fee schedules
                    </p>
                </div>

                <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs py-1 px-3">
                    Active Month: {formatMonthLabel(month)}
                </Badge>
            </div>

            {/* 2. Billing Batch Action Card */}
            {canBill && (
                <div className="p-5 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-4">
                    <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-slate-800">
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Sparkles className="w-4 h-4" />
                        </div>
                        <div>
                            <h3 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                Execute Monthly Transport Billing Run
                            </h3>
                            <p className="text-[11px] text-slate-400">
                                Invoices all active students with a bus seat for the chosen month. Safe to run repeatedly; duplicate records are automatically skipped.
                            </p>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-end">
                        <div className="space-y-1.5">
                            <Label htmlFor="bill-month" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                Billing Cycle Month <span className="text-rose-500">*</span>
                            </Label>
                            <Input
                                id="bill-month"
                                type="month"
                                value={month}
                                onChange={(e) => {
                                    setMonth(e.target.value);
                                    setResult(null);
                                    setPage(1);
                                }}
                                className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="bill-due" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                Invoice Payment Due Date <span className="text-slate-400 font-normal">(Optional)</span>
                            </Label>
                            <Input
                                id="bill-due"
                                type="date"
                                value={dueDate}
                                onChange={(e) => setDueDate(e.target.value)}
                                className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                            />
                        </div>

                        <div>
                            <Button
                                disabled={!month || run.isPending}
                                onClick={() => {
                                    setError(null);
                                    setConfirming(true);
                                }}
                                className="w-full gap-2"
                            >
                                {run.isPending ? (
                                    <>
                                        <Loader2 className="w-4 h-4 animate-spin" />
                                        <span>Executing Batch Run...</span>
                                    </>
                                ) : (
                                    <>
                                        <Coins className="w-4 h-4" />
                                        <span>Bill Month of {formatMonthLabel(month)}</span>
                                    </>
                                )}
                            </Button>
                        </div>
                    </div>

                    {error && (
                        <p role="alert" className="text-xs font-semibold text-rose-600 flex items-center gap-1.5 pt-1">
                            <AlertCircle className="w-3.5 h-3.5" />
                            <span>{error}</span>
                        </p>
                    )}
                </div>
            )}

            {/* 3. Result Banner (When Batch Ran) */}
            {result && (
                <div className="rounded-xl border border-emerald-300 dark:border-emerald-500/40 bg-emerald-50/80 dark:bg-emerald-950/30 p-4 space-y-2 shadow-2xs">
                    <div className="flex items-center gap-2 text-emerald-900 dark:text-emerald-300">
                        <CheckCircle2 className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                        <h4 className="text-xs font-bold uppercase tracking-wider">
                            Billing Run Completed Successfully
                        </h4>
                    </div>
                    <p className="text-xs font-semibold text-emerald-950 dark:text-emerald-200">
                        {result.billed === 0
                            ? "No new charges were generated (all active riders were previously invoiced for this month)."
                            : `Successfully invoiced ${result.billed} student${result.billed === 1 ? "" : "s"} for a total of ${formatIndianCurrency(result.total)}.`}
                    </p>
                    <div className="flex flex-wrap gap-4 text-[11px] text-slate-600 dark:text-slate-400 pt-1">
                        {result.already_billed > 0 && (
                            <span>• {result.already_billed} students were already billed and skipped</span>
                        )}
                        {result.no_fee > 0 && (
                            <span>• {result.no_fee} students assigned to free stops</span>
                        )}
                        {result.no_enrollment.length > 0 && (
                            <span className="text-amber-700 dark:text-amber-400 font-medium">
                                • Skipped {result.no_enrollment.length} students without active grade enrollment
                            </span>
                        )}
                    </div>
                </div>
            )}

            {/* 4. Filter Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search billed student by name or enrollment ID..."
                        value={search}
                        onChange={(e) => {
                            setSearch(e.target.value);
                            setPage(1);
                        }}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                    {search && (
                        <button
                            onClick={() => {
                                setSearch("");
                                setPage(1);
                            }}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                <div className="text-xs text-slate-500 dark:text-slate-400 shrink-0 font-medium">
                    Showing invoices for <span className="font-bold text-slate-800 dark:text-slate-200">{formatMonthLabel(month)}</span>
                </div>
            </div>

            {/* 5. Invoices Table */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load invoices. Please try again." onRetry={refetch} />
            ) : bills.length === 0 ? (
                <EmptyState
                    title="No invoices generated for this month yet"
                    description={
                        canBill
                            ? `Click "Bill Month of ${formatMonthLabel(month)}" above to generate transport fee lines for all active students.`
                            : "Contact an administrator to execute the monthly transport billing run."
                    }
                />
            ) : (
                <div className="space-y-4">
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Student Billed
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Route Name
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Designated Stop
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Billing Month
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Billed Amount
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {bills.map((b) => {
                                    return (
                                        <TableRow
                                            key={b.id}
                                            className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                        >
                                            {/* Student with Avatar */}
                                            <TableCell className="py-3.5 pl-4">
                                                <div className="flex items-center gap-2.5">
                                                    <Avatar name={b.student_name} size="sm" />
                                                    <div>
                                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {b.student_name}
                                                        </div>
                                                        <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                            {b.enrollment_id}
                                                        </code>
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Route */}
                                            <TableCell className="py-3.5">
                                                <div className="flex items-center gap-1.5 font-semibold text-xs text-slate-800 dark:text-slate-200">
                                                    <Bus className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400 shrink-0" />
                                                    <span>{b.route_name}</span>
                                                </div>
                                            </TableCell>

                                            {/* Stop */}
                                            <TableCell className="py-3.5">
                                                <div className="flex items-center gap-1 text-xs text-slate-700 dark:text-slate-300">
                                                    <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                                    <span className="font-medium">{b.stop_name || "Main Depot"}</span>
                                                </div>
                                            </TableCell>

                                            {/* Billing Month */}
                                            <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-300 font-medium">
                                                {formatMonthLabel(b.month)}
                                            </TableCell>

                                            {/* Billed Amount */}
                                            <TableCell className="py-3.5 pr-4 text-right">
                                                <span className="text-xs font-bold text-slate-900 dark:text-white">
                                                    {formatIndianCurrency(b.amount)}
                                                </span>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableShell>

                    {/* Pagination */}
                    {totalCount > PAGE_SIZE && (
                        <div className="pt-2">
                            <Pagination
                                page={page}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={setPage}
                            />
                        </div>
                    )}
                </div>
            )}

            {/* Confirmation Dialog */}
            <ConfirmationDialog
                open={confirming}
                onOpenChange={setConfirming}
                title={`Execute Transport Billing for ${formatMonthLabel(month)}?`}
                description="This generates monthly transport fee charges on student accounts for all active seat allocations. Students who have already been billed for this month will be skipped."
                confirmLabel="Yes, Execute Billing Run"
                isLoading={run.isPending}
                onConfirm={() =>
                    run.mutate(
                        { month, ...(dueDate ? { due_date: dueDate } : {}) },
                        {
                            onSuccess: (r) => {
                                setResult(r);
                                refetch();
                            },
                            onError: (e) => setError(inventoryErrorMessage(e, "Could not execute billing run")),
                            onSettled: () => setConfirming(false),
                        }
                    )
                }
            />
        </div>
    );
}
