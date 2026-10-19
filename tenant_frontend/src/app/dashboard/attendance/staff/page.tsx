"use client";

import { useState } from "react";
import { LoaderCircle, CheckCheck } from "lucide-react";
import { useStaffMembers } from "@/hooks/useStaff";
import { useSubmitStaffAttendance } from "@/hooks/useAttendance";
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

export default function StaffAttendancePage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("mark_staff_attendance")) {
        return <Unauthorized />;
    }

    // This screen marks attendance for the whole staff roster at once, so
    // it needs the full list rather than one page of it - pageSize is set
    // to the backend's maximum (100).
    const { data: staffData, isLoading, isError, refetch } = useStaffMembers({ pageSize: 100 });
    const staffMembers = staffData?.results;
    const [date, setDate] = useState(todayISO());
    const [marks, setMarks] = useState<Record<string, AttendanceStatus>>({});
    const { mutate: submit, isPending } = useSubmitStaffAttendance();

    const markAllPresent = () => {
        if (!staffMembers) return;
        const next: Record<string, AttendanceStatus> = {};
        for (const s of staffMembers) next[s.id] = "present";
        setMarks(next);
    };

    const handleSubmit = () => {
        if (!staffMembers) return;
        const records = staffMembers.map((s: any) => ({
            staff: s.id,
            status: marks[s.id] ?? "present",
        }));
        submit({ date, records });
    };

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Staff Attendance</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Manually record daily attendance for staff members
                </p>
            </div>

            <div className="flex flex-wrap gap-4 items-end">
                <div className="w-48">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Date</label>
                    <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                </div>
                {staffMembers && staffMembers.length > 0 && (
                    <Button variant="outline" onClick={markAllPresent} className="gap-2">
                        <CheckCheck className="h-4 w-4" />
                        Mark all present
                    </Button>
                )}
            </div>

            {/* Holiday & School Closure Advisory Banner */}
            <AttendanceHolidayAdvisory date={date} />

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !staffMembers || staffMembers.length === 0 ? (
                <EmptyState title="No staff members found." className="py-16 text-slate-500 text-sm" />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 dark:bg-slate-900">
                            <tr className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                <th className="px-4 py-3">Staff Member</th>
                                <th className="px-4 py-3">Employee ID</th>
                                <th className="px-4 py-3 w-40">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {staffMembers.map((s: any) => (
                                <tr key={s.id} className="border-t border-slate-100 dark:border-slate-800">
                                    <td className="px-4 py-2 font-medium">
                                        {s.profile_details?.first_name} {s.profile_details?.last_name}
                                    </td>
                                    <td className="px-4 py-2 text-slate-500">{s.employee_id}</td>
                                    <td className="px-4 py-2">
                                        <Select
                                            value={marks[s.id] ?? "present"}
                                            onValueChange={(v) => setMarks((prev) => ({ ...prev, [s.id]: v as AttendanceStatus }))}
                                        >
                                            <SelectTrigger className="h-9">
                                                <SelectValue />
                                            </SelectTrigger>
                                            <SelectContent>
                                                {STATUS_OPTIONS.map((opt) => (
                                                    <SelectItem key={opt.value} value={opt.value}>
                                                        {opt.label}
                                                    </SelectItem>
                                                ))}
                                            </SelectContent>
                                        </Select>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            {staffMembers && staffMembers.length > 0 && (
                <div className="flex justify-end">
                    <Button onClick={handleSubmit} disabled={isPending} className="gap-2">
                        {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                        Submit Attendance
                    </Button>
                </div>
            )}
        </div>
    );
}
