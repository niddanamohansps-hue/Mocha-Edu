"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import {
    useDecideMalpractice,
    useMalpracticeCases,
    useReportMalpractice,
    useUpdateMalpractice,
} from "@/hooks/useExamAllocation";
import { useExamSchedules, useExaminations } from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { MalpracticeCase, MalpracticeDecision } from "@/types/ExamAllocation";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

const DECISIONS: { value: MalpracticeDecision; label: string; help: string }[] = [
    { value: "dismissed", label: "Dismiss, no action", help: "The marks stand." },
    { value: "warning", label: "Warning, marks stand", help: "The student is warned; the marks stand." },
    { value: "marks_cancelled", label: "Cancel this paper's marks", help: "The student is recorded as malpractice in this paper and the score is removed." },
    { value: "all_papers_cancelled", label: "Cancel all papers in this examination", help: "Every paper of this examination for the student is recorded as malpractice." },
];

export default function MalpracticePage() {
    const { can, isOwner } = usePermissions();
    const canReport = isOwner || can("report_exam_malpractice");
    const canDecide = isOwner || can("decide_exam_malpractice");
    if (!canReport && !canDecide) return <Unauthorized />;
    return <MalpracticeContent canReport={canReport} canDecide={canDecide} />;
}

function MalpracticeContent({ canReport, canDecide }: { canReport: boolean; canDecide: boolean }) {
    const [filter, setFilter] = useState("");
    const { data: cases = [], isLoading } = useMalpracticeCases(filter || undefined);
    const [reporting, setReporting] = useState(false);
    const [openId, setOpenId] = useState<string | null>(null);
    const open = cases.find((c) => c.id === openId);

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Exam malpractice</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Report a student for cheating, add what was found, and have it decided. Reporting changes nothing about the
                    student&apos;s marks; only a decision that cancels marks does. Results cannot be published while a case is
                    undecided.
                    {!canDecide && " You see only the cases you reported."}
                </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
                <select className={selectClass} value={filter} onChange={(e) => setFilter(e.target.value)}>
                    <option value="">All cases</option>
                    <option value="reported">Waiting for a decision</option>
                    <option value="decided">Decided</option>
                </select>
                {canReport && <Button onClick={() => setReporting(true)}>Report a case</Button>}
            </div>

            {isLoading ? (
                <LoadingState />
            ) : cases.length === 0 ? (
                <EmptyState title="No cases" description="Reported malpractice cases will be listed here." />
            ) : (
                <div className="space-y-3">
                    {cases.map((c) => (
                        <button
                            key={c.id}
                            onClick={() => setOpenId(c.id)}
                            className="w-full rounded-2xl border border-slate-200 bg-white p-4 text-left hover:border-slate-300 dark:border-slate-800 dark:bg-slate-900"
                        >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <span className="font-semibold">{c.student} <span className="text-sm font-normal text-slate-400">{c.enrollment_id}</span></span>
                                <Badge variant={c.status === "reported" ? "destructive" : "outline"}>
                                    {c.status === "reported" ? "Waiting for a decision" : c.decision_label}
                                </Badge>
                            </div>
                            <p className="mt-1 text-sm text-slate-500">{c.examination_name} - {c.subject} - {c.class}</p>
                        </button>
                    ))}
                </div>
            )}

            {reporting && <ReportDialog onClose={() => setReporting(false)} />}
            {open && <CaseDialog key={open.id} item={open} canDecide={canDecide} onClose={() => setOpenId(null)} />}
        </div>
    );
}

