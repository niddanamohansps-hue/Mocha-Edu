"use client";

import { useMemo, useState } from "react";
import {
    LoaderCircle,
    CheckCheck,
    Lock,
    Calendar,
    Users,
    UserCheck,
    UserX,
    Clock,
    AlertCircle,
    Search,
    X,
    Filter,
    Sparkles,
    CalendarDays,
    RotateCcw,
    ChevronRight,
    GraduationCap,
    CheckCircle2,
    Save,
} from "lucide-react";
import { useSections } from "@/hooks/useAcademics";
import {
    useSectionRoster,
    useSubmitAttendanceSession,
    useUpdateAttendanceSession,
} from "@/hooks/useAttendance";
import { AttendanceStatus } from "@/types/Attendance";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
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
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { AttendanceHolidayAdvisory } from "@/components/dashboard/attendance/AttendanceHolidayAdvisory";
import { toast } from "sonner";

const STATUS_CONFIG: Record<
    AttendanceStatus,
    {
        label: string;
        activeClass: string;
        inactiveClass: string;
        dotClass: string;
    }
> = {
    present: {
        label: "Present",
        activeClass: "bg-emerald-600 text-white shadow-xs font-bold",
        inactiveClass: "bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300",
        dotClass: "bg-emerald-500",
    },
    absent: {
        label: "Absent",
        activeClass: "bg-rose-600 text-white shadow-xs font-bold",
        inactiveClass: "bg-rose-50 text-rose-700 hover:bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300",
        dotClass: "bg-rose-500",
    },
    late: {
        label: "Late",
        activeClass: "bg-amber-600 text-white shadow-xs font-bold",
        inactiveClass: "bg-amber-50 text-amber-700 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300",
        dotClass: "bg-amber-500",
    },
    half_day: {
        label: "Half Day",
        activeClass: "bg-sky-600 text-white shadow-xs font-bold",
        inactiveClass: "bg-sky-50 text-sky-700 hover:bg-sky-100 dark:bg-sky-950/40 dark:text-sky-300",
        dotClass: "bg-sky-500",
    },
    leave: {
        label: "Leave",
        activeClass: "bg-purple-600 text-white shadow-xs font-bold",
        inactiveClass: "bg-purple-50 text-purple-700 hover:bg-purple-100 dark:bg-purple-950/40 dark:text-purple-300",
        dotClass: "bg-purple-500",
    },
};

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

function todayISO() {
    return new Date().toISOString().slice(0, 10);
}

function yesterdayISO() {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    return d.toISOString().slice(0, 10);
}

