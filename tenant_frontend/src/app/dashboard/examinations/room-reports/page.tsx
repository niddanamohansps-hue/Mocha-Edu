"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useRoomReports } from "@/hooks/useExamAllocation";
import { useExaminations } from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function RoomReportsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("manage_exam_allocation")) return <Unauthorized />;
    return <Content />;
}

function Content() {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const [examinationId, setExaminationId] = useState("");
    const { data = [], isLoading } = useRoomReports(examinationId || undefined);
    const waiting = data.filter((r) => !r.submitted).length;
    const mismatched = data.filter((r) => r.submitted && r.difference !== 0).length;

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Room reports</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    After each sitting the invigilator reports how many answer scripts were collected. See which rooms have not
                    reported, where the count does not match, and any incidents.
                </p>
            </div>
            <select className={selectClass} value={examinationId} onChange={(e) => setExaminationId(e.target.value)}>
                <option value="">Choose an examination</option>
                {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
            </select>
            {!examinationId ? (
                <EmptyState title="Choose an examination" description="Its rooms will be listed here." />
            ) : isLoading ? (
                <LoadingState />
            ) : data.length === 0 ? (
                <EmptyState title="No rooms yet" description="Allocate rooms for this examination first." />
            ) : (
                <>
                    <p className="text-sm text-slate-500">{data.length} rooms, {waiting} not reported, {mismatched} with a count that does not match.</p>
                    <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
                        {data.map((r) => (
                            <li key={`${r.sitting}-${r.room_id}`} className="space-y-1 px-4 py-3">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                    <span>
                                        <span className="font-medium">{r.room}</span>{" "}
                                        <span className="text-xs text-slate-400">{r.date}, {r.start_time.slice(0, 5)} to {r.end_time.slice(0, 5)}</span>
                                    </span>
                                    <span className="flex items-center gap-2 text-sm">
                                        {!r.submitted ? (
                                            <Badge variant="outline">Not reported</Badge>
                                        ) : r.difference === 0 ? (
                                            <Badge>{r.scripts_collected} of {r.expected} scripts</Badge>
                                        ) : (
                                            <Badge variant="destructive">{r.scripts_collected} of {r.expected} scripts</Badge>
                                        )}
                                        {r.has_incidents && <Badge variant="secondary">Incident</Badge>}
                                    </span>
                                </div>
                                {r.has_incidents && <p className="text-sm text-slate-600 dark:text-slate-300">{r.incidents}</p>}
                            </li>
                        ))}
                    </ul>
                </>
            )}
        </div>
    );
}
