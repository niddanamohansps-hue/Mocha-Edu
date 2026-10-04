"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { LoaderCircle, Lock } from "lucide-react";
import axiosInstance from "@/lib/axios";
import { useExaminations, useExamSchedules, useSubmitExamMarks } from "@/hooks/useExaminations";
import { ExamMark } from "@/types/Examinations";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function MarksEntryPage() {
    const { can, isOwner } = usePermissions();
    const canEnter = isOwner || can("enter_marks");

    const { data: examinations } = useExaminations();
    const [examinationId, setExaminationId] = useState("");
    const { data: schedules } = useExamSchedules(examinationId || undefined);
    const [scheduleId, setScheduleId] = useState("");

    const schedule = schedules?.find((s) => s.id === scheduleId);

    const { data: roster, isLoading: loadingRoster, isError: rosterError, refetch: refetchRoster } = useQuery({
        queryKey: ["examinations", "roster", scheduleId],
        queryFn: async () => {
            // The section roster - reuses the same active-students-in-section
            // data already exposed for Attendance's roster endpoint's
            // underlying students, via the schedule's own section marks
            // response once entered. For a schedule with no marks yet we
            // still need a roster: derive it from the attendance roster
            // endpoint for this section, which already excludes inactive
            // students - matching the same eligibility rule as the backend.
            const response = await axiosInstance.get(
                `/attendance/sections/${schedule?.section}/roster/?date=${schedule?.date}`
            );
            return response.data.students as { student: string; full_name: string; enrollment_id: string }[];
        },
        enabled: !!schedule,
    });

    const [marks, setMarks] = useState<Record<string, { marks_obtained: string; is_absent: boolean; remarks: string }>>({});
    const { mutate: submitMarks, isPending } = useSubmitExamMarks();

    useEffect(() => {
        if (!roster) return;
        const initial: typeof marks = {};
        for (const s of roster) {
            initial[s.student] = { marks_obtained: "", is_absent: false, remarks: "" };
        }
        setMarks(initial);
    }, [roster]);

    const handleSubmit = () => {
        if (!schedule) return;
        const records = Object.entries(marks).map(([student, m]) => ({
            student,
            marks_obtained: m.is_absent || m.marks_obtained === "" ? null : Number(m.marks_obtained),
            is_absent: m.is_absent,
            remarks: m.remarks,
        }));
        submitMarks({ scheduleId: schedule.id, records });
    };

    if (!canEnter) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Marks Entry</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Only schedules you are assigned to teach are shown below
                </p>
            </div>

            <div className="flex flex-wrap gap-4 items-end">
                <div className="w-64">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Examination</label>
                    <Select value={examinationId} onValueChange={(v) => { setExaminationId(v); setScheduleId(""); }}>
                        <SelectTrigger><SelectValue placeholder="Select examination" /></SelectTrigger>
                        <SelectContent>
                            {examinations?.map((e) => <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>)}
                        </SelectContent>
                    </Select>
                </div>
                <div className="w-72">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Schedule</label>
                    <Select value={scheduleId} onValueChange={setScheduleId} disabled={!examinationId}>
                        <SelectTrigger><SelectValue placeholder={schedules?.length ? "Select schedule" : "No assigned schedules"} /></SelectTrigger>
                        <SelectContent>
                            {schedules?.map((s) => (
                                <SelectItem key={s.id} value={s.id}>{s.subject_name} - {s.section_name}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
            </div>

            {schedule?.is_locked && (
                <div className="flex items-center gap-2 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 text-sm font-medium px-4 py-3 rounded-xl">
                    <Lock className="h-4 w-4" /> This schedule is locked - marks cannot be edited.
                </div>
            )}

            {scheduleId && loadingRoster && <LoadingState className="py-16" />}

            {scheduleId && rosterError && !loadingRoster && <ErrorState onRetry={refetchRoster} />}

            {scheduleId && roster && roster.length === 0 && (
                <EmptyState title="No students are currently enrolled in this section." className="py-16 text-slate-500 text-sm" />
            )}

            {scheduleId && roster && roster.length > 0 && schedule && (
                <>
                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 dark:bg-slate-900">
                                <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                    <th className="px-4 py-3">Student</th>
                                    <th className="px-4 py-3">Marks (/{schedule.max_marks})</th>
                                    <th className="px-4 py-3">Absent</th>
                                    <th className="px-4 py-3">Remarks</th>
                                </tr>
                            </thead>
                            <tbody>
                                {roster.map((s) => (
                                    <tr key={s.student} className="border-t border-slate-100 dark:border-slate-800">
                                        <td className="px-4 py-2 font-medium">{s.full_name} <span className="text-slate-400 text-xs">({s.enrollment_id})</span></td>
                                        <td className="px-4 py-2">
                                            <Input
                                                type="number" className="h-9 w-24" disabled={schedule.is_locked || marks[s.student]?.is_absent}
                                                value={marks[s.student]?.marks_obtained ?? ""}
                                                onChange={(e) => setMarks((prev) => ({ ...prev, [s.student]: { ...prev[s.student], marks_obtained: e.target.value } }))}
                                            />
                                        </td>
                                        <td className="px-4 py-2">
                                            <Checkbox
                                                checked={marks[s.student]?.is_absent ?? false} disabled={schedule.is_locked}
                                                onCheckedChange={(v) => setMarks((prev) => ({ ...prev, [s.student]: { ...prev[s.student], is_absent: !!v } }))}
                                            />
                                        </td>
                                        <td className="px-4 py-2">
                                            <Input
                                                className="h-9" disabled={schedule.is_locked} placeholder="Optional"
                                                value={marks[s.student]?.remarks ?? ""}
                                                onChange={(e) => setMarks((prev) => ({ ...prev, [s.student]: { ...prev[s.student], remarks: e.target.value } }))}
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    <div className="flex justify-end">
                        <Button onClick={handleSubmit} disabled={schedule.is_locked || isPending} className="gap-2">
                            {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                            Submit Marks
                        </Button>
                    </div>
                </>
            )}
        </div>
    );
}