function ReportDialog({ onClose }: { onClose: () => void }) {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const [examinationId, setExaminationId] = useState("");
    const [scheduleId, setScheduleId] = useState("");
    const [studentId, setStudentId] = useState("");
    const [description, setDescription] = useState("");
    const [evidence, setEvidence] = useState("");
    const { data: schedules = [] } = useExamSchedules(examinationId || undefined);
    const schedule = schedules.find((s) => s.id === scheduleId);
    const report = useReportMalpractice();

    const { data: roster = [] } = useQuery({
        queryKey: ["examinations", "malpractice-roster", scheduleId],
        enabled: !!schedule,
        queryFn: async () =>
            (await axiosInstance.get(`/attendance/sections/${schedule?.section}/roster/`, { params: { date: schedule?.date } }))
                .data.students as { student: string; full_name: string; enrollment_id: string }[],
    });

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>Report a malpractice case</DialogTitle>
                    <DialogDescription>Reporting does not change the student&apos;s marks. The head decides the case.</DialogDescription>
                </DialogHeader>
                <div className="grid gap-4">
                    <select className={selectClass} value={examinationId} onChange={(e) => { setExaminationId(e.target.value); setScheduleId(""); setStudentId(""); }}>
                        <option value="">Examination</option>
                        {examinations.filter((e) => !e.is_published).map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
                    </select>
                    <select className={selectClass} value={scheduleId} onChange={(e) => { setScheduleId(e.target.value); setStudentId(""); }}>
                        <option value="">Paper</option>
                        {schedules.map((s) => <option key={s.id} value={s.id}>{s.section_name} - {s.subject_name} ({s.date})</option>)}
                    </select>
                    <select className={selectClass} value={studentId} onChange={(e) => setStudentId(e.target.value)} disabled={!schedule}>
                        <option value="">Student</option>
                        {roster.map((s) => <option key={s.student} value={s.student}>{s.full_name} ({s.enrollment_id})</option>)}
                    </select>
                    <div className="grid gap-1.5">
                        <Label>What happened (required)</Label>
                        <Textarea rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
                    </div>
                    <div className="grid gap-1.5">
                        <Label>What was found (optional)</Label>
                        <Textarea rows={2} value={evidence} onChange={(e) => setEvidence(e.target.value)} placeholder="Items, witnesses, notes on the answer sheet" />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={onClose}>Cancel</Button>
                    <Button
                        disabled={report.isPending || !scheduleId || !studentId || description.trim().length < 10}
                        onClick={() => report.mutate({ schedule: scheduleId, student: studentId, description, evidence_notes: evidence }, { onSuccess: onClose })}
                    >
                        Report
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

function CaseDialog({ item, canDecide, onClose }: { item: MalpracticeCase; canDecide: boolean; onClose: () => void }) {
    const update = useUpdateMalpractice();
    const decide = useDecideMalpractice();
    const [evidence, setEvidence] = useState(item.evidence_notes);
    const [decision, setDecision] = useState<MalpracticeDecision | "">("");
    const [notes, setNotes] = useState("");
    const [confirming, setConfirming] = useState(false);
    const undecided = item.status === "reported";
    const chosen = DECISIONS.find((d) => d.value === decision);

    return (
        <Dialog open onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{item.student} <span className="text-sm font-normal text-slate-400">{item.enrollment_id}</span></DialogTitle>
                    <DialogDescription>{item.examination_name} - {item.subject} - {item.class}</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 text-sm">
                    <section>
                        <h4 className="font-semibold">What happened</h4>
                        <p className="whitespace-pre-line text-slate-600 dark:text-slate-300">{item.description}</p>
                        <p className="mt-1 text-xs text-slate-400">Reported by {item.reported_by || "staff"} on {new Date(item.reported_at).toLocaleString()}</p>
                    </section>
                    <section className="space-y-2">
                        <h4 className="font-semibold">What was found</h4>
                        {undecided ? (
                            <>
                                <Textarea rows={3} value={evidence} onChange={(e) => setEvidence(e.target.value)} />
                                <Button size="sm" variant="outline" disabled={update.isPending || evidence === item.evidence_notes} onClick={() => update.mutate({ id: item.id, evidence_notes: evidence })}>
                                    Save notes
                                </Button>
                            </>
                        ) : (
                            <p className="whitespace-pre-line text-slate-600 dark:text-slate-300">{item.evidence_notes || "Nothing recorded."}</p>
                        )}
                    </section>

                    {!undecided && (
                        <section className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                            <h4 className="font-semibold">Decision: {item.decision_label}</h4>
                            <p className="whitespace-pre-line text-slate-600 dark:text-slate-300">{item.decision_notes}</p>
                            <p className="mt-1 text-xs text-slate-400">By {item.decided_by || "the head"}{item.decided_at ? ` on ${new Date(item.decided_at).toLocaleString()}` : ""}</p>
                        </section>
                    )}

                    {undecided && canDecide && (
                        <section className="space-y-3 rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                            <h4 className="font-semibold">Decide this case</h4>
                            <select className={selectClass} value={decision} onChange={(e) => setDecision(e.target.value as MalpracticeDecision)}>
                                <option value="">Choose a decision</option>
                                {DECISIONS.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
                            </select>
                            {chosen && <p className="text-xs text-slate-500">{chosen.help}</p>}
                            <Textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Reasons for the decision (required)" />
                            <Button disabled={!decision || notes.trim().length < 5 || decide.isPending} onClick={() => setConfirming(true)}>Record the decision</Button>
                        </section>
                    )}
                </div>
                <ConfirmationDialog
                    open={confirming}
                    onOpenChange={setConfirming}
                    title="Record this decision?"
                    description={
                        decision === "marks_cancelled" || decision === "all_papers_cancelled"
                            ? "The student's marks will be cancelled and recorded as malpractice. The old marks stay in the marks history. A decision cannot be changed afterwards."
                            : "A decision cannot be changed afterwards."
                    }
                    confirmLabel="Record"
                    isLoading={decide.isPending}
                    onConfirm={() => decision && decide.mutate({ id: item.id, decision, notes: notes.trim() }, { onSuccess: () => { setConfirming(false); onClose(); } })}
                />
            </DialogContent>
        </Dialog>
    );
}
