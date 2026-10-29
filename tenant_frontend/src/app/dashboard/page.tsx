"use client";

import React from "react";
import Link from "next/link";
import { useMe } from "@/hooks/useAuth";
import { useDashboardSummary } from "@/hooks/useDashboard";
import { usePermissions } from "@/providers/PermissionProvider";
import { useApproverInbox } from "@/hooks/useStaffLeaves";
import { useExpenses } from "@/hooks/useExpenses";
import { formatIndianCurrency } from "@/lib/currency";
import {
    Users,
    GraduationCap,
    Activity,
    Wallet,
    ArrowUpRight,
    AlertCircle,
    CheckCircle2,
    Calendar,
    Clock,
    CreditCard,
    CheckSquare,
    UserPlus,
    CalendarCheck2,
    Megaphone,
    ShieldAlert,
    Layers,
    ChevronRight,
    FileText,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/feedback/ErrorState";

const ACTION_LABELS: Record<string, { label: string; color: string }> = {
    promoted: { label: "Promoted", color: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-200" },
    retained: { label: "Retained", color: "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-200" },
    transferred: { label: "Transferred", color: "bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border-sky-200" },
    withdrawn: { label: "Withdrawn", color: "bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-200" },
    graduated: { label: "Graduated", color: "bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-200" },
    reversed: { label: "Reversed", color: "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-slate-300" },
};

export default function DashboardOverview() {
    const { data: user } = useMe();
    const { can, isOwner } = usePermissions();
    const canViewSummary = isOwner || can("view_dashboard");
    const canManageLeaves = isOwner || can("manage_staff_leaves");
    const canManageExpenses = isOwner || can("view_expense") || can("add_expense");

    const { data: summary, isLoading, isError, refetch } = useDashboardSummary();

    // Query pending approvals safely only if user has permissions
    const { data: pendingLeavesData } = useApproverInbox({ status: "pending" });
    const { data: draftExpensesData } = useExpenses({ status: "draft" });

    const pendingLeavesCount = canManageLeaves ? (pendingLeavesData?.count ?? pendingLeavesData?.results?.length ?? 0) : 0;
    const pendingExpensesCount = canManageExpenses ? (draftExpensesData?.length ?? 0) : 0;

    // Time-based greeting
    const getGreeting = () => {
        const hour = new Date().getHours();
        if (hour < 12) return "Good morning";
        if (hour < 17) return "Good afternoon";
        return "Good evening";
    };

    const formattedDate = new Intl.DateTimeFormat("en-US", {
        weekday: "long",
        month: "short",
        day: "numeric",
        year: "numeric",
    }).format(new Date());

    const hasAttendanceMarked =
        summary?.attendance.today_percentage !== null &&
        summary?.attendance.today_percentage !== undefined;

    const pendingAttentionTotal =
        (hasAttendanceMarked ? 0 : 1) +
        (pendingLeavesCount > 0 ? 1 : 0) +
        (pendingExpensesCount > 0 ? 1 : 0);

    return (
        <div className="space-y-6 animate-in fade-in slide-in-from-bottom-2 duration-500">
            {/* 1. Compact Morning Executive Briefing Strip */}
            <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-sky-700 via-teal-700 to-emerald-800 p-6 md:p-8 text-white shadow-lg shadow-sky-950/10">
                <div className="absolute inset-0 bg-[radial-gradient(#fff_1px,transparent_1px)] [background-size:16px_16px] opacity-10 pointer-events-none" />
                <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div className="space-y-1">
                        <div className="flex items-center gap-2 text-xs font-semibold tracking-wider uppercase text-sky-200">
                            <Calendar className="h-3.5 w-3.5" />
                            <span>{formattedDate}</span>
                            <span>•</span>
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-200 border border-emerald-400/30 text-[10px]">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                Operations Live
                            </span>
                        </div>
                        <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">
                            {getGreeting()}, <span className="text-sky-200">{user?.profile?.first_name || "Administrator"}</span>
                        </h1>
                        <p className="text-sky-100/90 text-sm max-w-xl font-normal">
                            Here is the live operational summary and executive pulse for your institution today.
                        </p>
                    </div>

                    {/* Quick Right Pills */}
                    <div className="flex flex-wrap items-center gap-3">
                        {summary && summary.notifications.unread > 0 && (
                            <Link
                                href="/dashboard/notifications"
                                className="flex items-center gap-2 bg-white/10 hover:bg-white/20 border border-white/20 rounded-xl px-3.5 py-2 backdrop-blur-md transition-all text-xs font-semibold text-white cursor-pointer"
                            >
                                <Megaphone className="h-4 w-4 text-amber-300" />
                                <span>{summary.notifications.unread} Unread Alerts</span>
                            </Link>
                        )}
                        <Link
                            href="/dashboard/attendance/mark"
                            className="flex items-center gap-2 bg-white text-sky-900 hover:bg-sky-50 rounded-xl px-4 py-2 font-semibold text-xs transition shadow-sm cursor-pointer"
                        >
                            <CheckSquare className="h-3.5 w-3.5 text-sky-600" />
                            <span>Mark Roll Call</span>
                        </Link>
                    </div>
                </div>
            </div>

            {!canViewSummary ? (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-10 text-center text-slate-500">
                    Use the sidebar navigation to access the operational modules assigned to your role.
                </div>
            ) : isError ? (
                <ErrorState message="Failed to load dashboard summary. Please try again later." onRetry={refetch} />
            ) : (
                <>
                    {/* 2. Executive Metric Cards (4 Grid) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 md:gap-5">
                        {/* Metric 1: Active Students */}
                        <Card className="border border-slate-200/80 dark:border-slate-800 shadow-xs hover:shadow-md transition-all group bg-white dark:bg-slate-900">
                            <CardContent className="p-5 flex flex-col justify-between h-full">
                                <div className="flex items-start justify-between">
                                    <span className="text-xs font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400">
                                        Active Students
                                    </span>
                                    <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 group-hover:scale-105 transition-transform">
                                        <Users className="h-5 w-5" />
                                    </div>
                                </div>
                                <div className="mt-2">
                                    {isLoading ? (
                                        <Skeleton className="h-8 w-24" />
                                    ) : (
                                        <div className="flex items-baseline gap-2">
                                            <p className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">
                                                {summary?.students.active ?? 0}
                                            </p>
                                        </div>
                                    )}
                                </div>
                                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                    <span className="text-slate-500 dark:text-slate-400">
                                        {summary?.students.total ?? 0} total enrolled
                                    </span>
                                    <Link
                                        href="/dashboard/students"
                                        className="inline-flex items-center gap-0.5 text-sky-600 dark:text-sky-400 font-semibold hover:underline"
                                    >
                                        Directory <ArrowUpRight className="h-3 w-3" />
                                    </Link>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Metric 2: Active Faculty & Staff */}
                        <Card className="border border-slate-200/80 dark:border-slate-800 shadow-xs hover:shadow-md transition-all group bg-white dark:bg-slate-900">
                            <CardContent className="p-5 flex flex-col justify-between h-full">
                                <div className="flex items-start justify-between">
                                    <span className="text-xs font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400">
                                        Active Faculty & Staff
                                    </span>
                                    <div className="p-2.5 rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400 group-hover:scale-105 transition-transform">
                                        <GraduationCap className="h-5 w-5" />
                                    </div>
                                </div>
                                <div className="mt-2">
                                    {isLoading ? (
                                        <Skeleton className="h-8 w-20" />
                                    ) : (
                                        <p className="text-3xl font-black text-slate-900 dark:text-white tracking-tight">
                                            {summary?.staff.active ?? 0}
                                        </p>
                                    )}
                                </div>
                                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                    <span className="text-slate-500 dark:text-slate-400">
                                        Teaching & Non-teaching
                                    </span>
                                    <Link
                                        href="/dashboard/staff"
                                        className="inline-flex items-center gap-0.5 text-teal-600 dark:text-teal-400 font-semibold hover:underline"
                                    >
                                        Roster <ArrowUpRight className="h-3 w-3" />
                                    </Link>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Metric 3: Today's Attendance */}
                        <Card className="border border-slate-200/80 dark:border-slate-800 shadow-xs hover:shadow-md transition-all group bg-white dark:bg-slate-900">
                            <CardContent className="p-5 flex flex-col justify-between h-full">
                                <div className="flex items-start justify-between">
                                    <span className="text-xs font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400">
                                        Today&apos;s Attendance
                                    </span>
                                    <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 group-hover:scale-105 transition-transform">
                                        <Activity className="h-5 w-5" />
                                    </div>
                                </div>
                                <div className="mt-2">
                                    {isLoading ? (
                                        <Skeleton className="h-8 w-24" />
                                    ) : hasAttendanceMarked ? (
                                        <div className="flex items-baseline gap-2">
                                            <p className="text-3xl font-black text-emerald-600 dark:text-emerald-400 tracking-tight">
                                                {summary?.attendance.today_percentage}%
                                            </p>
                                            <span className="text-xs font-bold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 px-2 py-0.5 rounded-md">
                                                Recorded
                                            </span>
                                        </div>
                                    ) : (
                                        <div className="flex items-baseline gap-2">
                                            <p className="text-2xl font-bold text-amber-600 dark:text-amber-400 tracking-tight">
                                                Not Recorded
                                            </p>
                                        </div>
                                    )}
                                </div>
                                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                    <span className="text-slate-500 dark:text-slate-400 truncate">
                                        {hasAttendanceMarked ? "Daily roll call logged" : "Roll call pending today"}
                                    </span>
                                    <Link
                                        href="/dashboard/attendance/mark"
                                        className="inline-flex items-center gap-0.5 text-indigo-600 dark:text-indigo-400 font-semibold hover:underline shrink-0"
                                    >
                                        {hasAttendanceMarked ? "Details" : "Mark Now"} <ArrowUpRight className="h-3 w-3" />
                                    </Link>
                                </div>
                            </CardContent>
                        </Card>

                        {/* Metric 4: Outstanding Fees with Indian Currency Format */}
                        <Card className="border border-slate-200/80 dark:border-slate-800 shadow-xs hover:shadow-md transition-all group bg-white dark:bg-slate-900">
                            <CardContent className="p-5 flex flex-col justify-between h-full">
                                <div className="flex items-start justify-between">
                                    <span className="text-xs font-bold tracking-wider uppercase text-slate-500 dark:text-slate-400">
                                        Outstanding Fees
                                    </span>
                                    <div className="p-2.5 rounded-xl bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 group-hover:scale-105 transition-transform">
                                        <Wallet className="h-5 w-5" />
                                    </div>
                                </div>
                                <div className="mt-2">
                                    {isLoading || !summary ? (
                                        <Skeleton className="h-8 w-28" />
                                    ) : (
                                        <div className="space-y-0.5">
                                            <p
                                                className="text-3xl font-black text-slate-900 dark:text-white tracking-tight"
                                                title={formatIndianCurrency(summary.fees.outstanding)}
                                            >
                                                {formatIndianCurrency(summary.fees.outstanding, { compact: true })}
                                            </p>
                                            <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                                                Exact: {formatIndianCurrency(summary.fees.outstanding)}
                                            </p>
                                        </div>
                                    )}
                                </div>
                                <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                    <span className="text-slate-500 dark:text-slate-400">Pending collections</span>
                                    <Link
                                        href="/dashboard/fees"
                                        className="inline-flex items-center gap-0.5 text-rose-600 dark:text-rose-400 font-semibold hover:underline"
                                    >
                                        Fees Desk <ArrowUpRight className="h-3 w-3" />
                                    </Link>
                                </div>
                            </CardContent>
                        </Card>
                    </div>

                    {/* 3. Action Center: Items Requiring Immediate Attention */}
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-xs">
                        <div className="flex items-center justify-between mb-4">
                            <div className="flex items-center gap-2.5">
                                <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                                    <AlertCircle className="h-4 w-4" />
                                </div>
                                <div>
                                    <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                                        Executive Action Center
                                    </h2>
                                    <p className="text-xs text-slate-500 dark:text-slate-400">
                                        Approvals, daily operations, and workflows requiring attention
                                    </p>
                                </div>
                            </div>
                            <span className="text-xs font-semibold px-2.5 py-1 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                                {pendingAttentionTotal} {pendingAttentionTotal === 1 ? "Item" : "Items"}
                            </span>
                        </div>

                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                            {/* Attention Item 1: Attendance */}
                            {!hasAttendanceMarked ? (
                                <Link
                                    href="/dashboard/attendance/mark"
                                    className="flex items-center justify-between p-3.5 rounded-xl border border-amber-200/80 bg-amber-50/50 dark:bg-amber-950/20 dark:border-amber-800/60 hover:bg-amber-100/60 transition group cursor-pointer"
                                >
                                    <div className="flex items-center gap-3">
                                        <Clock className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
                                        <div>
                                            <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                                Student Attendance Pending
                                            </p>
                                            <p className="text-[11px] text-slate-600 dark:text-slate-400">
                                                Today&apos;s roll call is not completed
                                            </p>
                                        </div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-amber-600 group-hover:translate-x-0.5 transition-transform" />
                                </Link>
                            ) : (
                                <div className="flex items-center justify-between p-3.5 rounded-xl border border-emerald-200/80 bg-emerald-50/40 dark:bg-emerald-950/20 dark:border-emerald-800/60">
                                    <div className="flex items-center gap-3">
                                        <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                        <div>
                                            <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                                Attendance Logged
                                            </p>
                                            <p className="text-[11px] text-slate-600 dark:text-slate-400">
                                                {summary?.attendance.today_percentage}% overall attendance recorded
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Attention Item 2: Staff Leave Approvals */}
                            {pendingLeavesCount > 0 ? (
                                <Link
                                    href="/dashboard/staff/leaves"
                                    className="flex items-center justify-between p-3.5 rounded-xl border border-rose-200/80 bg-rose-50/50 dark:bg-rose-950/20 dark:border-rose-800/60 hover:bg-rose-100/60 transition group cursor-pointer"
                                >
                                    <div className="flex items-center gap-3">
                                        <ShieldAlert className="h-4 w-4 text-rose-600 dark:text-rose-400 shrink-0" />
                                        <div>
                                            <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                                {pendingLeavesCount} Leave {pendingLeavesCount === 1 ? "Request" : "Requests"}
                                            </p>
                                            <p className="text-[11px] text-slate-600 dark:text-slate-400">
                                                Awaiting admin or principal approval
                                            </p>
                                        </div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-rose-600 group-hover:translate-x-0.5 transition-transform" />
                                </Link>
                            ) : (
                                <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200/70 bg-slate-50/50 dark:bg-slate-800/40 dark:border-slate-800">
                                    <div className="flex items-center gap-3">
                                        <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                        <div>
                                            <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                                Staff Leaves Clear
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                No pending leave applications
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}

                            {/* Attention Item 3: Expense Vouchers */}
                            {pendingExpensesCount > 0 ? (
                                <Link
                                    href="/dashboard/expenses"
                                    className="flex items-center justify-between p-3.5 rounded-xl border border-sky-200/80 bg-sky-50/50 dark:bg-sky-950/20 dark:border-sky-800/60 hover:bg-sky-100/60 transition group cursor-pointer"
                                >
                                    <div className="flex items-center gap-3">
                                        <FileText className="h-4 w-4 text-sky-600 dark:text-sky-400 shrink-0" />
                                        <div>
                                            <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                                {pendingExpensesCount} Draft {pendingExpensesCount === 1 ? "Voucher" : "Vouchers"}
                                            </p>
                                            <p className="text-[11px] text-slate-600 dark:text-slate-400">
                                                Operational expense approval pending
                                            </p>
                                        </div>
                                    </div>
                                    <ChevronRight className="h-4 w-4 text-sky-600 group-hover:translate-x-0.5 transition-transform" />
                                </Link>
                            ) : (
                                <div className="flex items-center justify-between p-3.5 rounded-xl border border-slate-200/70 bg-slate-50/50 dark:bg-slate-800/40 dark:border-slate-800">
                                    <div className="flex items-center gap-3">
                                        <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
                                        <div>
                                            <p className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                                Vouchers Approved
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                All accounts entries audited
                                            </p>
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* 4. Split Cockpit (Recent Activity vs Quick Launchpad & Academic Structure) */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        {/* Left Column: Recent Promotion Activity & Lifecycle (8 Cols) */}
                        <div className="lg:col-span-8 space-y-6">
                            <Card className="border border-slate-200/80 dark:border-slate-800 shadow-xs bg-white dark:bg-slate-900">
                                <CardHeader className="flex flex-row items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
                                    <div>
                                        <CardTitle className="text-base font-bold text-slate-900 dark:text-white">
                                            Student Academic Lifecycle
                                        </CardTitle>
                                        <CardDescription className="text-xs">
                                            Recent promotions, grade advancements, and transfers
                                        </CardDescription>
                                    </div>
                                    <Link
                                        href="/dashboard/students/promotions"
                                        className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline inline-flex items-center gap-1"
                                    >
                                        View All <ChevronRight className="h-3 w-3" />
                                    </Link>
                                </CardHeader>
                                <CardContent className="pt-4 px-0">
                                    {isLoading ? (
                                        <div className="px-6 space-y-3">
                                            <Skeleton className="h-12 w-full" />
                                            <Skeleton className="h-12 w-full" />
                                            <Skeleton className="h-12 w-full" />
                                        </div>
                                    ) : !summary || summary.promotion.recent.length === 0 ? (
                                        <div className="text-center py-10 px-4">
                                            <Activity className="h-10 w-10 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
                                            <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                                                No lifecycle activity logged yet
                                            </p>
                                            <p className="text-xs text-slate-400 mt-1">
                                                Student promotions and batch transitions will appear here.
                                            </p>
                                        </div>
                                    ) : (
                                        <div className="divide-y divide-slate-100 dark:divide-slate-800/80">
                                            {summary.promotion.recent.slice(0, 6).map((record) => {
                                                const actionInfo = ACTION_LABELS[record.action] ?? {
                                                    label: record.action,
                                                    color: "bg-slate-100 text-slate-700 border-slate-200",
                                                };
                                                return (
                                                    <div
                                                        key={record.id}
                                                        className="flex items-center gap-4 px-6 py-3.5 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors"
                                                    >
                                                        <div className="h-10 w-10 rounded-full bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 font-bold flex items-center justify-center shrink-0 text-xs border border-sky-200/50 dark:border-sky-800/50">
                                                            {record.student_name.slice(0, 2).toUpperCase()}
                                                        </div>
                                                        <div className="flex-1 min-w-0">
                                                            <div className="flex items-center gap-2">
                                                                <p className="font-semibold text-sm text-slate-900 dark:text-slate-100 truncate">
                                                                    {record.student_name}
                                                                </p>
                                                                <span
                                                                    className={`px-2 py-0.5 rounded text-[10px] font-bold border ${actionInfo.color}`}
                                                                >
                                                                    {actionInfo.label}
                                                                </span>
                                                            </div>
                                                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5 truncate">
                                                                {record.source_level_name || "—"}
                                                                {record.target_level_name ? ` → ${record.target_level_name}` : ""}
                                                                {" · "}
                                                                {record.source_academic_year}
                                                                {record.target_academic_year ? ` → ${record.target_academic_year}` : ""}
                                                            </p>
                                                        </div>
                                                        <span className="text-[11px] font-medium text-slate-400 shrink-0">
                                                            {new Date(record.created_at).toLocaleDateString(undefined, {
                                                                month: "short",
                                                                day: "numeric",
                                                            })}
                                                        </span>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </CardContent>
                            </Card>
                        </div>

                        {/* Right Column: Launchpad & Academic Structure (4 Cols) */}
                        <div className="lg:col-span-4 space-y-6">
                            {/* Fast Launchpad */}
                            <Card className="border border-slate-200/80 dark:border-slate-800 shadow-xs bg-white dark:bg-slate-900">
                                <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
                                    <CardTitle className="text-sm font-bold text-slate-900 dark:text-white">
                                        Operational Launchpad
                                    </CardTitle>
                                    <CardDescription className="text-xs">
                                        Frequent daily management tasks
                                    </CardDescription>
                                </CardHeader>
                                <CardContent className="p-3 space-y-1">
                                    <Link
                                        href="/dashboard/fees"
                                        className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-lg bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 group-hover:scale-105 transition-transform">
                                            <CreditCard className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                                Collect Student Fees
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Search enrollment & record payment
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/attendance/mark"
                                        className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400 group-hover:scale-105 transition-transform">
                                            <CheckSquare className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                                Mark Daily Attendance
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Section-wise roll call sheet
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/students"
                                        className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-lg bg-sky-50 dark:bg-sky-950/50 text-sky-600 dark:text-sky-400 group-hover:scale-105 transition-transform">
                                            <UserPlus className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                                New Admission
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Enroll new student into batch
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/ptm"
                                        className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-lg bg-teal-50 dark:bg-teal-950/50 text-teal-600 dark:text-teal-400 group-hover:scale-105 transition-transform">
                                            <CalendarCheck2 className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                                PTM Slot Booking
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Manage parent-teacher schedules
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/communication/announcements"
                                        className="flex items-center gap-3 p-2.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-lg bg-purple-50 dark:bg-purple-950/50 text-purple-600 dark:text-purple-400 group-hover:scale-105 transition-transform">
                                            <Megaphone className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                                School Notice Board
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Broadcast circulars to parents & staff
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>
                                </CardContent>
                            </Card>

                            {/* Academic Structure Live Card */}
                            <Card className="border border-slate-200/80 dark:border-slate-800 shadow-xs bg-white dark:bg-slate-900">
                                <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
                                    <div className="flex items-center justify-between">
                                        <CardTitle className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                            <Layers className="h-4 w-4 text-sky-600 dark:text-sky-400" />
                                            <span>Academic Structure</span>
                                        </CardTitle>
                                        <Link
                                            href="/dashboard/academics"
                                            className="text-[11px] font-semibold text-sky-600 hover:underline"
                                        >
                                            Configure
                                        </Link>
                                    </div>
                                </CardHeader>
                                <CardContent className="p-4">
                                    <div className="grid grid-cols-3 gap-2 text-center">
                                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                                            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Programs</p>
                                            <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                                                {summary?.academics.programs ?? 0}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                                            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Levels</p>
                                            <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                                                {summary?.academics.levels ?? 0}
                                            </p>
                                        </div>
                                        <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 border border-slate-100 dark:border-slate-800">
                                            <p className="text-xs font-semibold text-slate-500 dark:text-slate-400">Sections</p>
                                            <p className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                                                {summary?.academics.sections ?? 0}
                                            </p>
                                        </div>
                                    </div>
                                </CardContent>
                            </Card>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
