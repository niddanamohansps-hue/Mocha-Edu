"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { useApplyModeration, usePreviewModeration } from "@/hooks/useExamAllocation";
import { useExamSchedules, useExaminations } from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { ModerationOptions, ModerationPreview } from "@/types/ExamAllocation";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function ModerationPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("moderate_exam_marks")) return <Unauthorized />;
    return <ModerationContent />;
}

function ModerationContent() {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const [examinationId, setExaminationId] = useState("");
    const [scheduleId, setScheduleId] = useState("");
    const { data: schedules = [] } = useExamSchedules(examinationId || undefined);
    const examination = examinations.find((e) => e.id === examinationId);
    const schedule = schedules.find((s) => s.id === scheduleId);

    const [method, setMethod] = useState<"add" | "scale">("add");
    const [value, setValue] = useState("");
    const [step, setStep] = useState("1");
    const [below, setBelow] = useState("");
    const [reason, setReason] = useState("");
    const [preview, setPreview] = useState<ModerationPreview | null>(null);
    const [confirming, setConfirming] = useState(false);
    const previewMutation = usePreviewModeration();
    const applyMutation = useApplyModeration();

    const options: ModerationOptions = { method, value, step, below: below || undefined };
    const reset = () => setPreview(null);

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Marks moderation</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Adjust a whole paper&apos;s marks together, for example when a paper was harder than planned. See the effect
                    first, then apply it with a reason. Every changed mark keeps its old value in its history. This works only
                    before results are published.
                </p>
            </div>

            <div className="flex flex-wrap gap-3">
                <select className={selectClass} value={examinationId} onChange={(e) => { setExaminationId(e.target.value); setScheduleId(""); reset(); }}>
                    <option value="">Choose an examination</option>
                    {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}{exam.is_published ? " (published)" : ""}</option>)}
                </select>
                <select className={selectClass} value={scheduleId} onChange={(e) => { setScheduleId(e.target.value); reset(); }}>
                    <option value="">Choose a paper</option>
                    {schedules.map((s) => <option key={s.id} value={s.id}>{s.section_name} - {s.subject_name} ({s.date})</option>)}
                </select>
            </div>

            {!schedule || !examination ? (
                <EmptyState title="Choose an examination and a paper" description="Its moderation options will be shown here." />
            ) : examination.is_published ? (
                <EmptyState title="Results are published" description="Marks can no longer be moderated. Use a recheck or grace marks for individual students." />
            ) : (schedule.components?.length ?? 0) > 0 ? (
                <EmptyState title="This paper has score parts" description="Papers split into parts such as Theory and Practical cannot be moderated together." />
            ) : (
                <>
                    <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                        <p className="text-sm text-slate-500">
                            Out of {Number(schedule.max_marks)}, pass mark {Number(schedule.pass_marks)}.
                        </p>
                        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                            <div className="grid gap-1.5">
                                <Label>What to do</Label>
                                <select className={selectClass} value={method} onChange={(e) => { setMethod(e.target.value as "add" | "scale"); reset(); }}>
                                    <option value="add">Add marks</option>
                                    <option value="scale">Multiply marks</option>
                                </select>
                            </div>
                            <div className="grid gap-1.5">
                                <Label>{method === "add" ? "Marks to add (or take away)" : "Multiply by"}</Label>
                                <Input type="number" step="any" value={value} onChange={(e) => { setValue(e.target.value); reset(); }} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Round to</Label>
                                <select className={selectClass} value={step} onChange={(e) => { setStep(e.target.value); reset(); }}>
                                    <option value="1">Whole marks</option>
                                    <option value="0.5">Half marks</option>
                                    <option value="0.25">Quarter marks</option>
                                    <option value="0.01">Two decimals</option>
                                </select>
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Only students below (optional)</Label>
                                <Input type="number" min={0} value={below} onChange={(e) => { setBelow(e.target.value); reset(); }} />
                            </div>
                        </div>
                        <Button
                            variant="outline"
                            disabled={!value || previewMutation.isPending}
                            onClick={() => previewMutation.mutate({ schedule: schedule.id, ...options }, { onSuccess: setPreview })}
                        >
                            {previewMutation.isPending ? "Working it out..." : "Preview the effect"}
                        </Button>
                    </section>

                    {preview && (
                        <section className="space-y-4">
                            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                                <Tile label="Marks that change" value={`${preview.summary.changed} of ${preview.summary.students_with_marks}`} />
                                <Tile label="Passing" value={`${preview.summary.passed_before} to ${preview.summary.passed_after}`} />
                                <Tile label="Average" value={`${preview.summary.average_before ?? "-"} to ${preview.summary.average_after ?? "-"}`} />
                                <Tile label="Held at the maximum" value={String(preview.summary.capped)} />
                            </div>
                            {preview.rows.length === 0 ? (
                                <p className="text-sm text-slate-500">Nothing would change with these settings.</p>
                            ) : (
                                <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                                    <table className="w-full text-sm">
                                        <thead className="bg-slate-50 dark:bg-slate-900">
                                            <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                                                <th className="px-4 py-3">Student</th>
                                                <th className="px-4 py-3">Now</th>
                                                <th className="px-4 py-3">After</th>
                                                <th className="px-4 py-3">Result</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {preview.rows.map((row) => (
                                                <tr key={row.mark_id} className="border-t border-slate-100 dark:border-slate-800">
                                                    <td className="px-4 py-2"><span className="font-medium">{row.name}</span> <span className="text-xs text-slate-400">{row.enrollment_id}</span></td>
                                                    <td className="px-4 py-2">{Number(row.old)}</td>
                                                    <td className="px-4 py-2 font-medium">{Number(row.new)}</td>
                                                    <td className="px-4 py-2">
                                                        {row.passed_before === row.passed_after ? (
                                                            <span className="text-slate-500">{row.passed_after ? "Passes" : "Fails"}</span>
                                                        ) : row.passed_after ? (
                                                            <Badge variant="outline">Now passes</Badge>
                                                        ) : (
                                                            <Badge variant="destructive">Now fails</Badge>
                                                        )}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}

                            {preview.rows.length > 0 && (
                                <div className="space-y-3 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                                    <div className="grid gap-1.5">
                                        <Label>Reason (kept on record, required)</Label>
                                        <Textarea rows={2} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="For example: the paper was harder than planned" />
                                    </div>
                                    <Button disabled={reason.trim().length < 5 || applyMutation.isPending} onClick={() => setConfirming(true)}>
                                        Apply moderation
                                    </Button>
                                </div>
                            )}
                        </section>
                    )}

                    <ConfirmationDialog
                        open={confirming}
                        onOpenChange={setConfirming}
                        title="Apply this moderation?"
                        description={`${preview?.summary.changed ?? 0} students' marks will change. Each old mark stays in the history, but this is a real change to marks, so check the preview first.`}
                        confirmLabel="Apply"
                        isLoading={applyMutation.isPending}
                        onConfirm={() =>
                            preview &&
                            applyMutation.mutate(
                                { schedule: schedule.id, reason: reason.trim(), expected_changed: preview.summary.changed, ...options },
                                { onSuccess: () => { setConfirming(false); setPreview(null); setReason(""); setValue(""); } },
                            )
                        }
                    />
                </>
            )}
        </div>
    );
}

function Tile({ label, value }: { label: string; value: string }) {
    return (
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className="text-xl font-bold text-slate-900 dark:text-white">{value}</div>
            <div className="text-xs text-slate-500">{label}</div>
        </div>
    );
}
