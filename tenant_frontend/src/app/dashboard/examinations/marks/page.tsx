"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { History, LoaderCircle, Lock, Upload } from "lucide-react";
import axiosInstance from "@/lib/axios";
import {
    importErrors, useExaminations, useExamSchedules, useImportMarks, useMarksHistory, useRequestRecheck, useScheduleMarks,
    useSetGrace, useSubmitExamMarks,
} from "@/hooks/useExaminations";
import { ATTENDANCE_LABELS, MarkAttendance, MarksImportResult, SavedMark } from "@/types/Examinations";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Field, FormDialog, SELECT_CLASS, formatDateTime } from "@/components/dashboard/inventory/shared";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

type Row = { marks_obtained: string; attendance: MarkAttendance; remarks: string; components?: Record<string, string> };

const TEXTAREA = "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm min-h-[70px]";

function GraceDialog({ mark, max, onClose }: { mark: SavedMark; max: string; onClose: () => void }) {
    const setGrace = useSetGrace();
    const [grace, setGraceValue] = useState(Number(mark.grace_marks) ? String(Number(mark.grace_marks)) : "");
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    const room = Number(max) - Number(mark.marks_obtained ?? 0);
    return (
        <FormDialog
            open onOpenChange={(o) => !o && onClose()}
            title={`Grace marks: ${mark.student_name}`}
            description={`Marks ${Number(mark.marks_obtained)} of ${Number(max)}. At most ${room} grace marks fit. 0 removes them.`}
            submitLabel="Save" pending={setGrace.isPending} error={error}
            onSubmit={() => {
                if (!/^\d+(\.\d{1,2})?$/.test(grace.trim())) return setError("Enter grace marks as a number.");
                if (Number(grace) > room) return setError(`At most ${room} grace marks fit under the maximum.`);
                if (!reason.trim()) return setError("Give a reason; it is kept with the mark's history.");
                setError(null);
                setGrace.mutate({ markId: mark.id, grace_marks: grace.trim(), reason: reason.trim() }, { onSuccess: onClose });
            }}
        >
            <Field label="Grace marks" htmlFor="gr-marks"><Input id="gr-marks" inputMode="decimal" value={grace} onChange={(e) => setGraceValue(e.target.value)} /></Field>
            <Field label="Reason" htmlFor="gr-reason"><textarea id="gr-reason" className={TEXTAREA} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        </FormDialog>
    );
}

function RecheckDialog({ mark, onClose }: { mark: SavedMark; onClose: () => void }) {
    const ask = useRequestRecheck();
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open onOpenChange={(o) => !o && onClose()}
            title={`Ask for a recheck: ${mark.student_name}`}
            description="Someone who manages marks re-checks the answer script and accepts or rejects the request."
            submitLabel="Ask" pending={ask.isPending} error={error}
            onSubmit={() => {
                if (!reason.trim()) return setError("Say what should be re-checked.");
                setError(null);
                ask.mutate({ mark: mark.id, reason: reason.trim() }, { onSuccess: onClose });
            }}
        >
            <Field label="What should be re-checked" htmlFor="rc-reason"><textarea id="rc-reason" className={TEXTAREA} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
        </FormDialog>
    );
}

function ImportDialog({ scheduleId, needsReason, onClose }: { scheduleId: string; needsReason: boolean; onClose: () => void }) {
    const run = useImportMarks();
    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<MarksImportResult | null>(null);
    const [errors, setErrors] = useState<string[]>([]);
    const [reason, setReason] = useState("");
    const send = (dryRun: boolean) => {
        if (!file) return setErrors(["Choose a CSV file."]);
        if (!dryRun && needsReason && !reason.trim()) return setErrors(["This schedule is locked. Give a reason for changing marks."]);
        setErrors([]);
        run.mutate({ scheduleId, file, dryRun, reason: reason.trim() }, {
            onSuccess: (data) => (dryRun ? setPreview(data) : onClose()),
            onError: (e) => { setPreview(null); setErrors(importErrors(e)); },
        });
    };
    return (
        <FormDialog
            open onOpenChange={(o) => !o && onClose()}
            title="Import marks from a CSV file"
            description="Columns: enrollment_id, marks, and optionally attendance (present, absent, medical, malpractice, exempt) and remarks. Check the file first; nothing is saved if any line is wrong."
            submitLabel={preview ? `Import ${preview.total} rows` : "Check the file"} pending={run.isPending}
            error={errors.length ? errors.slice(0, 8).join("\n") + (errors.length > 8 ? `\n...and ${errors.length - 8} more` : "") : null}
            onSubmit={() => send(!preview)}
        >
            <Field label="CSV file" htmlFor="im-file">
                <input id="im-file" type="file" accept=".csv,text/csv" className="text-sm"
                    onChange={(e) => { setFile(e.target.files?.[0] ?? null); setPreview(null); setErrors([]); }} />
            </Field>
            {needsReason && (
                <Field label="Reason for changing locked marks" htmlFor="im-reason"><Input id="im-reason" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            )}
            {preview?.rows && (
                <div className="max-h-56 overflow-y-auto rounded-xl border border-slate-200 dark:border-slate-800 text-sm">
                    {preview.rows.map((r) => (
                        <div key={r.line} className="flex justify-between gap-2 px-3 py-1 border-b border-slate-100 dark:border-slate-800 last:border-0">
                            <span>{r.student_name} <span className="text-xs text-slate-500">({r.enrollment_id})</span></span>
                            <span className="text-slate-600 dark:text-slate-300">{r.attendance === "present" ? (r.marks ?? "not marked") : ATTENDANCE_LABELS[r.attendance]}</span>
                        </div>
                    ))}
                </div>
            )}
        </FormDialog>
    );
}

