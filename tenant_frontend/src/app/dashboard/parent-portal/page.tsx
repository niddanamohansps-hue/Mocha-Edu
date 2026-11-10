"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
    Users,
    CalendarCheck,
    CreditCard,
    GraduationCap,
    Clock,
    Sparkles,
    ArrowRight,
    CheckCircle2,
    XCircle,
    AlertTriangle,
    Calendar,
    Award,
    Video,
    ChevronRight,
    Loader2,
    ShieldAlert,
    BookOpen,
} from "lucide-react";
import {
    useChildAttendance,
    useChildUpcomingExams,
    useChildReportCard,
    useChildFees,
    useChildTimetable,
    useLinkedChildren,
} from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { formatIndianCurrency } from "@/lib/currency";

function todayISODate() {
    return new Date().toISOString().slice(0, 10);
}

export default function ParentPortalDashboardPage() {
    const { can, isOwner } = usePermissions();
    if (!(isOwner || can("view_own_children"))) {
        return <Unauthorized />;
    }
    return <ParentPortalDashboardPageContent />;
}

function ParentPortalDashboardPageContent() {
    const { can, isOwner } = usePermissions();
    const canViewAttendance = isOwner || can("view_child_attendance");
    const canViewResults = isOwner || can("view_child_results");
    const canViewFees = isOwner || can("view_child_fees");

    const {
        data: children,
        isLoading: loadingChildren,
        isError: childrenError,
        refetch: refetchChildren,
    } = useLinkedChildren();

    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);

    const effectiveChildId = selectedChildId || children?.[0]?.student_id;
    const selectedChild = children?.find((c) => c.student_id === effectiveChildId);

    const attendanceChildId = canViewAttendance ? effectiveChildId : undefined;
    const resultsChildId = canViewResults ? effectiveChildId : undefined;
    const feesChildId = canViewFees ? effectiveChildId : undefined;

    const { data: attendance, isLoading: loadingAttendance } = useChildAttendance(attendanceChildId);
    const { data: upcomingExams, isLoading: loadingUpcoming } = useChildUpcomingExams(resultsChildId);
    const { data: reportCard, isLoading: loadingReportCard } = useChildReportCard(resultsChildId);
    const { data: feeData, isLoading: loadingFees } = useChildFees(feesChildId);
    const { data: timetable, isLoading: loadingTimetable } = useChildTimetable(effectiveChildId);

    const today = todayISODate();
    const todaysAttendance = attendance?.records?.find((r) => r.date === today);
    const latestResult = reportCard?.examinations?.[0];

    // Outstanding fees
    const totalOutstanding = useMemo(() => {
        if (!feeData?.fees) return 0;
        return feeData.fees
            .filter((f) => f.status === "active")
            .reduce((acc, f) => acc + (parseFloat(f.outstanding_balance) || 0), 0);
    }, [feeData]);

    const activeFeeCount = useMemo(() => {
        if (!feeData?.fees) return 0;
        return feeData.fees.filter((f) => f.status === "active" && parseFloat(f.outstanding_balance) > 0).length;
    }, [feeData]);

    return (
        <div className="space-y-6">
            {/* Header with Child Switcher */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Users className="w-6 h-6 text-sky-600 dark:text-sky-400" />
                        <span>Parent Portal Command Center</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Track academic progress, daily attendance, fee settlements, and timetable schedules.
                    </p>
                </div>

                <div className="flex items-center gap-3 self-start sm:self-auto">
                    <ChildSwitcher
                        childOptions={children || []}
                        selectedId={effectiveChildId}
                        onChange={setSelectedChildId}
                    />
                </div>
            </div>

            {loadingChildren ? (
                <LoadingState className="py-20" />
            ) : childrenError ? (
                <ErrorState onRetry={refetchChildren} />
            ) : !children || children.length === 0 ? (
                <EmptyState
                    title="No children linked to this parent account."
                    description="Please contact the school administrative office to link your student admission records."
                    className="py-16"
                />
            ) : !selectedChild ? (
                <EmptyState title="Select a child to view their academic dashboard." className="py-16" />
            ) : (
                <>
                    {/* 1. Student Hero Profile Strip */}
                    <div className="p-5 bg-gradient-to-r from-sky-500/10 via-indigo-500/10 to-transparent rounded-2xl border border-sky-200/70 dark:border-sky-900/50 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-5">
                        <div className="flex items-center gap-4">
                            <Avatar name={selectedChild.full_name} size="xl" shape="rounded" />
                            <div className="space-y-1">
                                <div className="flex items-center gap-2.5 flex-wrap">
                                    <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                                        {selectedChild.full_name}
                                    </h2>
                                    {selectedChild.is_primary_contact && (
                                        <Badge className="bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border-none text-[10px] font-semibold">
                                            Primary Contact
                                        </Badge>
                                    )}
                                </div>
                                <div className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-400 flex-wrap">
                                    <span className="font-semibold text-slate-900 dark:text-slate-200">
                                        Class: {selectedChild.level || "—"}
                                    </span>
                                    {selectedChild.section && (
                                        <span>• Section {selectedChild.section}</span>
                                    )}
                                    <span>• Adm No: {selectedChild.enrollment_id}</span>
                                </div>
                            </div>
                        </div>

                        {/* Quick Hero Shortcuts */}
                        <div className="flex items-center gap-2 flex-wrap">
                            <Link href="/dashboard/parent-portal/fees">
                                <Button
                                    size="sm"
                                    className="bg-emerald-600 hover:bg-emerald-500 text-white gap-1.5"
                                >
                                    <CreditCard className="w-3.5 h-3.5" />
                                    <span>Pay Fees</span>
                                </Button>
                            </Link>
                            <Link href="/dashboard/parent-portal/results">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="gap-1.5"
                                >
                                    <GraduationCap className="w-3.5 h-3.5 text-sky-600" />
                                    <span>Report Card</span>
                                </Button>
                            </Link>
                            <Link href="/dashboard/parent-portal/ptm">
                                <Button
                                    variant="outline"
                                    size="sm"
                                    className="gap-1.5"
                                >
                                    <Video className="w-3.5 h-3.5 text-indigo-600" />
                                    <span>Book PTM</span>
                                </Button>
                            </Link>
                        </div>
                    </div>

                    {/* 2. Four-Card Vital Pulse Strip */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                        {/* Attendance Pulse */}
                        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2">
                            <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                                <span>Today&apos;s Attendance</span>
                                <CalendarCheck className="w-4 h-4 text-sky-500" />
                            </div>
                            <div className="pt-1">
                                {!canViewAttendance ? (
                                    <span className="text-xs text-slate-400">Restricted</span>
                                ) : loadingAttendance ? (
                                    <Loader2 className="w-5 h-5 animate-spin text-sky-600" />
                                ) : todaysAttendance ? (
                                    <div className="flex items-center gap-2">
                                        <Badge
                                            className={
                                                todaysAttendance.status === "present"
                                                    ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-xs px-2.5 py-0.5"
                                                    : todaysAttendance.status === "absent"
                                                    ? "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 text-xs px-2.5 py-0.5"
                                                    : "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 text-xs px-2.5 py-0.5"
                                            }
                                        >
                                            {todaysAttendance.status.toUpperCase()}
                                        </Badge>
                                        <span className="text-xs text-slate-400">Marked today</span>
                                    </div>
                                ) : (
                                    <div className="flex items-center gap-1.5 text-slate-500 text-sm font-semibold">
                                        <Clock className="w-4 h-4 text-slate-400" />
                                        <span>Not Marked Yet</span>
                                    </div>
                                )}
                            </div>
                            <div className="pt-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                                <span>Monthly Average</span>
                                <span className="font-semibold text-slate-700 dark:text-slate-300">
                                    {attendance?.records?.length
                                        ? `${Math.round(
                                              (attendance.records.filter((r) => r.status === "present").length /
                                                  attendance.records.length) *
                                                  100
                                          )}%`
                                        : "—"}
                                </span>
                            </div>
                        </div>

                        {/* Academic Standing */}
                        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2">
                            <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                                <span>Academic Performance</span>
                                <Award className="w-4 h-4 text-purple-500" />
                            </div>
                            <div className="pt-1">
                                {!canViewResults ? (
                                    <span className="text-xs text-slate-400">Restricted</span>
                                ) : loadingReportCard ? (
                                    <Loader2 className="w-5 h-5 animate-spin text-purple-600" />
                                ) : latestResult ? (
                                    <div>
                                        <div className="text-xl font-bold text-slate-900 dark:text-white">
                                            {latestResult.percentage}%
                                        </div>
                                        <div className="text-[11px] text-slate-400 truncate">
                                            {latestResult.examination_name}
                                        </div>
                                    </div>
                                ) : (
                                    <span className="text-xs text-slate-400">No published scores</span>
                                )}
                            </div>
                            <div className="pt-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                                <span>Grade Assessment</span>
                                <span className="font-semibold text-purple-600 dark:text-purple-400">
                                    {latestResult ? "Term Complete" : "Pending Evaluation"}
                                </span>
                            </div>
                        </div>

                        {/* Fee Status */}
                        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2">
                            <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                                <span>Outstanding Fees</span>
                                <CreditCard className="w-4 h-4 text-emerald-500" />
                            </div>
                            <div className="pt-1">
                                {!canViewFees ? (
                                    <span className="text-xs text-slate-400">Restricted</span>
                                ) : loadingFees ? (
                                    <Loader2 className="w-5 h-5 animate-spin text-emerald-600" />
                                ) : totalOutstanding > 0 ? (
                                    <div>
                                        <div className="text-xl font-bold text-rose-600 dark:text-rose-400">
                                            {formatIndianCurrency(totalOutstanding)}
                                        </div>
                                        <div className="text-[11px] text-slate-400">
                                            {activeFeeCount} pending fee installment{activeFeeCount > 1 ? "s" : ""}
                                        </div>
                                    </div>
                                ) : (
                                    <div>
                                        <div className="text-xl font-bold text-emerald-600 dark:text-emerald-400">
                                            ₹0.00
                                        </div>
                                        <div className="text-[11px] text-emerald-600 dark:text-emerald-400">
                                            All dues settled
                                        </div>
                                    </div>
                                )}
                            </div>
                            <div className="pt-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                                <span>Online Gateway</span>
                                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                                    {totalOutstanding > 0 ? "Settlement Due" : "Clear"}
                                </span>
                            </div>
                        </div>

                        {/* Timetable Schedule */}
                        <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs space-y-2">
                            <div className="flex items-center justify-between text-xs font-semibold text-slate-500">
                                <span>Weekly Schedule</span>
                                <Clock className="w-4 h-4 text-amber-500" />
                            </div>
                            <div className="pt-1">
                                {loadingTimetable ? (
                                    <Loader2 className="w-5 h-5 animate-spin text-amber-600" />
                                ) : timetable?.results?.length ? (
                                    <div>
                                        <div className="text-xl font-bold text-slate-900 dark:text-white">
                                            {timetable.results.length} Periods
                                        </div>
                                        <div className="text-[11px] text-slate-400 truncate">
                                            Section: {timetable.section}
                                        </div>
                                    </div>
                                ) : (
                                    <div>
                                        <div className="text-xl font-bold text-slate-700 dark:text-slate-300">
                                            Standard
                                        </div>
                                        <div className="text-[11px] text-slate-400">Regular school timetable</div>
                                    </div>
                                )}
                            </div>
                            <div className="pt-1 border-t border-slate-100 dark:border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
                                <span>Section Schedule</span>
                                <span className="font-semibold text-amber-600 dark:text-amber-400">Active</span>
                            </div>
                        </div>
                    </div>

                    {/* 3. Operational Two-Column Work Desk */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                        {/* Quick Action Navigation Grid (7 Columns) */}
                        <div className="lg:col-span-7 space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                    Student Management Hub
                                </h3>
                                <span className="text-xs text-slate-400">Quick portals</span>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                                {/* Fees Card */}
                                <Link
                                    href="/dashboard/parent-portal/fees"
                                    className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-emerald-300 dark:hover:border-emerald-800 transition shadow-2xs group cursor-pointer block"
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                                            <CreditCard className="w-5 h-5" />
                                        </div>
                                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition" />
                                    </div>
                                    <div className="mt-3">
                                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                                            Fee Payments & Invoices
                                        </div>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                            View itemized fee structures, due dates, receipts, and pay online securely.
                                        </p>
                                    </div>
                                </Link>

                                {/* Attendance Card */}
                                <Link
                                    href="/dashboard/parent-portal/attendance"
                                    className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-sky-300 dark:hover:border-sky-800 transition shadow-2xs group cursor-pointer block"
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                                            <CalendarCheck className="w-5 h-5" />
                                        </div>
                                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition" />
                                    </div>
                                    <div className="mt-3">
                                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                                            Attendance Calendar
                                        </div>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                            Monitor daily arrival records, leaves, half-days, and monthly attendance ratios.
                                        </p>
                                    </div>
                                </Link>

                                {/* Results & Transcripts */}
                                <Link
                                    href="/dashboard/parent-portal/results"
                                    className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-purple-300 dark:hover:border-purple-800 transition shadow-2xs group cursor-pointer block"
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                                            <GraduationCap className="w-5 h-5" />
                                        </div>
                                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition" />
                                    </div>
                                    <div className="mt-3">
                                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                                            Report Cards & Results
                                        </div>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                            Download published terminal report cards, subject breakdowns, and teacher feedback.
                                        </p>
                                    </div>
                                </Link>

                                {/* PTM Meetings */}
                                <Link
                                    href="/dashboard/parent-portal/ptm"
                                    className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-indigo-300 dark:hover:border-indigo-800 transition shadow-2xs group cursor-pointer block"
                                >
                                    <div className="flex items-start justify-between">
                                        <div className="p-2.5 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                                            <Video className="w-5 h-5" />
                                        </div>
                                        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:translate-x-1 transition" />
                                    </div>
                                    <div className="mt-3">
                                        <div className="text-sm font-bold text-slate-900 dark:text-white">
                                            Parent-Teacher Meetings
                                        </div>
                                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                            Book one-on-one conference slots with subject teachers and class mentors.
                                        </p>
                                    </div>
                                </Link>
                            </div>
                        </div>

                        {/* Upcoming Examinations & Academic Alerts (5 Columns) */}
                        <div className="lg:col-span-5 space-y-4">
                            <div className="flex items-center justify-between">
                                <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                    Upcoming Examinations
                                </h3>
                                <Badge variant="outline" className="text-[10px] py-0 text-slate-500">
                                    Examination Cell
                                </Badge>
                            </div>

                            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-4 shadow-2xs space-y-3">
                                {!canViewResults ? (
                                    <p className="text-xs text-slate-400 py-4 text-center">No permission to view upcoming exams.</p>
                                ) : loadingUpcoming ? (
                                    <div className="flex items-center justify-center py-6">
                                        <Loader2 className="w-6 h-6 animate-spin text-sky-600" />
                                    </div>
                                ) : !upcomingExams || upcomingExams.length === 0 ? (
                                    <div className="text-center py-6 space-y-1.5">
                                        <BookOpen className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto" />
                                        <p className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                            No Upcoming Exams Scheduled
                                        </p>
                                        <p className="text-[11px] text-slate-400">
                                            Check back when the examination schedule is published.
                                        </p>
                                    </div>
                                ) : (
                                    <div className="divide-y divide-slate-100 dark:divide-slate-800">
                                        {upcomingExams.slice(0, 5).map((exam) => (
                                            <div key={exam.id} className="py-2.5 flex items-center justify-between gap-3">
                                                <div className="min-w-0">
                                                    <div className="text-xs font-bold text-slate-900 dark:text-white truncate">
                                                        {exam.subject_name}
                                                    </div>
                                                    <div className="text-[11px] text-slate-400 truncate">
                                                        {exam.examination_name}
                                                    </div>
                                                </div>
                                                <div className="text-right shrink-0">
                                                    <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300 border border-sky-200/80 text-[10px]">
                                                        {exam.date}
                                                    </Badge>
                                                    {exam.start_time && (
                                                        <div className="text-[10px] text-slate-400 mt-0.5">
                                                            {exam.start_time}
                                                        </div>
                                                    )}
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
