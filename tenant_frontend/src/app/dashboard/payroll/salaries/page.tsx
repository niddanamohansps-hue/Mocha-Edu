"use client";

import { useState, useMemo } from "react";
import {
    Coins,
    Plus,
    Search,
    X,
    Users,
    Calendar,
    ChevronRight,
    SlidersHorizontal,
    Banknote,
    FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import { SetSalaryDialog, StructureDialog } from "@/components/dashboard/payroll/SalaryDialogs";
import { formatDate } from "@/components/dashboard/payroll/shared";
import { useSalaries } from "@/hooks/usePayroll";
import { usePermissions } from "@/providers/PermissionProvider";
import { formatIndianCurrency } from "@/lib/currency";

const PAGE_SIZE = 20;

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name: string) {
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

function getInitials(name: string) {
    if (!name) return "ST";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
}

export default function SalariesPage() {
    const { can } = usePermissions();
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [setting, setSetting] = useState(false);
    const [viewing, setViewing] = useState<{ id: string; name: string } | null>(null);

    const { data, isLoading, isError, refetch } = useSalaries({ page, search });

    if (!can("view_payroll")) {
        return <ErrorState message="You do not have permission to view staff salaries." />;
    }

    const rows = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    // Metrics
    const metrics = useMemo(() => {
        const sumBasic = rows.reduce((acc, r) => acc + (parseFloat(r.basic_amount) || 0), 0);
        const avgBasic = rows.length > 0 ? sumBasic / rows.length : 0;
        return { totalCount, sumBasic, avgBasic };
    }, [rows, totalCount]);

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Coins className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Staff Salary Profiles & Structures</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Active employee basic monthly compensation, recurring allowances, statutory deductions, and net CTC breakdown
                    </p>
                </div>

                {can("manage_salary_structures") && (
                    <Button
                        onClick={() => setSetting(true)}
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Set Staff Salary</span>
                    </Button>
                )}
            </div>

            {/* 2. Executive 3-Card Operational Pulse Strip */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                {/* Configured Profiles */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Configured Salaries</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Users className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalCount}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">staff members</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Active employee pay schedules
                    </p>
                </div>

                {/* Monthly Base Outlay */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Monthly Basic Commitment</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <Banknote className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {formatIndianCurrency(metrics.sumBasic)}
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Excluding variable allowances & deductions
                    </p>
                </div>

                {/* Average Basic */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Average Base Pay</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Coins className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {formatIndianCurrency(metrics.avgBasic)}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">/ month</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Mean institutional basic salary
                    </p>
                </div>
            </div>

            {/* 3. Search Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex items-center justify-between gap-3">
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search employee by name or ID..."
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
            </div>

            {/* 4. Table */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load staff salaries. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyState
                    title={search ? "No staff members matched your query" : "No employee salaries configured yet"}
                    description={
                        search
                            ? "Try searching with a different employee name or ID."
                            : "Set up employee basic pay and salary structures before initiating monthly payroll calculations."
                    }
                    action={
                        !search && can("manage_salary_structures") ? (
                            <Button
                                onClick={() => setSetting(true)}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Set First Salary</span>
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
                                        Staff Member
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Basic Monthly Salary
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Effective Since
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Internal Notes
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Pay Structure
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {rows.map((r) => {
                                    const avatarStyle = getAvatarStyle(r.staff_name);
                                    const initials = getInitials(r.staff_name);

                                    return (
                                        <TableRow
                                            key={r.id}
                                            className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                        >
                                            {/* Staff Member with Avatar */}
                                            <TableCell className="py-3.5 pl-4">
                                                <div className="flex items-center gap-2.5">
                                                    <div
                                                        className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                    >
                                                        {initials}
                                                    </div>
                                                    <div>
                                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {r.staff_name}
                                                        </div>
                                                        <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                            {r.employee_id}
                                                        </code>
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Basic Monthly Salary */}
                                            <TableCell className="py-3.5">
                                                <span className="text-xs font-bold text-slate-900 dark:text-white">
                                                    {formatIndianCurrency(r.basic_amount)}
                                                </span>
                                                <span className="text-[10px] text-slate-400 block font-normal">
                                                    per month
                                                </span>
                                            </TableCell>

                                            {/* Effective Since */}
                                            <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-300 font-medium">
                                                {formatDate(r.effective_from)}
                                            </TableCell>

                                            {/* Notes */}
                                            <TableCell className="py-3.5 text-xs text-slate-500 max-w-xs truncate">
                                                {r.note || "—"}
                                            </TableCell>

                                            {/* Actions */}
                                            <TableCell className="py-3.5 pr-4 text-right">
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => setViewing({ id: r.staff, name: r.staff_name })}
                                                    className="h-8 px-2.5 text-xs font-semibold border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 hover:text-sky-600 cursor-pointer"
                                                >
                                                    <SlidersHorizontal className="w-3.5 h-3.5 mr-1 text-slate-400" />
                                                    <span>Pay Structure</span>
                                                </Button>
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

            {/* Dialogs */}
            <SetSalaryDialog open={setting} onClose={() => { setSetting(false); refetch(); }} />
            <StructureDialog staffId={viewing?.id ?? null} staffName={viewing?.name ?? ""} onClose={() => setViewing(null)} />
        </div>
    );
}
