"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useMemo, useState } from "react";
import { LoaderCircle, CheckCheck, Lock } from "lucide-react";
import { useSections } from "@/hooks/useAcademics";
import {
    useSectionRoster,
    useSubmitAttendanceSession,
    useUpdateAttendanceSession,
} from "@/hooks/useAttendance";
import { AttendanceStatus } from "@/types/Attendance";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { AttendanceHolidayAdvisory } from "@/components/dashboard/attendance/AttendanceHolidayAdvisory";

const STATUS_OPTIONS: { value: AttendanceStatus; label: string }[] = [
    { value: "present", label: "Present" },
    { value: "absent", label: "Absent" },
    { value: "late", label: "Late" },
    { value: "half_day", label: "Half Day" },
    { value: "leave", label: "Leave" },
];

function todayISO() {
    return new Date().toISOString().slice(0, 10);
}

export default function MarkAttendancePage() {
    const { can, isOwner } = usePermissions();
    const canMark = isOwner || can("mark_attendance");

    const { data: sections, isLoading: loadingSections } = useSections();
    const [sectionId, setSectionId] = useState<string>("");
    const [date, setDate] = useState<string>(todayISO());
    const [marks, setMarks] = useState<Record<string, { status: AttendanceStatus; remarks: string }>>({});

    const { data: roster, isLoading: loadingRoster, isFetching, isError: rosterError, refetch: refetchRoster } = useSectionRoster(sectionId || undefined, date);
    const { mutate: submitSession, isPending: isSubmitting } = useSubmitAttendanceSession();
    const { mutate: updateSession, isPending: isUpdating } = useUpdateAttendanceSession();

    const isLocked = !!roster?.session?.is_locked;
    const alreadySubmitted = !!roster?.session;

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

    const markAllPresent = () => {
        setMarks((prev) => {
            const next = { ...prev };
            for (const key of Object.keys(next)) {
                next[key] = { ...next[key], status: "present" };
            }
            return next;
        });
    };

    const handleSubmit = () => {
        if (!roster) return;
        const records = roster.students.map((s) => ({
            student: s.student,
            status: marks[s.student]?.status ?? "present",
            remarks: marks[s.student]?.remarks ?? "",
        }));

        if (roster.session) {
            updateSession({ sessionId: roster.session.id, records });
        } else {
            submitSession({ section: sectionId, date, records });
        }
    };

    if (!canMark) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Mark Attendance</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Select a section and date to record today's attendance
                </p>
            </div>

            <div className="flex flex-wrap gap-4 items-end">
                <div className="w-64">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Section</label>
                    <Select value={sectionId} onValueChange={setSectionId} disabled={loadingSections}>
                        <SelectTrigger>
                            <SelectValue placeholder="Select a section" />
                        </SelectTrigger>
                        <SelectContent>
                            {sections?.map((s) => (
                                <SelectItem key={s.id} value={s.id}>
                                    {s.level_name} - {s.name}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="w-48">
                    <label htmlFor="f-date" className="text-xs font-medium text-slate-500 mb-1 block">Date</label>
                    <Input id="f-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                </div>
                {roster && roster.students.length > 0 && (
                    <Button variant="outline" onClick={markAllPresent} className="gap-2">
                        <CheckCheck className="h-4 w-4" />
                        Mark all present
                    </Button>
                )}
            </div>

            {/* Holiday & School Closure Advisory Banner */}
            <AttendanceHolidayAdvisory date={date} />

            {!sectionId && (
                <EmptyState title="Choose a section above to load its roster." className="py-16 text-slate-500 text-sm" />
            )}

            {sectionId && (loadingRoster || isFetching) && <LoadingState className="py-20" />}

            {sectionId && rosterError && !loadingRoster && <ErrorState onRetry={refetchRoster} />}

            {sectionId && roster && !loadingRoster && (
                <>
                    {isLocked && (
                        <div className="flex items-center gap-2 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 text-sm font-medium px-4 py-3 rounded-xl">
                            <Lock className="h-4 w-4" />
                            This attendance session is locked and cannot be edited from here.
                        </div>
                    )}

                    {roster.students.length === 0 ? (
                        <EmptyState title="No students are currently enrolled in this section." className="py-16 text-slate-500 text-sm" />
                    ) : (
                        <ResponsiveList
                            rows={roster.students}
                            rowKey={(s) => s.student}
                            columns={[
                                { key: "student", header: "Student", primary: true, cell: (s) => s.full_name },
                                { key: "enrollment", header: "Enrollment ID", className: "text-slate-500", cell: (s) => s.enrollment_id },
                                {
                                    key: "status",
                                    header: "Attendance Status",
                                    className: "w-60",
                                    cell: (s) => {
                                        const currentStatus = marks[s.student]?.status ?? "present";
                                        return (
                                            <div className="flex items-center gap-1.5">
                                                <button
                                                    type="button"
                                                    disabled={isLocked}
                                                    onClick={() =>
                                                        setMarks((prev) => ({
                                                            ...prev,
                                                            [s.student]: { ...prev[s.student], status: "present" },
                                                        }))
                                                    }
                                                    className={`px-2.5 py-1 text-xs rounded-lg transition font-semibold cursor-pointer ${
                                                        currentStatus === "present"
                                                            ? "bg-emerald-600 text-white shadow-xs"
                                                            : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100 dark:bg-emerald-950/40 dark:text-emerald-300"
                                                    }`}
                                                >
                                                    Present
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={isLocked}
                                                    onClick={() =>
                                                        setMarks((prev) => ({
                                                            ...prev,
                                                            [s.student]: { ...prev[s.student], status: "absent" },
                                                        }))
                                                    }
                                                    className={`px-2.5 py-1 text-xs rounded-lg transition font-semibold cursor-pointer ${
                                                        currentStatus === "absent"
                                                            ? "bg-rose-600 text-white shadow-xs"
                                                            : "bg-rose-50 text-rose-700 hover:bg-rose-100 dark:bg-rose-950/40 dark:text-rose-300"
                                                    }`}
                                                >
                                                    Absent
                                                </button>
                                                <button
                                                    type="button"
                                                    disabled={isLocked}
                                                    onClick={() =>
                                                        setMarks((prev) => ({
                                                            ...prev,
                                                            [s.student]: { ...prev[s.student], status: "late" },
                                                        }))
                                                    }
                                                    className={`px-2.5 py-1 text-xs rounded-lg transition font-semibold cursor-pointer ${
                                                        currentStatus === "late"
                                                            ? "bg-amber-600 text-white shadow-xs"
                                                            : "bg-amber-50 text-amber-700 hover:bg-amber-100 dark:bg-amber-950/40 dark:text-amber-300"
                                                    }`}
                                                >
                                                    Late
                                                </button>
                                            </div>
                                        );
                                    },
                                },
                                {
                                    key: "remarks",
                                    header: "Remarks",
                                    cell: (s) => (
                                        <Input
                                            aria-label={`Remarks for ${s.full_name}`}
                                            className="h-9"
                                            placeholder="Optional"
                                            disabled={isLocked}
                                            value={marks[s.student]?.remarks ?? ""}
                                            onChange={(e) =>
                                                setMarks((prev) => ({
                                                    ...prev,
                                                    [s.student]: { ...prev[s.student], remarks: e.target.value },
                                                }))
                                            }
                                        />
                                    ),
                                },
                            ]}
                        />
                    )}

                    {roster.students.length > 0 && (
                        <div className="flex justify-end">
                            <Button
                                onClick={handleSubmit}
                                disabled={isLocked || isSubmitting || isUpdating}
                                className="gap-2"
                            >
                                {(isSubmitting || isUpdating) && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                {alreadySubmitted ? "Update Attendance" : "Submit Attendance"}
                            </Button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
