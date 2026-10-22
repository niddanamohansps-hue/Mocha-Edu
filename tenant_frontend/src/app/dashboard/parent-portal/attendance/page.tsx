"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useState } from "react";
import { useChildAttendance, useLinkedChildren } from "@/hooks/useParentPortal";
import { AttendanceStatus } from "@/types/ParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const STATUS_LABELS: Record<AttendanceStatus, string> = {
    present: "Present",
    absent: "Absent",
    late: "Late",
    half_day: "Half Day",
    leave: "Leave",
};

export default function ParentPortalAttendancePage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_child_attendance");

    const { data: children } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");

    const { data, isLoading, isError, refetch } = useChildAttendance(selectedChildId, startDate, endDate);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Child Attendance</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Attendance history for your selected child
                </p>
            </div>

            <div className="flex flex-wrap gap-4 items-end">
                <ChildSwitcher
                    childOptions={children || []}
                    selectedId={selectedChildId}
                    onChange={setSelectedChildId}
                />
                <div className="w-44">
                    <label htmlFor="f-from" className="text-xs font-medium text-slate-500 mb-1 block">From</label>
                    <Input id="f-from" type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </div>
                <div className="w-44">
                    <label htmlFor="f-to" className="text-xs font-medium text-slate-500 mb-1 block">To</label>
                    <Input id="f-to" type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </div>
            </div>

            {!selectedChildId ? (
                <EmptyState
                    title={
                        children && children.length === 0
                            ? "No children are linked to your account yet."
                            : "Select a child to view their attendance."
                    }
                    className="py-16 text-slate-500 text-sm"
                />
            ) : isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : data ? (
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
                        {(Object.entries(STATUS_LABELS) as [AttendanceStatus, string][]).map(([key, label]) => (
                            <Card key={key} className="border-none shadow-md">
                                <CardContent className="p-4">
                                    <p className="text-xs text-slate-500 uppercase font-bold">{label}</p>
                                    <p className="text-2xl font-black">{data.counts[key] ?? 0}</p>
                                </CardContent>
                            </Card>
                        ))}
                    </div>

                    {data.records.length === 0 ? (
                        <EmptyState title="No attendance records found." className="py-16 text-slate-500 text-sm" />
                    ) : (
                        <ResponsiveList
                            rows={data.records}
                            rowKey={(r) => `${r.date}-${r.status}`}
                            columns={[
                                { key: "date", header: "Date", primary: true, cell: (r) => r.date },
                                { key: "status", header: "Status", cell: (r) => STATUS_LABELS[r.status] ?? r.status },
                                { key: "remarks", header: "Remarks", className: "text-slate-500", cell: (r) => r.remarks || "—" },
                            ]}
                        />
                    )}
                </>
            ) : null}
        </div>
    );
}
