"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useRoomReport, useSubmitRoomReport } from "@/hooks/useExamAllocation";
import type { RoomReport } from "@/types/ExamAllocation";

export default function RoomReportPage() {
    return (
        <Suspense fallback={<LoadingState />}>
            <RoomReportContent />
        </Suspense>
    );
}

function RoomReportContent() {
    const params = useSearchParams();
    const sitting = params.get("sitting");
    const room = params.get("room");
    const { data, isLoading, isError } = useRoomReport(sitting, room);
    if (!sitting || !room) {
        return <EmptyState title="Open this from your duty" description="Choose your duty on the Exam Duties page, then press Room report." />;
    }
    if (isLoading) return <LoadingState />;
    if (isError || !data) {
        return <EmptyState title="You cannot report for this room" description="The report is made by the invigilators on duty in the room." />;
    }
    return <Form key={`${sitting}-${room}`} sitting={sitting} room={room} data={data} />;
}

function Form({ sitting, room, data }: { sitting: string; room: string; data: RoomReport }) {
    const submit = useSubmitRoomReport();
    const [scripts, setScripts] = useState(data.scripts_collected === null ? "" : String(data.scripts_collected));
    const [incidents, setIncidents] = useState(data.incidents);
    const n = scripts === "" ? null : Number(scripts);
    const difference = n === null || Number.isNaN(n) ? null : n - data.expected;

    return (
        <div className="max-w-xl mx-auto space-y-5">
            <div className="space-y-1">
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Room report</h1>
                <p className="text-sm text-slate-500">
                    {data.seated} students were seated and {data.absent} marked absent, so {data.expected} answer scripts are expected.
                    {data.submitted && ` Last reported by ${data.submitted_by}.`}
                </p>
            </div>
            <div className="grid gap-1.5">
                <Label>Answer scripts collected</Label>
                <Input type="number" min={0} className="w-40" value={scripts} onChange={(e) => setScripts(e.target.value)} />
                {difference !== null && difference !== 0 && (
                    <p className="text-sm text-amber-700 dark:text-amber-400">
                        {difference < 0 ? `${-difference} fewer` : `${difference} more`} than expected. Please check before you submit.
                    </p>
                )}
            </div>
            <div className="grid gap-1.5">
                <Label>Incidents (optional)</Label>
                <textarea
                    className="min-h-28 rounded-md border border-slate-200 bg-white p-3 text-sm dark:border-slate-800 dark:bg-slate-950"
                    placeholder="Anything that went wrong: a student unwell, a torn paper, a phone found..."
                    value={incidents}
                    onChange={(e) => setIncidents(e.target.value)}
                />
            </div>
            <Button
                disabled={submit.isPending || n === null || Number.isNaN(n)}
                onClick={() => submit.mutate({ sitting, room, scripts_collected: n as number, incidents })}
            >
                {submit.isPending ? "Saving..." : data.submitted ? "Update report" : "Submit report"}
            </Button>
        </div>
    );
}
