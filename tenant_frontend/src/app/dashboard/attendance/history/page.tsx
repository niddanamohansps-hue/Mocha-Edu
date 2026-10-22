"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useState } from "react";
import { useMe } from "@/hooks/useAuth";
import { useStudentAttendanceHistory } from "@/hooks/useAttendance";
import { usePermissions } from "@/providers/PermissionProvider";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const STATUS_LABELS: Record<string, string> = {
    present: "Present",
    absent: "Absent",
    late: "Late",
    half_day: "Half Day",
    leave: "Leave",
};

export default function AttendanceHistoryPage() {
    const { data: user } = useMe();
    const { activeRole } = usePermissions();
    const isStudent = activeRole === "student";

    const [studentId, setStudentId] = useState<string>(isStudent ? user?.profile?.student_id ?? "" : "");
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const effectiveStudentId = isStudent ? user?.profile?.student_id ?? undefined : studentId || undefined;
    const { data, isLoading, isError, refetch } = useStudentAttendanceHistory(effectiveStudentId, startDate, endDate);

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Attendance History</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {isStudent ? "Your attendance record" : "View a student's attendance record"}
                </p>
            </div>

            <div className="flex flex-wrap gap-4 items-end">
                {!isStudent && (
                    <div className="w-72">
                        <label htmlFor="f-student-id" className="text-xs font-medium text-slate-500 mb-1 block">Student ID</label>
                        <Input id="f-student-id"
                            placeholder="Paste a student ID"
                            value={studentId}
                            onChange={(e) => setStudentId(e.target.value)}
                        />
                    </div>
                )}
                <div className="w-44">
                    <label htmlFor="f-from" className="text-xs font-medium text-slate-500 mb-1 block">From</label>
                    <Input id="f-from" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </div>
                <div className="w-44">
                    <label htmlFor="f-to" className="text-xs font-medium text-slate-500 mb-1 block">To</label>
                    <Input id="f-to" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </div>
            </div>

            {!effectiveStudentId && (
                <EmptyState
                    title={isStudent ? "No student record linked to your account yet." : "Enter a student ID to view their history."}
                    className="py-16 text-slate-500 text-sm"
                />
            )}

            {effectiveStudentId && isLoading && <LoadingState className="py-20" />}

            {effectiveStudentId && isError && <ErrorState onRetry={refetch} />}

            {effectiveStudentId && data && (
                <>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
                        <Card className="border-none shadow-md">
                            <CardContent className="p-4">
                                <p className="text-xs text-slate-500 uppercase font-bold">Percentage</p>
                                <p className="text-2xl font-black">
                                    {data.percentage !== null ? `${data.percentage}%` : "—"}
                                </p>
                            </CardContent>
                        </Card>
                        {Object.entries(STATUS_LABELS).map(([key, label]) => (
                            <Card key={key} className="border-none shadow-md">
                                <CardContent className="p-4">
                                    <p className="text-xs text-slate-500 uppercase font-bold">{label}</p>
                                    <p className="text-2xl font-black">{(data.counts as any)[key] ?? 0}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {data.records.length === 0 ? (
                        <EmptyState title="No attendance records found." className="py-16 text-slate-500 text-sm" />
                    ) : (
                        <ResponsiveList
                            rows={data.records}
                            rowKey={(r, i) => String(i)}
                            columns={[
                                { key: "date", header: "Date", primary: true, cell: (r) => r.date },
                                { key: "status", header: "Status", cell: (r) => STATUS_LABELS[r.status] ?? r.status },
                                { key: "remarks", header: "Remarks", className: "text-slate-500", cell: (r) => r.remarks || "—" },
                            ]}
                        />
                    )}
                </>
            )}
        </div>
    );
}
