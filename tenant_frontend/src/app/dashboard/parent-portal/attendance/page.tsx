"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useChildAttendance, useLinkedChildren } from "@/hooks/useParentPortal";
import { AttendanceStatus } from "@/types/ParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";

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

    const { data, isLoading } = useChildAttendance(selectedChildId, startDate, endDate);

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
                    <label className="text-xs font-medium text-slate-500 mb-1 block">From</label>
                    <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                </div>
                <div className="w-44">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">To</label>
                    <Input type="date" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
                </div>
            </div>

            {!selectedChildId ? (
                <div className="py-16 text-center text-sm text-slate-500">
                    {children && children.length === 0
                        ? "No children are linked to your account yet."
                        : "Select a child to view their attendance."}
                </div>
            ) : isLoading ? (
                <div className="flex items-center justify-center py-20">
                    <LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" />
                </div>
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
                        <div className="py-16 text-center text-sm text-slate-500">No attendance records found.</div>
                    ) : (
                        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 dark:bg-slate-900">
                                    <tr className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                        <th className="px-4 py-3">Date</th>
                                        <th className="px-4 py-3">Status</th>
                                        <th className="px-4 py-3">Remarks</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.records.map((r, i) => (
                                        <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                                            <td className="px-4 py-2">{r.date}</td>
                                            <td className="px-4 py-2">{STATUS_LABELS[r.status] ?? r.status}</td>
                                            <td className="px-4 py-2 text-slate-500">{r.remarks || "—"}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </>
            ) : null}
        </div>
    );
}