export default function MarkAttendancePage() {
    const { can, isOwner } = usePermissions();
    const canMark = isOwner || can("mark_attendance");

    const { data: sections, isLoading: loadingSections } = useSections();
    const [sectionId, setSectionId] = useState<string>("");
    const [date, setDate] = useState<string>(todayISO());
    const [marks, setMarks] = useState<Record<string, { status: AttendanceStatus; remarks: string }>>({});
    const [studentSearch, setStudentSearch] = useState<string>("");
    const [statusFilter, setStatusFilter] = useState<string>("all");

    const {
        data: roster,
        isLoading: loadingRoster,
        isFetching,
        isError: rosterError,
        refetch: refetchRoster,
    } = useSectionRoster(sectionId || undefined, date);

    const { mutate: submitSession, isPending: isSubmitting } = useSubmitAttendanceSession();
    const { mutate: updateSession, isPending: isUpdating } = useUpdateAttendanceSession();

    const isLocked = Boolean(roster?.session?.is_locked);
    const alreadySubmitted = Boolean(roster?.session);

    // Reset local marks whenever the roster changes (new section/date, or refetched).
    const rosterKey = roster ? `${roster.section}-${roster.date}` : "";
    const [initializedKey, setInitializedKey] = useState("");
    if (roster && rosterKey !== initializedKey) {
        const initial: Record<string, { status: AttendanceStatus; remarks: string }> = {};
        for (const s of roster.students) {
            initial[s.student] = {
                status: s.existing?.status ?? "present",
                remarks: s.existing?.remarks ?? "",
            };
        }
        setMarks(initial);
        setInitializedKey(rosterKey);
    }

    // Selected section details
    const selectedSection = useMemo(() => {
        return sections?.find((s) => s.id === sectionId);
    }, [sections, sectionId]);

    // Live Attendance Statistics Calculations
    const stats = useMemo(() => {
        if (!roster || roster.students.length === 0) {
            return {
                total: 0,
                present: 0,
                absent: 0,
                late: 0,
                halfDay: 0,
                leave: 0,
                rate: 100,
            };
        }

        const total = roster.students.length;
        let present = 0;
        let absent = 0;
        let late = 0;
        let halfDay = 0;
        let leave = 0;

        for (const s of roster.students) {
            const status = marks[s.student]?.status ?? "present";
            if (status === "present") present++;
            else if (status === "absent") absent++;
            else if (status === "late") late++;
            else if (status === "half_day") halfDay++;
            else if (status === "leave") leave++;
        }

        const rate = total > 0 ? Math.round(((present + late * 0.5 + halfDay * 0.5) / total) * 100) : 100;

        return {
            total,
            present,
            absent,
            late,
            halfDay,
            leave,
            rate,
        };
    }, [roster, marks]);

    // Filtered roster students by search query and status pill
    const filteredStudents = useMemo(() => {
        if (!roster?.students) return [];
        return roster.students.filter((s) => {
            const matchesSearch =
                !studentSearch ||
                s.full_name.toLowerCase().includes(studentSearch.toLowerCase()) ||
                s.enrollment_id.toLowerCase().includes(studentSearch.toLowerCase());

            const studentStatus = marks[s.student]?.status ?? "present";
            const matchesStatus =
                statusFilter === "all" ||
                studentStatus === statusFilter;

            return matchesSearch && matchesStatus;
        });
    }, [roster?.students, studentSearch, statusFilter, marks]);

    const markAllPresent = () => {
        if (isLocked) return;
        setMarks((prev) => {
            const next = { ...prev };
            for (const key of Object.keys(next)) {
                next[key] = { ...next[key], status: "present" };
            }
            return next;
        });
        toast.success("Marked all students as Present");
    };

    const markAllAbsent = () => {
        if (isLocked) return;
        setMarks((prev) => {
            const next = { ...prev };
            for (const key of Object.keys(next)) {
                next[key] = { ...next[key], status: "absent" };
            }
            return next;
        });
        toast.info("Marked all students as Absent");
    };

    const resetMarks = () => {
        if (isLocked || !roster) return;
        const initial: Record<string, { status: AttendanceStatus; remarks: string }> = {};
        for (const s of roster.students) {
            initial[s.student] = {
                status: s.existing?.status ?? "present",
                remarks: s.existing?.remarks ?? "",
            };
        }
        setMarks(initial);
        toast.info("Reset attendance records to initial session state");
    };

    const handleSubmit = () => {
        if (!roster || isLocked) return;
        const records = roster.students.map((s) => ({
            student: s.student,
            status: marks[s.student]?.status ?? "present",
            remarks: marks[s.student]?.remarks ?? "",
        }));

        if (roster.session) {
            updateSession(
                { sessionId: roster.session.id, records },
                {
                    onSuccess: () => {
                        toast.success("Attendance session updated successfully!");
                    },
                }
            );
        } else {
            submitSession(
                { section: sectionId, date, records },
                {
                    onSuccess: () => {
                        toast.success("Attendance session recorded successfully!");
                    },
                }
            );
        }
    };

    if (!canMark) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <CheckCircle2 className="h-7 w-7 text-emerald-600 dark:text-emerald-400" />
                        <span>Classroom Attendance Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Daily roll-call registry, real-time presence pulse, and exception tracking across academic sections
                    </p>
                </div>

                {/* Session Status Pill */}
                {sectionId && roster && (
                    <div className="flex items-center gap-2 shrink-0">
                        {isLocked ? (
                            <Badge variant="outline" className="h-8 px-3 gap-1.5 border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/60 text-amber-700 dark:text-amber-300 text-xs font-semibold">
                                <Lock className="h-3.5 w-3.5 text-amber-600" />
                                Session Locked
                            </Badge>
                        ) : alreadySubmitted ? (
                            <Badge variant="outline" className="h-8 px-3 gap-1.5 border-emerald-300 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 text-xs font-semibold">
                                <CheckCheck className="h-3.5 w-3.5 text-emerald-600" />
                                Recorded (Editable)
                            </Badge>
                        ) : (
                            <Badge variant="outline" className="h-8 px-3 gap-1.5 border-sky-300 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 text-xs font-semibold">
                                <Sparkles className="h-3.5 w-3.5 text-sky-600" />
                                New Registry
                            </Badge>
                        )}
                    </div>
                )}
            </div>

            {/* 2. Control Card: Section & Date Selectors */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-end">
                    {/* Section Selector */}
                    <div className="md:col-span-6 lg:col-span-5 space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                            <Users className="h-3.5 w-3.5 text-slate-500" />
                            Academic Section <span className="text-rose-500">*</span>
                        </label>
                        <Select value={sectionId} onValueChange={setSectionId} disabled={loadingSections}>
                            <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue placeholder="Select class and section..." />
                            </SelectTrigger>
                            <SelectContent>
                                {sections?.map((s) => (
                                    <SelectItem key={s.id} value={s.id} className="text-xs font-medium cursor-pointer">
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold text-slate-900 dark:text-slate-100">{s.level_name}</span>
                                            <span className="text-slate-400">Section {s.name}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Date Picker & Quick Shortcuts */}
                    <div className="md:col-span-6 lg:col-span-4 space-y-1.5">
                        <div className="flex items-center justify-between">
                            <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                <Calendar className="h-3.5 w-3.5 text-slate-500" />
                                Attendance Date <span className="text-rose-500">*</span>
                            </label>
                            <div className="flex items-center gap-1 text-[11px]">
                                <button
                                    type="button"
                                    onClick={() => setDate(todayISO())}
                                    className={`px-1.5 py-0.5 rounded transition cursor-pointer font-semibold ${
                                        date === todayISO()
                                            ? "bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300"
                                            : "text-slate-500 hover:text-slate-900 dark:hover:text-slate-200"
                                    }`}
                                >
                                    Today
                                </button>
                                <span className="text-slate-300 dark:text-slate-700">•</span>
                                <button
                                    type="button"
                                    onClick={() => setDate(yesterdayISO())}
                                    className={`px-1.5 py-0.5 rounded transition cursor-pointer font-semibold ${
                                        date === yesterdayISO()
                                            ? "bg-sky-100 dark:bg-sky-950 text-sky-700 dark:text-sky-300"
                                            : "text-slate-500 hover:text-slate-900 dark:hover:text-slate-200"
                                    }`}
                                >
                                    Yesterday
                                </button>
                            </div>
                        </div>
                        <Input
                            type="date"
                            value={date}
                            onChange={(e) => setDate(e.target.value)}
                            className="h-10 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                        />
                    </div>

                    {/* Quick Bulk Action Buttons */}
                    <div className="md:col-span-12 lg:col-span-3 flex items-center gap-2">
                        {roster && roster.students.length > 0 && !isLocked && (
                            <>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={markAllPresent}
                                    className="h-10 flex-1 text-xs font-semibold border-emerald-200 dark:border-emerald-800/60 bg-emerald-50/50 hover:bg-emerald-100/70 text-emerald-700 dark:text-emerald-300 gap-1.5 cursor-pointer shadow-2xs"
                                >
                                    <CheckCheck className="h-3.5 w-3.5" />
                                    All Present
                                </Button>
                                <Button
                                    type="button"
                                    variant="outline"
                                    size="sm"
                                    onClick={markAllAbsent}
                                    className="h-10 text-xs font-semibold border-rose-200 dark:border-rose-800/60 bg-rose-50/50 hover:bg-rose-100/70 text-rose-700 dark:text-rose-300 gap-1.5 cursor-pointer shadow-2xs"
                                >
                                    <UserX className="h-3.5 w-3.5" />
                                    All Absent
                                </Button>
                            </>
                        )}
                    </div>
                </div>

                {/* Holiday & School Closure Advisory Banner */}
                <AttendanceHolidayAdvisory date={date} />
            </div>

            {/* Empty State: Prompt to select a section */}
            {!sectionId && (
                <EmptyState
                    title="Choose a section to open today's roster"
                    description="Select an academic class and section from the dropdown above to load enrolled students and mark attendance."
                    className="py-16 text-slate-500"
                />
            )}

            {/* Loading State */}
            {sectionId && (loadingRoster || isFetching) && <LoadingState className="py-20" />}

            {/* Error State */}
            {sectionId && rosterError && !loadingRoster && <ErrorState onRetry={refetchRoster} />}

            {/* 3. Main Roster Desk View */}
            {sectionId && roster && !loadingRoster && (
                <>
                    {/* Locked Banner Warning */}
                    {isLocked && (
                        <div className="flex items-center gap-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800/60 text-amber-800 dark:text-amber-300 text-xs font-medium px-4 py-3 rounded-xl shadow-2xs">
                            <Lock className="h-4 w-4 shrink-0 text-amber-600" />
                            <span>
                                This attendance session has been finalized and locked by the academic administration. Records are in read-only audit mode.
                            </span>
                        </div>
                    )}

                    {roster.students.length === 0 ? (
                        <EmptyState
                            title="No enrolled students found"
                            description={`No active students are currently allocated to ${selectedSection?.level_name ?? "this level"} - ${selectedSection?.name ?? "Section"}.`}
                            className="py-16 text-slate-500 text-sm"
                        />
                    ) : (
                        <div className="space-y-4">
                            {/* 3A. Attendance Pulse Gauge (Real-Time Metrics Strip) */}
                            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
                                {/* Total Roster */}
                                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 shadow-2xs">
                                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                        Total Class
                                    </span>
                                    <div className="text-xl font-bold text-slate-900 dark:text-white mt-1">
                                        {stats.total}
                                    </div>
                                    <span className="text-[10px] text-slate-400 font-medium">Students Enrolled</span>
                                </div>

                                {/* Present Count */}
                                <div className="bg-white dark:bg-slate-900 border border-emerald-200/60 dark:border-emerald-900/60 rounded-xl p-3 shadow-2xs">
                                    <span className="text-[11px] font-semibold text-emerald-600 dark:text-emerald-400 uppercase tracking-wider block">
                                        Present
                                    </span>
                                    <div className="text-xl font-bold text-emerald-700 dark:text-emerald-300 mt-1">
                                        {stats.present}
                                    </div>
                                    <span className="text-[10px] text-emerald-600/80 dark:text-emerald-400/80 font-medium">
                                        {Math.round((stats.present / (stats.total || 1)) * 100)}% of class
                                    </span>
                                </div>

                                {/* Absent Count */}
                                <div className="bg-white dark:bg-slate-900 border border-rose-200/60 dark:border-rose-900/60 rounded-xl p-3 shadow-2xs">
                                    <span className="text-[11px] font-semibold text-rose-600 dark:text-rose-400 uppercase tracking-wider block">
                                        Absent
                                    </span>
                                    <div className="text-xl font-bold text-rose-700 dark:text-rose-300 mt-1">
                                        {stats.absent}
                                    </div>
                                    <span className="text-[10px] text-rose-600/80 dark:text-rose-400/80 font-medium">
                                        Requires follow-up
                                    </span>
                                </div>

                                {/* Late Count */}
                                <div className="bg-white dark:bg-slate-900 border border-amber-200/60 dark:border-amber-900/60 rounded-xl p-3 shadow-2xs">
                                    <span className="text-[11px] font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider block">
                                        Late Arrival
                                    </span>
                                    <div className="text-xl font-bold text-amber-700 dark:text-amber-300 mt-1">
                                        {stats.late}
                                    </div>
                                    <span className="text-[10px] text-amber-600/80 dark:text-amber-400/80 font-medium">
                                        Tardy check-in
                                    </span>
                                </div>

                                {/* Leave & Half-Day Count */}
                                <div className="bg-white dark:bg-slate-900 border border-purple-200/60 dark:border-purple-900/60 rounded-xl p-3 shadow-2xs">
                                    <span className="text-[11px] font-semibold text-purple-600 dark:text-purple-400 uppercase tracking-wider block">
                                        Leave / Half-Day
                                    </span>
                                    <div className="text-xl font-bold text-purple-700 dark:text-purple-300 mt-1">
                                        {stats.halfDay + stats.leave}
                                    </div>
                                    <span className="text-[10px] text-purple-600/80 dark:text-purple-400/80 font-medium">
                                        Approved / partial
                                    </span>
                                </div>

                                {/* Presence Rate Gauge */}
                                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-3 shadow-2xs flex flex-col justify-between">
                                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                                        Attendance Rate
                                    </span>
                                    <div className="text-xl font-extrabold text-slate-900 dark:text-white">
                                        {stats.rate}%
                                    </div>
                                    {/* Mini Progress Bar */}
                                    <div className="w-full bg-slate-100 dark:bg-slate-800 rounded-full h-1.5 overflow-hidden">
                                        <div
                                            className={`h-full transition-all duration-500 ${
                                                stats.rate >= 90
                                                    ? "bg-emerald-500"
                                                    : stats.rate >= 75
                                                    ? "bg-amber-500"
                                                    : "bg-rose-500"
                                            }`}
                                            style={{ width: `${stats.rate}%` }}
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* 3B. Live Student Quick Search & Status Segment Filter */}
                            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 p-3 shadow-2xs flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                                {/* Search by student */}
                                <div className="relative flex-1 max-w-sm">
                                    <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                    <Input
                                        placeholder="Search student by name or enrollment ID..."
                                        value={studentSearch}
                                        onChange={(e) => setStudentSearch(e.target.value)}
                                        className="h-9 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                                    />
                                    {studentSearch && (
                                        <button
                                            type="button"
                                            onClick={() => setStudentSearch("")}
                                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5"
                                        >
                                            <X className="w-3 h-3" />
                                        </button>
                                    )}
                                </div>

                                {/* Status Filter Segment Pills */}
                                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 sm:pb-0 text-xs">
                                    {[
                                        { id: "all", label: "All", count: stats.total },
                                        { id: "present", label: "Present", count: stats.present },
                                        { id: "absent", label: "Absent", count: stats.absent },
                                        { id: "late", label: "Late", count: stats.late },
                                        { id: "half_day", label: "Half-Day", count: stats.halfDay },
                                        { id: "leave", label: "Leave", count: stats.leave },
                                    ].map((pill) => {
                                        const isActive = statusFilter === pill.id;
                                        return (
                                            <button
                                                key={pill.id}
                                                type="button"
                                                onClick={() => setStatusFilter(pill.id)}
                                                className={`px-2.5 py-1 rounded-lg text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 shrink-0 ${
                                                    isActive
                                                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                                        : "bg-slate-100/70 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 hover:bg-slate-200/60"
                                                }`}
                                            >
                                                <span>{pill.label}</span>
                                                <span
                                                    className={`text-[10px] px-1 py-0.2 rounded ${
                                                        isActive
                                                            ? "bg-white/20 text-white dark:bg-slate-900/20 dark:text-slate-900"
                                                            : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400"
                                                    }`}
                                                >
                                                    {pill.count}
                                                </span>
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>

                            {/* 3C. High-Density Roster Table */}
                            <TableShell>
                                <Table>
                                    <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                        <TableRow className="hover:bg-transparent">
                                            <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider w-16">
                                                Roll #
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Student Name & ID
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider min-w-[320px]">
                                                Roll-Call Status
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider pr-4 min-w-[200px]">
                                                Teacher Remarks (Optional)
                                            </TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredStudents.length === 0 ? (
                                            <TableRow>
                                                <TableCell colSpan={4} className="h-32 text-center text-xs text-slate-500">
                                                    No students match the current filter.
                                                </TableCell>
                                            </TableRow>
                                        ) : (
                                            filteredStudents.map((s, idx) => {
                                                const currentMark = marks[s.student] || { status: "present", remarks: "" };
                                                const avatarStyle = getAvatarStyle(s.full_name);
                                                const initials = getInitials(s.full_name);

                                                return (
                                                    <TableRow
                                                        key={s.student}
                                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 transition-colors border-b border-slate-100 dark:border-slate-800/70"
                                                    >
                                                        {/* Roll Number Index */}
                                                        <TableCell className="py-3 pl-4 font-mono text-xs text-slate-400 font-medium">
                                                            #{String(idx + 1).padStart(2, "0")}
                                                        </TableCell>

                                                        {/* Student Name with Deterministic Avatar */}
                                                        <TableCell className="py-3">
                                                            <div className="flex items-center gap-2.5">
                                                                <div
                                                                    className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                                >
                                                                    {initials}
                                                                </div>
                                                                <div>
                                                                    <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                                        {s.full_name}
                                                                    </div>
                                                                    <div className="text-[10px] font-mono text-slate-400">
                                                                        {s.enrollment_id}
                                                                    </div>
                                                                </div>
                                                            </div>
                                                        </TableCell>

                                                        {/* Segmented Status Pill Group */}
                                                        <TableCell className="py-3">
                                                            <div className="flex items-center gap-1 flex-wrap">
                                                                {(
                                                                    [
                                                                        "present",
                                                                        "absent",
                                                                        "late",
                                                                        "half_day",
                                                                        "leave",
                                                                    ] as AttendanceStatus[]
                                                                ).map((statusKey) => {
                                                                    const cfg = STATUS_CONFIG[statusKey];
                                                                    const isSelected = currentMark.status === statusKey;
                                                                    return (
                                                                        <button
                                                                            key={statusKey}
                                                                            type="button"
                                                                            disabled={isLocked}
                                                                            onClick={() => {
                                                                                setMarks((prev) => ({
                                                                                    ...prev,
                                                                                    [s.student]: {
                                                                                        ...prev[s.student],
                                                                                        status: statusKey,
                                                                                    },
                                                                                }));
                                                                            }}
                                                                            className={`px-2.5 py-1 text-xs rounded-lg transition cursor-pointer select-none ${
                                                                                isSelected ? cfg.activeClass : cfg.inactiveClass
                                                                            } ${isLocked ? "opacity-60 cursor-not-allowed" : ""}`}
                                                                        >
                                                                            {cfg.label}
                                                                        </button>
                                                                    );
                                                                })}
                                                            </div>
                                                        </TableCell>

                                                        {/* Optional Remarks Input */}
                                                        <TableCell className="py-3 pr-4">
                                                            <Input
                                                                aria-label={`Remarks for ${s.full_name}`}
                                                                className="h-8.5 text-xs bg-slate-50/50 dark:bg-slate-950/50 border-slate-200 dark:border-slate-800"
                                                                placeholder="Add attendance note..."
                                                                disabled={isLocked}
                                                                value={currentMark.remarks}
                                                                onChange={(e) =>
                                                                    setMarks((prev) => ({
                                                                        ...prev,
                                                                        [s.student]: {
                                                                            ...prev[s.student],
                                                                            remarks: e.target.value,
                                                                        },
                                                                    }))
                                                                }
                                                            />
                                                        </TableCell>
                                                    </TableRow>
                                                );
                                            })
                                        )}
                                    </TableBody>
                                </Table>
                            </TableShell>

                            {/* 3D. Sticky Bottom Docked Action Bar */}
                            <div className="sticky bottom-4 z-20 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md rounded-2xl border border-slate-200/90 dark:border-slate-800 p-4 shadow-lg flex flex-col sm:flex-row items-center justify-between gap-3">
                                <div className="flex items-center gap-3 text-xs">
                                    <div className="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
                                        <Users className="w-4 h-4 text-sky-600" />
                                        <span>
                                            {selectedSection?.level_name} - {selectedSection?.name}
                                        </span>
                                    </div>
                                    <span className="text-slate-300 dark:text-slate-700">|</span>
                                    <div className="flex items-center gap-2">
                                        <span className="text-emerald-600 font-semibold">{stats.present} Present</span>
                                        <span className="text-slate-300 dark:text-slate-700">•</span>
                                        <span className="text-rose-600 font-semibold">{stats.absent} Absent</span>
                                        {stats.late > 0 && (
                                            <>
                                                <span className="text-slate-300 dark:text-slate-700">•</span>
                                                <span className="text-amber-600 font-semibold">{stats.late} Late</span>
                                            </>
                                        )}
                                    </div>
                                </div>

                                <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end">
                                    {!isLocked && (
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            onClick={resetMarks}
                                            className="h-9 px-3 gap-1.5 text-xs font-semibold text-slate-600 dark:text-slate-300 cursor-pointer"
                                        >
                                            <RotateCcw className="w-3.5 h-3.5" />
                                            Reset
                                        </Button>
                                    )}

                                    <Button
                                        onClick={handleSubmit}
                                        disabled={isLocked || isSubmitting || isUpdating}
                                        className="h-9 px-5 gap-2 bg-emerald-600 hover:bg-emerald-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                                    >
                                        {isSubmitting || isUpdating ? (
                                            <LoaderCircle className="h-4 w-4 animate-spin" />
                                        ) : (
                                            <Save className="h-4 w-4" />
                                        )}
                                        {isLocked
                                            ? "Session Locked"
                                            : alreadySubmitted
                                            ? "Update Attendance Session"
                                            : "Submit Attendance Session"}
                                    </Button>
                                </div>
                            </div>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