function HistoryPanel({ scheduleId }: { scheduleId: string }) {
    const { data, isLoading, isError } = useMarksHistory(scheduleId, true);
    if (isLoading) return <LoadingState className="py-6" />;
    if (isError) return <ErrorState message="Could not load the history." />;
    if (!data?.length) return <p className="text-sm text-slate-500">No marks entered yet.</p>;
    const show = (marks: string | null, attendance: string, grace?: string) =>
        attendance && attendance !== "present" ? ATTENDANCE_LABELS[attendance as MarkAttendance] ?? attendance
            : marks === null ? "blank" : `${Number(marks)}${grace && Number(grace) ? ` +${Number(grace)}` : ""}`;
    return (
        <ul className="text-sm space-y-2 max-h-80 overflow-y-auto">
            {data.map((c) => (
                <li key={c.id}>
                    <span className="font-medium">{c.student_name}</span> <span className="text-xs text-slate-500">({c.enrollment_id})</span>:{" "}
                    {c.kind === "entry" ? `entered ${show(c.new_marks, c.new_attendance)}`
                        : c.kind === "grace" ? `grace ${Number(c.old_grace)} → ${Number(c.new_grace)}`
                        : `${c.kind === "recheck" ? "recheck" : c.kind === "import" ? "import" : "changed"} ${show(c.old_marks, c.old_attendance)} → ${show(c.new_marks, c.new_attendance)}`}
                    <span className="block text-xs text-slate-500">
                        {c.changed_by || "someone"}, {formatDateTime(c.created_at)}{c.reason ? ` · ${c.reason}` : ""}
                    </span>
                </li>
            ))}
        </ul>
    );
}

