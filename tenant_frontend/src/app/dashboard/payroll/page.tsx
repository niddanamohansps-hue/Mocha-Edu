"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
    Banknote,
    Plus,
    Calendar,
    Users,
    CreditCard,
    CheckCircle2,
    Clock,
    AlertCircle,
    ChevronRight,
    ArrowUpRight,
    FileSpreadsheet,
    FileText,
    ShieldCheck,
    Coins,
} from "lucide-react";
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
import { Pagination } from "@/components/ui/pagination";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import {
    Field,
    FormDialog,
    MONTHS,
    RunStatusBadge,
    SELECT_CLASS,
    formatDate,
    previousMonth,
} from "@/components/dashboard/payroll/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useCreateRun, useRuns } from "@/hooks/usePayroll";
import { usePermissions } from "@/providers/PermissionProvider";
import { RUN_STATUS_LABELS, RunStatus } from "@/types/Payroll";
import { formatIndianCurrency } from "@/lib/currency";

const PAGE_SIZE = 20;

function NewRunDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
    return open ? <NewRunForm onClose={onClose} /> : null;
}

function NewRunForm({ onClose }: { onClose: () => void }) {
    const start = previousMonth();
    const create = useCreateRun();
    const [year, setYear] = useState(String(start.year));
    const [month, setMonth] = useState(String(start.month));
    const [notes, setNotes] = useState("");
    const [error, setError] = useState<string | null>(null);

    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title="Start New Payroll Cycle"
            description="Select the payroll cycle month. The system calculates earnings, deductions, and unpaid leaves automatically before approval."
            submitLabel="Initialize Payroll"
            pending={create.isPending}
            error={error}
            onSubmit={() => {
                const y = Number(year);
                if (!Number.isInteger(y) || y < 2000 || y > 2200) return setError("Enter a valid calendar year.");
                setError(null);
                create.mutate(
                    { year: y, month: Number(month), notes: notes.trim() },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not start the payroll")) }
                );
            }}
        >
            <div className="grid grid-cols-2 gap-3.5">
                <Field label="Payroll Month" htmlFor="run-month">
                    <select
                        id="run-month"
                        className="w-full h-9.5 text-xs rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 font-medium"
                        value={month}
                        onChange={(e) => setMonth(e.target.value)}
                    >
                        {MONTHS.map((name, index) => (
                            <option key={name} value={index + 1}>{name}</option>
                        ))}
                    </select>
                </Field>
                <Field label="Payroll Year" htmlFor="run-year">
                    <Input
                        id="run-year"
                        inputMode="numeric"
                        value={year}
                        onChange={(e) => setYear(e.target.value)}
                        className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                    />
                </Field>
            </div>
            <div className="pt-2">
                <Field label="Cycle Reference Note (optional)" htmlFor="run-notes">
                    <Input
                        id="run-notes"
                        placeholder="e.g. Regular monthly faculty & staff disbursement"
                        value={notes}
                        maxLength={255}
                        onChange={(e) => setNotes(e.target.value)}
                        className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                    />
                </Field>
            </div>
        </FormDialog>
    );
}

