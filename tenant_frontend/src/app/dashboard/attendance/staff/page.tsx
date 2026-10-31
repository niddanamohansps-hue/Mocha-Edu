"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
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
    return <StaffAttendancePageContent />;
}

function StaffAttendancePageContent() {
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
        const records = staffMembers.map((s) => ({
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
                    <label htmlFor="f-date" className="text-xs font-medium text-slate-500 mb-1 block">Date</label>
                    <Input id="f-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
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
                <ResponsiveList
                    rows={staffMembers}
                    rowKey={(s) => s.id}
                    columns={[
                        {
                            key: "staff",
                            header: "Staff Member",
                            primary: true,
                            cell: (s) => `${s.profile_details?.first_name ?? ""} ${s.profile_details?.last_name ?? ""}`,
                        },
                        { key: "employee", header: "Employee ID", className: "text-slate-500", cell: (s) => s.employee_id },
                        {
                            key: "status",
                            header: "Status",
                            className: "w-40",
                            cell: (s) => (
                                <Select
                                    value={marks[s.id] ?? "present"}
                                    onValueChange={(v) => setMarks((prev) => ({ ...prev, [s.id]: v as AttendanceStatus }))}
                                >
                                    <SelectTrigger
                                        className="h-9 w-full"
                                        aria-label={`Attendance status for ${s.profile_details?.first_name ?? ""} ${s.profile_details?.last_name ?? ""}`}
                                    >
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
                            ),
                        },
                    ]}
                />
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