export default function MarksEntryPage() {
    const { can, isOwner } = usePermissions();
    const canEnter = isOwner || can("enter_marks");
    const canManage = isOwner || can("manage_marks");

    const { data: examinations } = useExaminations();
    const [examinationId, setExaminationId] = useState("");
    const { data: schedules } = useExamSchedules(examinationId || undefined);
    const [scheduleId, setScheduleId] = useState("");

    const schedule = schedules?.find((s) => s.id === scheduleId);

    const { data: roster, isLoading: loadingRoster, isError: rosterError, refetch: refetchRoster } = useQuery({
        queryKey: ["examinations", "roster", scheduleId],
        queryFn: async () => {
            // The section's current, active students (the same rule the server applies to marks).
            const response = await axiosInstance.get(
                `/attendance/sections/${schedule?.section}/roster/?date=${schedule?.date}`
            );
            return response.data.students as { student: string; full_name: string; enrollment_id: string }[];
        },
        enabled: !!schedule,
    });
    const saved = useScheduleMarks(scheduleId || undefined);

    const [marks, setMarks] = useState<Record<string, Row>>({});
    const [reason, setReason] = useState("");
    const [grace, setGrace] = useState<SavedMark | null>(null);
    const [recheck, setRecheck] = useState<SavedMark | null>(null);
    const [importing, setImporting] = useState(false);
    const [showHistory, setShowHistory] = useState(false);
    const { mutate: submitMarks, isPending } = useSubmitExamMarks();

    const savedByStudent = Object.fromEntries((saved.data?.marks ?? []).map((m) => [m.student, m]));

    useEffect(() => {
        if (!roster || !saved.data) return;
        const byStudent = Object.fromEntries(saved.data.marks.map((m) => [m.student, m]));
        const initial: Record<string, Row> = {};
        for (const s of roster) {
            const m = byStudent[s.student];
            const compMarksMap: Record<string, string> = {};
            if (m?.component_marks) {
                for (const cm of m.component_marks) {
                    compMarksMap[cm.component] = cm.marks_obtained === null ? "" : String(Number(cm.marks_obtained));
                }
            }
            initial[s.student] = m
                ? {
                    marks_obtained: m.marks_obtained === null ? "" : String(Number(m.marks_obtained)),
                    attendance: m.attendance,
                    remarks: m.remarks,
                    components: compMarksMap,
                }
                : { marks_obtained: "", attendance: "present", remarks: "", components: compMarksMap };
        }
        setMarks(initial);
        setReason("");
    }, [roster, saved.data]);

    const published = !!saved.data?.is_published;
    const locked = !!schedule?.is_locked;
    const editable = !published && (!locked || canManage);
    const needsReason = locked && canManage && !published;

    const update = (student: string, patch: Partial<Row>) => setMarks((prev) => ({ ...prev, [student]: { ...prev[student], ...patch } }));

    const updateComponent = (student: string, componentId: string, val: string) => {
        setMarks((prev) => {
            const studentRow = prev[student] || { marks_obtained: "", attendance: "present", remarks: "", components: {} };
            const updatedComps = { ...(studentRow.components || {}), [componentId]: val };
            const sum = Object.values(updatedComps).reduce((acc, curr) => {
                const num = parseFloat(curr);
                return isNaN(num) ? acc : acc + num;
            }, 0);
            return {
                ...prev,
                [student]: {
                    ...studentRow,
                    components: updatedComps,
                    marks_obtained: Object.values(updatedComps).some((v) => v !== "") ? String(sum) : "",
                },
            };
        });
    };

    const handleSubmit = () => {
        if (!schedule) return;
        const records = Object.entries(marks).map(([student, m]) => ({
            student,
            marks_obtained: m.attendance !== "present" || m.marks_obtained === "" ? null : Number(m.marks_obtained),
            is_absent: ["absent", "medical", "malpractice"].includes(m.attendance),
            attendance: m.attendance,
            remarks: m.remarks,
            components: schedule.components && schedule.components.length > 0 && m.components
                ? Object.entries(m.components).map(([cid, score]) => ({
                    component: cid,
                    marks_obtained: score === "" ? null : Number(score),
                    is_absent: ["absent", "medical", "malpractice"].includes(m.attendance),
                }))
                : undefined,
        }));
        submitMarks({ scheduleId: schedule.id, records, reason: reason.trim() });
    };

    if (!canEnter) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Marks Entry</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Only schedules you are assigned to teach are shown below. Every change is kept with who made it and why.
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
                    <Select value={scheduleId} onValueChange={(v) => { setScheduleId(v); setShowHistory(false); }} disabled={!examinationId}>
                        <SelectTrigger><SelectValue placeholder={schedules?.length ? "Select schedule" : "No assigned schedules"} /></SelectTrigger>
                        <SelectContent>
                            {schedules?.map((s) => (
                                <SelectItem key={s.id} value={s.id}>{s.subject_name} - {s.section_name}</SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                {schedule && (
                    <div className="flex gap-2 ml-auto">
                        {editable && <Button variant="outline" className="gap-2" onClick={() => setImporting(true)}><Upload className="h-4 w-4" /> Import CSV</Button>}
                        <Button variant="outline" className="gap-2" onClick={() => setShowHistory((v) => !v)}><History className="h-4 w-4" /> {showHistory ? "Hide history" : "History"}</Button>
                    </div>
                )}
            </div>

            {published && (
                <div className="flex items-center gap-2 bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-400 text-sm font-medium px-4 py-3 rounded-xl">
                    <Lock className="h-4 w-4" /> Results are published. Marks change only through a recheck or grace marks.
                </div>
            )}
            {!published && locked && (
                <div className="flex items-center gap-2 bg-amber-50 dark:bg-amber-500/10 text-amber-700 dark:text-amber-400 text-sm font-medium px-4 py-3 rounded-xl">
                    <Lock className="h-4 w-4" /> {canManage ? "This schedule is locked. You can still correct marks, with a reason." : "This schedule is locked - marks cannot be edited."}
                </div>
            )}

            {showHistory && scheduleId && (
                <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 space-y-2">
                    <h2 className="font-semibold text-slate-900 dark:text-white">History</h2>
                    <HistoryPanel scheduleId={scheduleId} />
                </section>
            )}

            {scheduleId && (loadingRoster || saved.isLoading) && <LoadingState className="py-16" />}

            {scheduleId && (rosterError || saved.isError) && !loadingRoster && <ErrorState onRetry={() => { refetchRoster(); saved.refetch(); }} />}

            {scheduleId && roster && roster.length === 0 && (
                <EmptyState title="No students are currently enrolled in this section." className="py-16 text-slate-500 text-sm" />
            )}

            {scheduleId && roster && roster.length > 0 && schedule && saved.data && (
                <>
                    <ResponsiveList
                        rows={roster}
                        rowKey={(s) => s.student}
                        columns={[
                            {
                                key: "student",
                                header: "Student",
                                primary: true,
                                cell: (s) => (
                                    <>
                                        {s.full_name} <span className="text-slate-400 text-xs font-normal">({s.enrollment_id})</span>
                                    </>
                                ),
                            },
                            {
                                key: "attendance",
                                header: "Attendance",
                                cell: (s) => (
                                    <select
                                        aria-label={`Attendance of ${s.full_name}`}
                                        className={`${SELECT_CLASS} h-9 w-40`}
                                        disabled={!editable}
                                        value={marks[s.student]?.attendance ?? "present"}
                                        onChange={(e) => update(s.student, { attendance: e.target.value as MarkAttendance })}
                                    >
                                        {(Object.keys(ATTENDANCE_LABELS) as MarkAttendance[]).map((a) => <option key={a} value={a}>{ATTENDANCE_LABELS[a]}</option>)}
                                    </select>
                                ),
                            },
                            ...(schedule.components && schedule.components.length > 0
                                ? schedule.components.map((c) => ({
                                    key: `comp_${c.id}`,
                                    header: `${c.name} (${Number(c.max_marks)})`,
                                    cell: (s: any) => (
                                        <Input
                                            type="number"
                                            inputMode="decimal"
                                            aria-label={`${c.name} marks for ${s.full_name}`}
                                            className="h-9 w-20"
                                            disabled={!editable || marks[s.student]?.attendance !== "present"}
                                            value={marks[s.student]?.components?.[c.id] ?? ""}
                                            onChange={(e) => updateComponent(s.student, c.id, e.target.value)}
                                        />
                                    ),
                                }))
                                : []),
                            {
                                key: "marks",
                                header: schedule.components && schedule.components.length > 0
                                    ? `Total (${Number(schedule.max_marks)})`
                                    : `Marks (out of ${Number(schedule.max_marks)})`,
                                cell: (s) => (
                                    <Input
                                        type="number"
                                        inputMode="decimal"
                                        aria-label={`Marks for ${s.full_name}`}
                                        className="h-9 w-24"
                                        disabled={!editable || marks[s.student]?.attendance !== "present" || (!!schedule.components && schedule.components.length > 0)}
                                        value={marks[s.student]?.marks_obtained ?? ""}
                                        onChange={(e) => update(s.student, { marks_obtained: e.target.value })}
                                    />
                                ),
                            },
                            {
                                key: "grace",
                                header: "Grace",
                                cell: (s) => {
                                    const m = savedByStudent[s.student];
                                    const g = Number(m?.grace_marks ?? 0);
                                    const canGrace = canManage && m && m.attendance === "present" && m.marks_obtained !== null;
                                    return (
                                        <span className="flex items-center gap-2 text-sm">
                                            {g ? `+${g}` : "-"}
                                            {canGrace && <Button size="sm" variant="ghost" onClick={() => setGrace(m)}>{g ? "Change" : "Add"}</Button>}
                                            {published && m && m.attendance === "present" && m.marks_obtained !== null && (
                                                <Button size="sm" variant="ghost" onClick={() => setRecheck(m)}>Recheck</Button>
                                            )}
                                        </span>
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
                                        disabled={!editable}
                                        placeholder="Optional"
                                        value={marks[s.student]?.remarks ?? ""}
                                        onChange={(e) => update(s.student, { remarks: e.target.value })}
                                    />
                                ),
                            },
                        ]}
                    />
                    {editable && (
                        <div className="flex flex-wrap justify-end items-end gap-3">
                            <div className="w-full sm:w-96">
                                <label htmlFor="marks-reason" className="text-xs font-medium text-slate-500 mb-1 block">
                                    {needsReason ? "Reason for changing marks (required)" : "Reason for any change (optional)"}
                                </label>
                                <Input id="marks-reason" maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Totalling error on page 3" />
                            </div>
                            <Button onClick={handleSubmit} disabled={isPending} className="gap-2">
                                {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                Submit Marks
                            </Button>
                        </div>
                    )}
                </>
            )}

            {grace && schedule && <GraceDialog mark={grace} max={schedule.max_marks} onClose={() => setGrace(null)} />}
            {recheck && <RecheckDialog mark={recheck} onClose={() => setRecheck(null)} />}
            {importing && scheduleId && <ImportDialog scheduleId={scheduleId} needsReason={needsReason} onClose={() => setImporting(false)} />}
        </div>
    );
}
