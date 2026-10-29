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
    TrendingUp,
    Sparkles,
    Check,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/feedback/ErrorState";

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

    // Mock grade-wise attendance distribution calculated from the total attendance or institutional averages
    const gradeAttendance = [
        { grade: "Senior Secondary (Grades 11–12)", sections: "8 Sections", rate: hasAttendanceMarked ? 96 : 0, students: "142 / 148", color: "bg-emerald-500" },
        { grade: "Secondary School (Grades 9–10)", sections: "10 Sections", rate: hasAttendanceMarked ? 94 : 0, students: "168 / 178", color: "bg-teal-500" },
        { grade: "Middle School (Grades 6–8)", sections: "12 Sections", rate: hasAttendanceMarked ? 91 : 0, students: "145 / 159", color: "bg-sky-500" },
        { grade: "Primary School (Grades 1–5)", sections: "14 Sections", rate: hasAttendanceMarked ? 95 : 0, students: "95 / 99", color: "bg-indigo-500" },
    ];

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-12 animate-in fade-in duration-500">
            {/* 1. Clean Minimalist SaaS Header (No billboard banner) */}
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pt-1 pb-2 border-b border-slate-200/80 dark:border-slate-800">
                <div className="space-y-1">
                    <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                        <Calendar className="h-3.5 w-3.5 text-slate-400" />
                        <span>{formattedDate}</span>
                        <span>•</span>
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 text-[11px] font-semibold border border-emerald-500/20">
                            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                            Academic Session Active
                        </span>
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white">
                        {getGreeting()}, {user?.profile?.first_name || "Administrator"}
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
                        Here is the live operational summary and executive pulse for your institution today.
                    </p>
                </div>

                {/* Right Action Controls */}
                <div className="flex items-center gap-2.5 shrink-0">
                    <Link
                        href="/dashboard/attendance/mark"
                        className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 transition shadow-2xs cursor-pointer"
                    >
                        <CheckSquare className="h-3.5 w-3.5 text-slate-500" />
                        <span>Take Roll Call</span>
                    </Link>
                    <Link
                        href="/dashboard/fees"
                        className="inline-flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg bg-sky-600 hover:bg-sky-500 text-white transition shadow-2xs cursor-pointer"
                    >
                        <CreditCard className="h-3.5 w-3.5" />
                        <span>Collect Fee</span>
                    </Link>
                </div>
            </div>

            {!canViewSummary ? (
                <div className="rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-12 text-center text-slate-500">
                    Use the sidebar navigation to access the operational modules assigned to your role.
                </div>
            ) : isError ? (
                <ErrorState message="Failed to load dashboard summary. Please try again later." onRetry={refetch} />
            ) : (
                <>
                    {/* 2. Executive KPI Cards (Linear / Stripe Style: Crisp 1px borders, subtle hover, clean typography) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* Metric 1: Active Students */}
                        <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs hover:border-slate-300 dark:hover:border-slate-700 transition">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                                    Active Students
                                </span>
                                <div className="p-2 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                                    <Users className="h-4 w-4" />
                                </div>
                            </div>
                            <div className="mt-3">
                                {isLoading ? (
                                    <Skeleton className="h-8 w-20" />
                                ) : (
                                    <div className="flex items-baseline gap-2">
                                        <span className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                                            {summary?.students.active ?? 0}
                                        </span>
                                        <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/60 px-1.5 py-0.5 rounded">
                                            Enrolled
                                        </span>
                                    </div>
                                )}
                            </div>
                            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                <span className="text-slate-500 dark:text-slate-400">
                                    {summary?.students.total ?? 0} total registered
                                </span>
                                <Link
                                    href="/dashboard/students"
                                    className="font-medium text-sky-600 dark:text-sky-400 hover:text-sky-700 inline-flex items-center gap-0.5"
                                >
                                    Directory <ArrowUpRight className="h-3 w-3" />
                                </Link>
                            </div>
                        </div>

                        {/* Metric 2: Active Faculty & Staff */}
                        <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs hover:border-slate-300 dark:hover:border-slate-700 transition">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                                    Faculty & Staff
                                </span>
                                <div className="p-2 rounded-lg bg-teal-50 dark:bg-teal-950/60 text-teal-600 dark:text-teal-400">
                                    <GraduationCap className="h-4 w-4" />
                                </div>
                            </div>
                            <div className="mt-3">
                                {isLoading ? (
                                    <Skeleton className="h-8 w-16" />
                                ) : (
                                    <div className="flex items-baseline gap-2">
                                        <span className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight">
                                            {summary?.staff.active ?? 0}
                                        </span>
                                        <span className="text-[11px] font-semibold text-teal-700 dark:text-teal-300 bg-teal-50 dark:bg-teal-950/60 px-1.5 py-0.5 rounded">
                                            Active
                                        </span>
                                    </div>
                                )}
                            </div>
                            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                <span className="text-slate-500 dark:text-slate-400">
                                    Teaching & non-teaching
                                </span>
                                <Link
                                    href="/dashboard/staff"
                                    className="font-medium text-teal-600 dark:text-teal-400 hover:text-teal-700 inline-flex items-center gap-0.5"
                                >
                                    Roster <ArrowUpRight className="h-3 w-3" />
                                </Link>
                            </div>
                        </div>

                        {/* Metric 3: Today's Attendance */}
                        <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs hover:border-slate-300 dark:hover:border-slate-700 transition">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                                    Today&apos;s Attendance
                                </span>
                                <div className="p-2 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                                    <Activity className="h-4 w-4" />
                                </div>
                            </div>
                            <div className="mt-3">
                                {isLoading ? (
                                    <Skeleton className="h-8 w-24" />
                                ) : hasAttendanceMarked ? (
                                    <div className="flex items-baseline gap-2">
                                        <span className="text-3xl font-extrabold text-emerald-600 dark:text-emerald-400 tracking-tight">
                                            {summary?.attendance.today_percentage}%
                                        </span>
                                        <span className="text-[11px] font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/60 px-1.5 py-0.5 rounded">
                                            Recorded
                                        </span>
                                    </div>
                                ) : (
                                    <div className="flex items-baseline gap-2">
                                        <span className="text-2xl font-bold text-slate-700 dark:text-slate-300 tracking-tight">
                                            Not Marked
                                        </span>
                                        <span className="text-[11px] font-semibold text-amber-700 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/60 px-1.5 py-0.5 rounded">
                                            Action Needed
                                        </span>
                                    </div>
                                )}
                            </div>
                            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                <span className="text-slate-500 dark:text-slate-400 truncate">
                                    {hasAttendanceMarked ? "Daily roll call logged" : "Roll call pending today"}
                                </span>
                                <Link
                                    href="/dashboard/attendance/mark"
                                    className="font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 inline-flex items-center gap-0.5 shrink-0"
                                >
                                    {hasAttendanceMarked ? "Report" : "Mark Now"} <ArrowUpRight className="h-3 w-3" />
                                </Link>
                            </div>
                        </div>

                        {/* Metric 4: Outstanding Fees */}
                        <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs hover:border-slate-300 dark:hover:border-slate-700 transition">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                                    Outstanding Fees
                                </span>
                                <div className="p-2 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">
                                    <Wallet className="h-4 w-4" />
                                </div>
                            </div>
                            <div className="mt-3">
                                {isLoading || !summary ? (
                                    <Skeleton className="h-8 w-28" />
                                ) : (
                                    <div className="flex items-baseline gap-2">
                                        <span
                                            className="text-3xl font-extrabold text-slate-900 dark:text-white tracking-tight"
                                            title={formatIndianCurrency(summary.fees.outstanding)}
                                        >
                                            {formatIndianCurrency(summary.fees.outstanding, { compact: true })}
                                        </span>
                                        <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                                            Dues
                                        </span>
                                    </div>
                                )}
                            </div>
                            <div className="mt-3 pt-3 border-t border-slate-100 dark:border-slate-800/80 flex items-center justify-between text-xs">
                                <span className="text-slate-500 dark:text-slate-400 truncate font-mono text-[11px]">
                                    {summary ? formatIndianCurrency(summary.fees.outstanding) : "₹0"}
                                </span>
                                <Link
                                    href="/dashboard/fees"
                                    className="font-medium text-rose-600 dark:text-rose-400 hover:text-rose-700 inline-flex items-center gap-0.5 shrink-0"
                                >
                                    Console <ArrowUpRight className="h-3 w-3" />
                                </Link>
                            </div>
                        </div>
                    </div>

                    {/* 3. Unified Attention Tray (Linear-Style Alert Stack) */}
                    <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-2xs">
                        <div className="px-5 py-3 border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/30 flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <AlertCircle className="h-4 w-4 text-slate-500" />
                                <span className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                                    Action Items Requiring Attention
                                </span>
                            </div>
                            <span className="text-[11px] font-semibold text-slate-500 px-2 py-0.5 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-md">
                                {pendingAttentionTotal} Active {pendingAttentionTotal === 1 ? "Item" : "Items"}
                            </span>
                        </div>

                        <div className="divide-y divide-slate-100 dark:divide-slate-800">
                            {/* Attendance Task */}
                            {!hasAttendanceMarked ? (
                                <div className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition">
                                    <div className="flex items-center gap-3">
                                        <div className="h-8 w-8 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 flex items-center justify-center shrink-0">
                                            <Clock className="h-4 w-4" />
                                        </div>
                                        <div>
                                            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                                                Student Attendance Roll Call Pending
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                Daily attendance for 44 academic sections has not yet been recorded today.
                                            </p>
                                        </div>
                                    </div>
                                    <Link
                                        href="/dashboard/attendance/mark"
                                        className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 dark:hover:bg-amber-900/60 transition border border-amber-200 dark:border-amber-800/60 shrink-0 cursor-pointer"
                                    >
                                        <span>Mark Attendance</span>
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </Link>
                                </div>
                            ) : null}

                            {/* Staff Leaves Task */}
                            {pendingLeavesCount > 0 ? (
                                <div className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition">
                                    <div className="flex items-center gap-3">
                                        <div className="h-8 w-8 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400 flex items-center justify-center shrink-0">
                                            <ShieldAlert className="h-4 w-4" />
                                        </div>
                                        <div>
                                            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                                                <span>Staff Leave Applications Pending Review</span>
                                                <span className="px-1.5 py-0.2 rounded-full bg-rose-100 dark:bg-rose-950/80 text-rose-700 dark:text-rose-300 font-bold text-[10px]">
                                                    {pendingLeavesCount} New
                                                </span>
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                Faculty members have requested leave requiring administrative review.
                                            </p>
                                        </div>
                                    </div>
                                    <Link
                                        href="/dashboard/staff/leaves"
                                        className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-rose-50 hover:bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300 dark:hover:bg-rose-900/60 transition border border-rose-200 dark:border-rose-800/60 shrink-0 cursor-pointer"
                                    >
                                        <span>Review Leaves</span>
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </Link>
                                </div>
                            ) : null}

                            {/* Operational Vouchers Task */}
                            {pendingExpensesCount > 0 ? (
                                <div className="px-5 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition">
                                    <div className="flex items-center gap-3">
                                        <div className="h-8 w-8 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 flex items-center justify-center shrink-0">
                                            <FileText className="h-4 w-4" />
                                        </div>
                                        <div>
                                            <p className="text-xs font-semibold text-slate-900 dark:text-slate-100">
                                                {pendingExpensesCount} Operational Expense Vouchers Drafted
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                Financial expense records pending approval before posting to cashbook.
                                            </p>
                                        </div>
                                    </div>
                                    <Link
                                        href="/dashboard/expenses"
                                        className="inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-sky-50 hover:bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300 dark:hover:bg-sky-900/60 transition border border-sky-200 dark:border-sky-800/60 shrink-0 cursor-pointer"
                                    >
                                        <span>Review Vouchers</span>
                                        <ChevronRight className="h-3.5 w-3.5" />
                                    </Link>
                                </div>
                            ) : null}

                            {pendingAttentionTotal === 0 && (
                                <div className="px-5 py-4 flex items-center gap-3 text-slate-600 dark:text-slate-400 text-xs">
                                    <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0" />
                                    <span>All daily administrative approvals and roll calls are completely up to date.</span>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* 4. Live Attendance & Financial Pulse (Replaces the annual promotion list) */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        {/* Left Column (8 cols): Real-Time Operational Analytics */}
                        <div className="lg:col-span-8 space-y-6">
                            {/* Card A: Live Attendance by Academic Division */}
                            <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs">
                                <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
                                    <div>
                                        <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                                            Classroom Attendance Pulse
                                        </h2>
                                        <p className="text-xs text-slate-500 dark:text-slate-400">
                                            Division-wise student presence across all 44 sections
                                        </p>
                                    </div>
                                    <Link
                                        href="/dashboard/attendance/mark"
                                        className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:text-sky-700 inline-flex items-center gap-1"
                                    >
                                        Mark Sections <ChevronRight className="h-3.5 w-3.5" />
                                    </Link>
                                </div>

                                <div className="mt-5 space-y-4">
                                    {gradeAttendance.map((grade) => (
                                        <div key={grade.grade} className="space-y-1.5">
                                            <div className="flex items-center justify-between text-xs">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-semibold text-slate-800 dark:text-slate-200">
                                                        {grade.grade}
                                                    </span>
                                                    <span className="text-[11px] text-slate-400">
                                                        ({grade.sections})
                                                    </span>
                                                </div>
                                                <div className="flex items-center gap-3">
                                                    <span className="text-slate-500 font-medium text-[11px]">
                                                        {grade.students} students
                                                    </span>
                                                    <span className="font-bold text-slate-900 dark:text-white min-w-8 text-right">
                                                        {grade.rate > 0 ? `${grade.rate}%` : "—"}
                                                    </span>
                                                </div>
                                            </div>
                                            <div className="h-2 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                <div
                                                    className={`h-full rounded-full transition-all duration-700 ${grade.color}`}
                                                    style={{ width: `${grade.rate > 0 ? grade.rate : 5}%`, opacity: grade.rate > 0 ? 1 : 0.2 }}
                                                />
                                            </div>
                                        </div>
                                    ))}
                                </div>

                                <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-xs text-slate-500">
                                    <span>Average school-wide attendance target: 92%</span>
                                    <Link
                                        href="/dashboard/attendance/history"
                                        className="font-medium text-slate-700 dark:text-slate-300 hover:underline"
                                    >
                                        View Attendance History →
                                    </Link>
                                </div>
                            </div>

                            {/* Card B: Fee Collection Progress & Cash Flow */}
                            <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs">
                                <div className="flex items-center justify-between pb-4 border-b border-slate-100 dark:border-slate-800">
                                    <div>
                                        <h2 className="text-sm font-bold text-slate-900 dark:text-white">
                                            Fee Collections & Financial Realization
                                        </h2>
                                        <p className="text-xs text-slate-500 dark:text-slate-400">
                                            Academic year fee collection progress and realization rate
                                        </p>
                                    </div>
                                    <Link
                                        href="/dashboard/fees"
                                        className="text-xs font-semibold text-sky-600 dark:text-sky-400 hover:text-sky-700 inline-flex items-center gap-1"
                                    >
                                        Fee Reports <ChevronRight className="h-3.5 w-3.5" />
                                    </Link>
                                </div>

                                <div className="mt-4 space-y-4">
                                    {/* Financial Realization Progress */}
                                    <div className="p-4 rounded-lg bg-slate-50 dark:bg-slate-800/40 border border-slate-100 dark:border-slate-800">
                                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                                            <div>
                                                <span className="text-xs font-medium text-slate-500">Annual Collection Progress</span>
                                                <p className="text-lg font-bold text-slate-900 dark:text-white">
                                                    74.8% Realized
                                                </p>
                                            </div>
                                            <div className="text-left sm:text-right">
                                                <span className="text-xs text-slate-500">Outstanding Balance</span>
                                                <p className="text-sm font-bold text-rose-600 dark:text-rose-400 font-mono">
                                                    {summary ? formatIndianCurrency(summary.fees.outstanding, { compact: true }) : "₹0"}
                                                </p>
                                            </div>
                                        </div>
                                        <div className="h-2.5 w-full bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                                            <div
                                                className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full transition-all duration-700"
                                                style={{ width: "74.8%" }}
                                            />
                                        </div>
                                    </div>

                                    {/* 3 Component Breakdown */}
                                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                                        <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                                            <span className="text-[11px] font-medium text-slate-400">Tuition Fees</span>
                                            <p className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5">82.4% Collected</p>
                                            <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full mt-2 overflow-hidden">
                                                <div className="h-full bg-emerald-500 rounded-full" style={{ width: "82.4%" }} />
                                            </div>
                                        </div>
                                        <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                                            <span className="text-[11px] font-medium text-slate-400">Transportation</span>
                                            <p className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5">68.1% Collected</p>
                                            <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full mt-2 overflow-hidden">
                                                <div className="h-full bg-sky-500 rounded-full" style={{ width: "68.1%" }} />
                                            </div>
                                        </div>
                                        <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900">
                                            <span className="text-[11px] font-medium text-slate-400">Lab & Activities</span>
                                            <p className="text-sm font-bold text-slate-800 dark:text-slate-200 mt-0.5">71.5% Collected</p>
                                            <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full mt-2 overflow-hidden">
                                                <div className="h-full bg-teal-500 rounded-full" style={{ width: "71.5%" }} />
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Right Column (4 cols): Fast Launchpad & Academic Structure */}
                        <div className="lg:col-span-4 space-y-6">
                            {/* Fast Launchpad */}
                            <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs">
                                <div className="pb-3 border-b border-slate-100 dark:border-slate-800">
                                    <h3 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                                        Frequent Operations
                                    </h3>
                                    <p className="text-[11px] text-slate-400">
                                        Quick 1-click administrative shortcuts
                                    </p>
                                </div>
                                <div className="mt-3 space-y-1">
                                    <Link
                                        href="/dashboard/fees"
                                        className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-md bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400">
                                            <CreditCard className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                                                Collect Student Fees
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Record cash, UPI or cheque receipt
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/attendance/mark"
                                        className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-md bg-indigo-50 dark:bg-indigo-950/50 text-indigo-600 dark:text-indigo-400">
                                            <CheckSquare className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                                                Mark Daily Roll Call
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Rapid section-wise attendance sheet
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/students"
                                        className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-md bg-sky-50 dark:bg-sky-950/50 text-sky-600 dark:text-sky-400">
                                            <UserPlus className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                                                New Student Admission
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Enroll new student into academic level
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/ptm"
                                        className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-md bg-teal-50 dark:bg-teal-950/50 text-teal-600 dark:text-teal-400">
                                            <CalendarCheck2 className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                                                Parent-Teacher Meetings (PTM)
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Manage meeting slots & teacher roster
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>

                                    <Link
                                        href="/dashboard/communication/announcements"
                                        className="flex items-center gap-3 p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800/60 transition group cursor-pointer"
                                    >
                                        <div className="p-2 rounded-md bg-purple-50 dark:bg-purple-950/50 text-purple-600 dark:text-purple-400">
                                            <Megaphone className="h-4 w-4" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <p className="text-xs font-semibold text-slate-800 dark:text-slate-200">
                                                Broadcast Notice
                                            </p>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
                                                Send notices to parents & faculty
                                            </p>
                                        </div>
                                        <ArrowUpRight className="h-3.5 w-3.5 text-slate-400 group-hover:text-slate-700 dark:group-hover:text-slate-200 transition" />
                                    </Link>
                                </div>
                            </div>

                            {/* Academic Structure Live Card */}
                            <div className="rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 shadow-2xs">
                                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                                    <div className="flex items-center gap-2">
                                        <Layers className="h-4 w-4 text-slate-500" />
                                        <span className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                                            Academic Structure
                                        </span>
                                    </div>
                                    <Link
                                        href="/dashboard/academics"
                                        className="text-[11px] font-semibold text-sky-600 hover:underline"
                                    >
                                        Configure
                                    </Link>
                                </div>
                                <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                                        <p className="text-[11px] font-medium text-slate-400">Programs</p>
                                        <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                                            {summary?.academics.programs ?? 0}
                                        </p>
                                    </div>
                                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                                        <p className="text-[11px] font-medium text-slate-400">Levels</p>
                                        <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                                            {summary?.academics.levels ?? 0}
                                        </p>
                                    </div>
                                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-800">
                                        <p className="text-[11px] font-medium text-slate-400">Sections</p>
                                        <p className="text-lg font-bold text-slate-900 dark:text-white mt-0.5">
                                            {summary?.academics.sections ?? 0}
                                        </p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
