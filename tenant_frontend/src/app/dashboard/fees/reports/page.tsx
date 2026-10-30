"use client";

import { useMemo, useState, Suspense } from "react";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import Link from "next/link";
import {
    TrendingDown,
    IndianRupee,
    Coins,
    Search,
    X,
    User,
    Users,
    Receipt,
    ArrowRight,
    AlertTriangle,
    Clock,
    FileSpreadsheet,
    Calendar,
    Send,
    CheckCircle2,
} from "lucide-react";
import { useOutstandingReport } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
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
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { formatIndianCurrency } from "@/lib/currency";

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name?: string | null) {
    if (!name || typeof name !== "string") return AVATAR_PALETTES[0];
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
    if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
}

function OutstandingReportContent() {
    const { can, isOwner } = usePermissions();
    const { selectedYear } = useAcademicYear();
    const canView = isOwner || can("view_financial_reports");

    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const academicYear = searchParams.get("academicYear") || selectedYear?.name || "";
    const [searchQuery, setSearchQuery] = useState("");

    const updateParams = (updates: Record<string, string | null>) => {
        const params = new URLSearchParams(searchParams.toString());
        for (const [key, value] of Object.entries(updates)) {
            if (value === null || value === "") {
                params.delete(key);
            } else {
                params.set(key, value);
            }
        }
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
    };

    const { data, isLoading, isError, refetch } = useOutstandingReport(academicYear);

    const totalOutstanding = parseFloat(data?.total_outstanding_amount ?? "0");
    const totalDefaultersCount = data?.count ?? 0;
    const avgOutstanding = totalDefaultersCount > 0 ? totalOutstanding / totalDefaultersCount : 0;

    // Filter results by student name or roll
    const filteredResults = useMemo(() => {
        if (!data?.results) return [];
        return data.results.filter((row: any) => {
            if (!searchQuery) return true;
            const q = searchQuery.toLowerCase();
            return (
                row.full_name?.toLowerCase().includes(q) ||
                row.enrollment_id?.toLowerCase().includes(q) ||
                row.fee_head?.toLowerCase().includes(q)
            );
        });
    }, [data?.results, searchQuery]);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-7 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <TrendingDown className="h-7 w-7 text-rose-600 dark:text-rose-400" />
                        <span>Student Fee Defaulters &amp; Overdue Dues</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Identify students with active outstanding balances, monitor unpaid fee heads, and trigger collections
                    </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                        asChild
                        variant="outline"
                        size="sm"
                        className="h-9 px-3 gap-1.5 text-xs font-semibold border-slate-200 dark:border-slate-800 cursor-pointer shadow-2xs"
                    >
                        <Link href="/dashboard/fees/structures">
                            <Receipt className="h-3.5 w-3.5 text-slate-500" />
                            <span>Fee Slabs Setup</span>
                        </Link>
                    </Button>
                    <Button
                        asChild
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                    >
                        <Link href="/dashboard/fees/collect">
                            <Coins className="h-3.5 w-3.5" />
                            <span>Cashier Collection Desk</span>
                        </Link>
                    </Button>
                </div>
            </div>

            {/* 2. Executive Financial Pulse Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-rose-200/70 dark:border-rose-900/60 p-5 shadow-2xs space-y-1">
                    <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider block">
                        Total Outstanding Dues
                    </span>
                    <div className="text-2xl font-black text-rose-700 dark:text-rose-300 mt-1">
                        {formatIndianCurrency(totalOutstanding)}
                    </div>
                    <span className="text-xs text-rose-600/80 dark:text-rose-400/80 font-medium">
                        Unpaid across all active heads
                    </span>
                </div>

                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Total Defaulters
                    </span>
                    <div className="text-2xl font-black text-slate-900 dark:text-white mt-1">
                        {totalDefaultersCount} Students
                    </div>
                    <span className="text-xs text-slate-400 font-medium">With active pending balances</span>
                </div>

                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-1">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                        Average Balance per Defaulter
                    </span>
                    <div className="text-2xl font-black text-slate-900 dark:text-white mt-1">
                        {formatIndianCurrency(avgOutstanding)}
                    </div>
                    <span className="text-xs text-slate-400 font-medium">Across active debtors</span>
                </div>
            </div>

            {/* 3. Search & Filter Bar */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-4 shadow-2xs flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                <div className="relative flex-1 max-w-sm">
                    <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <Input
                        placeholder="Search student by name, ID or fee type..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="h-9 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                    />
                    {searchQuery && (
                        <button
                            type="button"
                            onClick={() => setSearchQuery("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5"
                        >
                            <X className="w-3 h-3" />
                        </button>
                    )}
                </div>

                <div className="flex items-center gap-2 text-xs">
                    <span className="text-slate-400">Academic Year:</span>
                    <Badge
                        variant="outline"
                        className="bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 font-semibold"
                    >
                        {academicYear || "All sessions"}
                    </Badge>
                </div>
            </div>

            {/* 4. Table Desk View */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !data || data.results.length === 0 ? (
                <div className="p-12 rounded-2xl border border-emerald-200/60 dark:border-emerald-900/40 bg-emerald-50/30 dark:bg-emerald-950/10 text-center space-y-2">
                    <CheckCircle2 className="h-8 w-8 text-emerald-600 mx-auto" />
                    <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                        Zero Outstanding Dues for {academicYear}
                    </h3>
                    <p className="text-xs text-slate-500">
                        All student fees have been fully collected and settled. There are no active defaulters.
                    </p>
                </div>
            ) : (
                <div className="space-y-3">
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow>
                                    <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Student Candidate
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Enrollment ID
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Unpaid Fee Category
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider text-right">
                                        Outstanding Balance
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filteredResults.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={5} className="h-28 text-center text-xs text-slate-500">
                                            No defaulters match your search filter.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    filteredResults.map((row: any, i: number) => {
                                        const avatarStyle = getAvatarStyle(row.full_name);
                                        const initials = getInitials(row.full_name);

                                        return (
                                            <TableRow
                                                key={i}
                                                className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                            >
                                                {/* Student with Avatar */}
                                                <TableCell className="py-3 pl-4">
                                                    <div className="flex items-center gap-2.5">
                                                        <div
                                                            className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                        >
                                                            {initials}
                                                        </div>
                                                        <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {row.full_name}
                                                        </span>
                                                    </div>
                                                </TableCell>

                                                {/* Enrollment ID */}
                                                <TableCell className="py-3 font-mono text-xs text-slate-500">
                                                    {row.enrollment_id}
                                                </TableCell>

                                                {/* Fee Head */}
                                                <TableCell className="py-3">
                                                    <Badge
                                                        variant="outline"
                                                        className="text-xs font-medium bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-300"
                                                    >
                                                        {row.fee_head}
                                                    </Badge>
                                                </TableCell>

                                                {/* Outstanding Amount in INR */}
                                                <TableCell className="py-3 text-right">
                                                    <span className="font-bold text-xs text-rose-600 dark:text-rose-400">
                                                        {formatIndianCurrency(row.outstanding)}
                                                    </span>
                                                </TableCell>

                                                {/* Direct Action Link to Collect */}
                                                <TableCell className="py-3 pr-4 text-right">
                                                    <Button
                                                        asChild
                                                        size="sm"
                                                        className="h-8 px-3 text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white gap-1 rounded-lg"
                                                    >
                                                        <Link
                                                            href={`/dashboard/fees/collect?studentId=${row.student}&search=${encodeURIComponent(
                                                                row.enrollment_id
                                                            )}`}
                                                        >
                                                            <Coins className="w-3.5 h-3.5" />
                                                            <span>Collect</span>
                                                        </Link>
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })
                                )}
                            </TableBody>
                        </Table>
                    </TableShell>
                </div>
            )}
        </div>
    );
}

export default function OutstandingReportPage() {
    return (
        <Suspense fallback={<LoadingState className="py-20" />}>
            <OutstandingReportContent />
        </Suspense>
    );
}
