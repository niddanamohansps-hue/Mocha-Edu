"use client";

import { useState, useMemo } from "react";
import {
    CalendarCheck,
    CheckCircle2,
    XCircle,
    Clock,
    AlertCircle,
    Calendar,
    Filter,
    Percent,
} from "lucide-react";
import { useChildAttendance, useLinkedChildren } from "@/hooks/useParentPortal";
import { AttendanceStatus } from "@/types/ParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const STATUS_CONFIG: Record<
    AttendanceStatus,
    { label: string; badgeClass: string; icon: typeof CheckCircle2 }
> = {
    present: {
        label: "Present",
        badgeClass: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border-emerald-300/80",
        icon: CheckCircle2,
    },
    absent: {
        label: "Absent",
        badgeClass: "bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border-rose-300/80",
        icon: XCircle,
    },
    late: {
        label: "Late Arrival",
        badgeClass: "bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border-amber-300/80",
        icon: Clock,
    },
    half_day: {
        label: "Half Day",
        badgeClass: "bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border-sky-300/80",
        icon: AlertCircle,
    },
    leave: {
        label: "Approved Leave",
        badgeClass: "bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border-purple-300/80",
        icon: Calendar,
    },
};

export default function ParentPortalAttendancePage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_child_attendance");

    const { data: children } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const effectiveChildId = selectedChildId || children?.[0]?.student_id;
    const { data, isLoading, isError, refetch } = useChildAttendance(effectiveChildId, startDate, endDate);

    if (!canView) {
        return <Unauthorized />;
    }

    const setQuickRange = (days: number) => {
        const end = new Date().toISOString().slice(0, 10);
        const start = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString().slice(0, 10);
        setStartDate(start);
        setEndDate(end);
    };

    const clearRange = () => {
        setStartDate("");
        setEndDate("");
    };

    return (
        <div className="space-y-6">
            {/* Header & Controls */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <CalendarCheck className="w-6 h-6 text-sky-600 dark:text-sky-400" />
                        <span>Child Attendance Ledger</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Detailed attendance logs, daily punch timestamps, and cumulative attendance percentage.
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

            {/* Date Filters Bar */}
            <div className="p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div className="flex flex-wrap items-center gap-3 text-xs">
                    <div className="flex items-center gap-1.5">
                        <span className="text-slate-500 font-semibold">From:</span>
                        <Input
                            type="date"
                            value={startDate}
                            onChange={(e) => setStartDate(e.target.value)}
                            className="h-8.5 text-xs w-36 rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                        />
                    </div>
                    <div className="flex items-center gap-1.5">
                        <span className="text-slate-500 font-semibold">To:</span>
                        <Input
                            type="date"
                            value={endDate}
                            onChange={(e) => setEndDate(e.target.value)}
                            className="h-8.5 text-xs w-36 rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                        />
                    </div>
                    {(startDate || endDate) && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={clearRange}
                            className="h-8.5 px-2.5 text-xs text-slate-500 hover:text-slate-800 cursor-pointer"
                        >
                            Clear
                        </Button>
                    )}
                </div>

                {/* Quick Range Presets */}
                <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[11px] text-slate-400 font-medium mr-1">Presets:</span>
                    <button
                        type="button"
                        onClick={() => setQuickRange(7)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-md border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 cursor-pointer transition"
                    >
                        Last 7 Days
                    </button>
                    <button
                        type="button"
                        onClick={() => setQuickRange(30)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-md border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 cursor-pointer transition"
                    >
                        Last 30 Days
                    </button>
                    <button
                        type="button"
                        onClick={() => setQuickRange(90)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-md border border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-600 dark:text-slate-300 cursor-pointer transition"
                    >
                        Quarter (90d)
                    </button>
                </div>
            </div>

            {!effectiveChildId ? (
                <EmptyState
                    title={
                        children && children.length === 0
                            ? "No children linked to this parent account."
                            : "Select a child to view their attendance."
                    }
                    className="py-16"
                />
            ) : isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : data ? (
                <>
                    {/* Six-Card Metric Summary Strip */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3.5">
                        {/* Overall Percentage */}
                        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                Cumulative
                            </span>
                            <div className="text-2xl font-bold text-sky-600 dark:text-sky-400">
                                {data.percentage !== null ? `${data.percentage}%` : "—"}
                            </div>
                            <span className="text-[10px] text-slate-400 block">Attendance Rate</span>
                        </div>

                        {/* Present */}
                        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
                                Present
                            </span>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">
                                {data.counts.present ?? 0}
                            </div>
                            <span className="text-[10px] text-slate-400 block">Days attended</span>
                        </div>

                        {/* Absent */}
                        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-rose-600 dark:text-rose-400">
                                Absent
                            </span>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">
                                {data.counts.absent ?? 0}
                            </div>
                            <span className="text-[10px] text-slate-400 block">Unexcused days</span>
                        </div>

                        {/* Late */}
                        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-amber-600 dark:text-amber-400">
                                Late
                            </span>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">
                                {data.counts.late ?? 0}
                            </div>
                            <span className="text-[10px] text-slate-400 block">Delayed arrival</span>
                        </div>

                        {/* Half Day */}
                        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400">
                                Half Day
                            </span>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">
                                {data.counts.half_day ?? 0}
                            </div>
                            <span className="text-[10px] text-slate-400 block">Early exit</span>
                        </div>

                        {/* Leave */}
                        <div className="p-4 rounded-xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs space-y-1">
                            <span className="text-[10px] font-bold uppercase tracking-wider text-purple-600 dark:text-purple-400">
                                Leave
                            </span>
                            <div className="text-2xl font-bold text-slate-900 dark:text-white">
                                {data.counts.leave ?? 0}
                            </div>
                            <span className="text-[10px] text-slate-400 block">Formal leaves</span>
                        </div>
                    </div>

                    {/* Table of Records */}
                    {data.records.length === 0 ? (
                        <EmptyState
                            title="No attendance records in this date range."
                            description="Try selecting a different date range or preset."
                            className="py-16"
                        />
                    ) : (
                        <TableShell>
                            <Table>
                                <TableHeader>
                                    <TableRow className="bg-slate-50/75 dark:bg-slate-900/60">
                                        <TableHead className="w-12 text-center text-xs font-bold text-slate-500">
                                            #
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Date
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Attendance Status
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                            Remarks / Notes
                                        </TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.records.map((r, index) => {
                                        const config = STATUS_CONFIG[r.status] || {
                                            label: r.status,
                                            badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
                                            icon: AlertCircle,
                                        };
                                        const StatusIcon = config.icon;

                                        return (
                                            <TableRow key={`${r.date}-${index}`} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                                <TableCell className="text-center text-xs font-medium text-slate-400">
                                                    {index + 1}
                                                </TableCell>
                                                <TableCell className="text-xs font-bold text-slate-900 dark:text-white">
                                                    {r.date}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge
                                                        variant="outline"
                                                        className={`text-xs py-0.5 px-2.5 font-semibold inline-flex items-center gap-1.5 ${config.badgeClass}`}
                                                    >
                                                        <StatusIcon className="w-3.5 h-3.5" />
                                                        <span>{config.label}</span>
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-500 dark:text-slate-400">
                                                    {r.remarks || "—"}
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableShell>
                    )}
                </>
            ) : null}
        </div>
    );
}