export default function PayrollRunsPage() {
    const { can } = usePermissions();
    const [page, setPage] = useState(1);
    const [status, setStatus] = useState<RunStatus | "">("");
    const [creating, setCreating] = useState(false);

    const { data, isLoading, isError, refetch } = useRuns({ page, status });

    if (!can("view_payroll")) {
        return <ErrorState message="You do not have permission to view payroll. You can still see your own payslips under My Payslips." />;
    }

    const runs = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    // Metrics
    const metrics = useMemo(() => {
        const totalRuns = totalCount;
        const sumNet = runs.reduce((sum, r) => sum + (parseFloat(r.total_net) || 0), 0);
        const sumGross = runs.reduce((sum, r) => sum + (parseFloat(r.total_gross) || 0), 0);
        const pendingCount = runs.filter((r) => r.status === "calculated" || r.status === "approved").length;
        return { totalRuns, sumNet, sumGross, pendingCount };
    }, [runs, totalCount]);

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Banknote className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Institutional Payroll Runs & Disbursements</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Monthly salary calculation cycles, attendance-linked deductions, multi-stage approvals, and disbursement registers
                    </p>
                </div>

                {can("run_payroll") && (
                    <Button
                        onClick={() => setCreating(true)}
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Start Payroll Run</span>
                    </Button>
                )}
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Runs */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Payroll Cycles</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Calendar className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalRuns}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">recorded cycles</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Institutional salary batches
                    </p>
                </div>

                {/* Net Outlay */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Net Disbursed</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <Coins className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {formatIndianCurrency(metrics.sumNet)}
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Net salary transferred to staff
                    </p>
                </div>

                {/* Gross Billed */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Gross Compensation</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Banknote className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {formatIndianCurrency(metrics.sumGross)}
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Total basic & allowances
                    </p>
                </div>

                {/* Pending Actions */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Pending Cycles</span>
                        <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                            <Clock className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.pendingCount}
                        </span>
                        <span className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold">
                            in review
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Calculated or awaiting payment
                    </p>
                </div>
            </div>

            {/* 3. Status Funnel Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex items-center gap-1.5 overflow-x-auto scrollbar-none">
                {[
                    { value: "", label: "All Payrolls" },
                    { value: "calculated", label: "Awaiting Approval" },
                    { value: "approved", label: "Approved for Payment" },
                    { value: "paid", label: "Paid & Disbursed" },
                    { value: "draft", label: "Draft Cycles" },
                    { value: "cancelled", label: "Cancelled" },
                ].map((opt) => (
                    <button
                        key={opt.value}
                        type="button"
                        onClick={() => {
                            setStatus(opt.value as RunStatus | "");
                            setPage(1);
                        }}
                        className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                            status === opt.value
                                ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                        }`}
                    >
                        {opt.label}
                    </button>
                ))}
            </div>

            {/* 4. Runs Table */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load payroll runs. Please try again." onRetry={refetch} />
            ) : runs.length === 0 ? (
                <EmptyState
                    title={status ? "No payrolls in this state" : "No payroll cycles configured yet"}
                    description={
                        status
                            ? "Try choosing a different status filter."
                            : "Before running payroll, ensure employee salary structures are active and staff attendance/leaves are verified."
                    }
                    action={
                        !status && can("run_payroll") ? (
                            <Button
                                onClick={() => setCreating(true)}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Start First Payroll</span>
                            </Button>
                        ) : undefined
                    }
                />
            ) : (
                <div className="space-y-4">
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Pay Cycle
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Staff Count
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Gross Pay
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Deductions
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Net Payable
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Cycle Status
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {runs.map((r) => (
                                    <TableRow
                                        key={r.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        {/* Pay Cycle */}
                                        <TableCell className="py-3.5 pl-4">
                                            <div className="font-bold text-xs text-slate-900 dark:text-white">
                                                {r.month_label} {r.year}
                                            </div>
                                            <div className="text-[10px] text-slate-400 mt-0.5">
                                                {formatDate(r.period_start)} → {formatDate(r.period_end)}
                                            </div>
                                            {r.notes && (
                                                <div className="text-[10px] text-slate-500 italic mt-0.5 max-w-xs truncate">
                                                    {r.notes}
                                                </div>
                                            )}
                                        </TableCell>

                                        {/* Staff Invoiced */}
                                        <TableCell className="py-3.5">
                                            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 text-xs font-semibold">
                                                <Users className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
                                                <span>{r.payslip_count} Payslips</span>
                                            </div>
                                        </TableCell>

                                        {/* Gross Pay */}
                                        <TableCell className="py-3.5 text-xs font-semibold text-slate-700 dark:text-slate-300">
                                            {formatIndianCurrency(r.total_gross)}
                                        </TableCell>

                                        {/* Deductions */}
                                        <TableCell className="py-3.5 text-xs text-rose-600 dark:text-rose-400 font-semibold">
                                            -{formatIndianCurrency(r.total_deductions)}
                                        </TableCell>

                                        {/* Net Payable */}
                                        <TableCell className="py-3.5">
                                            <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                                {formatIndianCurrency(r.total_net)}
                                            </span>
                                        </TableCell>

                                        {/* Status */}
                                        <TableCell className="py-3.5">
                                            <RunStatusBadge status={r.status} />
                                        </TableCell>

                                        {/* Actions */}
                                        <TableCell className="py-3.5 pr-4 text-right">
                                            <Link href={`/dashboard/payroll/runs/${r.id}`}>
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="h-8 px-2.5 text-xs text-sky-600 hover:text-sky-700 hover:bg-sky-50 dark:hover:bg-sky-950/40 rounded-lg cursor-pointer"
                                                >
                                                    <span>Open Cycle</span>
                                                    <ChevronRight className="w-3.5 h-3.5 ml-1" />
                                                </Button>
                                            </Link>
                                        </TableCell>
                                    </TableRow>
                                ))}
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

            {/* Dialogs */}
            <NewRunDialog open={creating} onClose={() => { setCreating(false); refetch(); }} />
        </div>
    );
}
