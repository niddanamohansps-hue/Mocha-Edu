"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useHallAttendance, useSaveHallAttendance } from "@/hooks/useExamAllocation";
import type { HallRow } from "@/types/ExamAllocation";

const time = (t: string) => t.slice(0, 5);

export default function HallAttendancePage() {
    return (
        <Suspense fallback={<LoadingState />}>
            <HallAttendanceContent />
        </Suspense>
    );
}

function HallAttendanceContent() {
    const params = useSearchParams();
    const sitting = params.get("sitting");
    const room = params.get("room");
    const { data, isLoading, isError } = useHallAttendance(sitting, room);

    if (!sitting || !room) {
        return <EmptyState title="Open this from your duty" description="Choose your duty on the Exam Duties page, then press Take attendance." />;
    }
    if (isLoading) return <LoadingState />;
    if (isError || !data) {
        return <EmptyState title="You cannot take attendance here" description="Attendance can be taken by the invigilators on duty in this room." />;
    }
    return <Sheet key={`${sitting}-${room}`} sitting={sitting} room={room} data={data} />;
}

function Sheet({ sitting, room, data }: { sitting: string; room: string; data: import("@/types/ExamAllocation").HallAttendance }) {
    const save = useSaveHallAttendance();
    // What the invigilator has chosen so far, on top of what is already saved.
    const [choices, setChoices] = useState<Record<string, "present" | "absent">>({});
    const statusOf = (row: HallRow) => choices[row.student_id] || row.status;
    const marked = data.rows.filter((r) => statusOf(r)).length;
    const absent = data.rows.filter((r) => statusOf(r) === "absent").length;
    const [conflicts, setConflicts] = useState<{ student_id: string; name: string; problem: string }[]>([]);

    const set = (row: HallRow, status: "present" | "absent") => setChoices((c) => ({ ...c, [row.student_id]: status }));

    return (
        <div className="max-w-2xl mx-auto space-y-5">
            <div className="space-y-1">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Room {data.room.name}: attendance</h1>
                <p className="text-sm text-slate-500">
                    {data.sitting.examination}, {data.sitting.date}, {time(data.sitting.start_time)} to {time(data.sitting.end_time)}. Mark who is
                    sitting the paper. Students marked absent are put on the marks sheet as absent.
                </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
                <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setChoices((current) => ({ ...current, ...Object.fromEntries(data.rows.filter((r) => !statusOf(r)).map((r) => [r.student_id, "present" as const])) }))}
                >
                    Mark everyone not yet marked as present
                </Button>
                <span className="text-sm text-slate-500">{marked} of {data.rows.length} marked, {absent} absent</span>
            </div>

            <ul className="divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-900">
                {data.rows.map((row) => {
                    const status = statusOf(row);
                    return (
                        <li key={row.student_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                            <span>
                                <span className="mr-2 inline-block w-7 text-right font-mono text-slate-400">{row.seat}</span>
                                <span className="font-medium">{row.name}</span>{" "}
                                <span className="text-xs text-slate-400">{row.class} - {row.subject}</span>
                            </span>
                            <span className="flex gap-2">
                                <Button size="sm" variant={status === "present" ? "default" : "outline"} onClick={() => set(row, "present")}>Present</Button>
                                <Button size="sm" variant={status === "absent" ? "destructive" : "outline"} onClick={() => set(row, "absent")}>Absent</Button>
                            </span>
                        </li>
                    );
                })}
            </ul>

            {conflicts.length > 0 && (
                <div className="space-y-1 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/30 dark:text-amber-300">
                    <p className="font-medium">Saved, but the marks sheet was not changed for:</p>
                    {conflicts.map((c) => <p key={c.student_id}><Badge variant="outline">{c.name}</Badge> {c.problem}</p>)}
                </div>
            )}

            <Button
                disabled={save.isPending || Object.keys(choices).length === 0}
                onClick={() =>
                    save.mutate(
                        { sitting, room, records: Object.entries(choices).map(([student, status]) => ({ student, status })) },
                        { onSuccess: (result) => { setConflicts(result.conflicts); setChoices({}); } },
                    )
                }
            >
                {save.isPending ? "Saving..." : "Save attendance"}
            </Button>
        </div>
    );
}
