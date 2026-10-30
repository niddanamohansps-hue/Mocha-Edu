"use client";

import { useState } from "react";
import { useMe } from "@/hooks/useAuth";
import { useStudentAttendanceHistory } from "@/hooks/useAttendance";
import { useStudents } from "@/hooks/useStudents";
import { usePermissions } from "@/providers/PermissionProvider";
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
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import {
    History,
    Calendar,
    Search,
    User,
    CheckCircle2,
    XCircle,
    Clock,
    UserCheck,
    X,
    Filter,
} from "lucide-react";

const STATUS_LABELS: Record<string, { label: string; badge: string }> = {
    present: {
        label: "Present",
        badge: "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800",
    },
    absent: {
        label: "Absent",
        badge: "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800",
    },
    late: {
        label: "Late Arrival",
        badge: "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800",
    },
    half_day: {
        label: "Half Day",
        badge: "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-800",
    },
    leave: {
        label: "On Leave",
        badge: "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800",
    },
};

export default function AttendanceHistoryPage() {
    const { data: user } = useMe();
    const { activeRole } = usePermissions();
    const isStudent = activeRole === "student";

    const [studentSearch, setStudentSearch] = useState("");
    const [selectedStudent, setSelectedStudent] = useState<any>(null);
    const [studentId, setStudentId] = useState<string>(isStudent ? user?.profile?.student_id ?? "" : "");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    // Live student query for admin/teacher lookup
    const { data: studentList, isLoading: searchingStudents } = useStudents(
        studentSearch.trim().length >= 2 ? { search: studentSearch, pageSize: 6 } : { pageSize: 0 }
    );

    const effectiveStudentId = isStudent
        ? user?.profile?.student_id ?? undefined
        : selectedStudent?.id ?? (studentId ? studentId : undefined);

    const { data, isLoading, isError, refetch } = useStudentAttendanceHistory(
        effectiveStudentId,
        startDate,
        endDate
    );

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-16 animate-in fade-in duration-500">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <History className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        <span>Attendance History &amp; Audits</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {isStudent
                            ? "Review your personal attendance percentages, presence logs, and leave remarks"
                            : "Inspect individual student attendance records, absentee logs, and date-range metrics"}
                    </p>
                </div>
            </div>

            {/* Filter Card */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    {!isStudent && (
                        <div className="md:col-span-6 relative space-y-1.5">
                            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                <User className="h-3.5 w-3.5 text-slate-500" />
                                Find Student by Name or Enrollment ID
                            </label>
                            {selectedStudent ? (
                                <div className="flex items-center justify-between p-2 rounded-xl bg-sky-50 dark:bg-sky-950/60 border border-sky-200 dark:border-sky-800">
                                    <div className="flex items-center gap-2">
                                        <div className="h-7 w-7 rounded-full bg-sky-600 text-white font-bold text-xs flex items-center justify-center">
                                            {selectedStudent.first_name?.[0]}
                                        </div>
                                        <div>
                                            <div className="text-xs font-bold text-slate-900 dark:text-white">
                                                {selectedStudent.first_name} {selectedStudent.last_name}
                                            </div>
                                            <div className="text-[10px] font-mono text-slate-500">
                                                {selectedStudent.enrollment_id}
                                            </div>
                                        </div>
                                    </div>
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => {
                                            setSelectedStudent(null);
                                            setStudentId("");
                                        }}
                                        className="h-7 px-2 text-xs text-slate-500 hover:text-rose-600"
                                    >
                                        Change
                                    </Button>
                                </div>
                            ) : (
                                <div className="relative">
                                    <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                    <Input
                                        placeholder="Type student name or ID (e.g. Rahul)..."
                                        value={studentSearch}
                                        onChange={(e) => setStudentSearch(e.target.value)}
                                        className="h-10 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                                    />
                                    {/* Auto-Complete Dropdown */}
                                    {studentList && studentList.results && studentList.results.length > 0 && (
                                        <div className="absolute z-30 left-0 right-0 mt-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-lg overflow-hidden max-h-56 overflow-y-auto">
                                            {studentList.results.map((st: any) => (
                                                <button
                                                    key={st.id}
                                                    type="button"
                                                    onClick={() => {
                                                        setSelectedStudent(st);
                                                        setStudentId(st.id);
                                                        setStudentSearch("");
                                                    }}
                                                    className="w-full text-left p-2.5 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 last:border-0"
                                                >
                                                    <div>
                                                        <div className="text-xs font-semibold text-slate-900 dark:text-white">
                                                            {st.first_name} {st.last_name}
                                                        </div>
                                                        <div className="text-[10px] text-slate-400">
                                                            {st.current_section?.name || "Enrolled"}
                                                        </div>
                                                    </div>
                                                    <span className="font-mono text-[10px] bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-slate-600 dark:text-slate-400">
                                                        {st.enrollment_id}
                                                    </span>
                                                </button>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    )}

                    <div className={`${isStudent ? "md:col-span-6" : "md:col-span-3"} space-y-1.5`}>
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5 text-slate-500" />
                            From Date
                        </label>
                        <Input
                            type="date"
                            value={startDate}
                            onChange={(e) => setStartDate(e.target.value)}
                            className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                        />
                    </div>

                    <div className={`${isStudent ? "md:col-span-6" : "md:col-span-3"} space-y-1.5`}>
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                            <Calendar className="h-3.5 w-3.5 text-slate-500" />
                            To Date
                        </label>
                        <Input
                            type="date"
                            value={endDate}
                            onChange={(e) => setEndDate(e.target.value)}
                            className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                        />
                    </div>
                </div>
            </div>

            {!effectiveStudentId && (
                <EmptyState
                    title={
                        isStudent
                            ? "No student profile is linked to your account yet."
                            : "Search and select a student above to review their attendance history."
                    }
                    className="py-16 text-slate-500 text-sm"
                />
            )}

            {effectiveStudentId && isLoading && <LoadingState className="py-20" />}
            {effectiveStudentId && isError && <ErrorState onRetry={refetch} />}

            {effectiveStudentId && data && (
                <div className="space-y-5">
                    {/* Performance Metrics */}
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 shadow-2xs">
                            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                Attendance Rate
                            </span>
                            <div className="text-2xl font-black text-slate-900 dark:text-white mt-1">
                                {data.percentage !== null ? `${data.percentage}%` : "—"}
                            </div>
                        </div>

                        {Object.entries(STATUS_LABELS).map(([key, cfg]) => {
                            const count = (data.counts as any)?.[key] ?? 0;
                            return (
                                <div
                                    key={key}
                                    className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 shadow-2xs"
                                >
                                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                        {cfg.label}
                                    </span>
                                    <div className="text-2xl font-black text-slate-900 dark:text-white mt-1">
                                        {count}
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Records Table */}
                    {data.records.length === 0 ? (
                        <EmptyState
                            title="No attendance records found for this period."
                            className="py-16 text-slate-500 text-sm"
                        />
                    ) : (
                        <TableShell>
                            <Table>
                                <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                    <TableRow>
                                        <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Date
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Status
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider pr-4">
                                            Teacher Remarks
                                        </TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {data.records.map((r, i) => {
                                        const cfg = STATUS_LABELS[r.status] || {
                                            label: r.status,
                                            badge: "bg-slate-100 text-slate-700 border-slate-200",
                                        };
                                        return (
                                            <TableRow
                                                key={i}
                                                className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                            >
                                                <TableCell className="py-3 pl-4 font-medium text-xs text-slate-900 dark:text-slate-100">
                                                    {r.date}
                                                </TableCell>
                                                <TableCell className="py-3">
                                                    <span
                                                        className={`text-xs px-2.5 py-0.5 rounded-full font-semibold border ${cfg.badge}`}
                                                    >
                                                        {cfg.label}
                                                    </span>
                                                </TableCell>
                                                <TableCell className="py-3 pr-4 text-xs text-slate-500 dark:text-slate-400">
                                                    {r.remarks || "—"}
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableShell>
                    )}
                </div>
            )}
        </div>
    );
}
