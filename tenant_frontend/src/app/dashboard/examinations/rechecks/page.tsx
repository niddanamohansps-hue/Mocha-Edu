"use client";

import { useState } from "react";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Field, FILTER_SELECT_CLASS, FormDialog, Pager, SELECT_CLASS, formatDateTime } from "@/components/dashboard/inventory/shared";
import { useMe } from "@/hooks/useAuth";
import { useCollectRecheckFee, useDecideRecheck, useRefundRecheckFee, useRechecks, useRequestRecheck, useStudentResults } from "@/hooks/useExaminations";
import { usePermissions } from "@/providers/PermissionProvider";
import { RecheckRequest, RecheckStatus } from "@/types/Examinations";

const STATUS_LABELS: Record<RecheckStatus, string> = { pending: "Waiting", accepted: "Accepted", rejected: "Rejected" };
const STATUS_STYLES: Record<RecheckStatus, string> = {
    pending: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    accepted: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    rejected: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
};
const TEXTAREA = "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm min-h-[70px]";

function DecideDialog({ recheck, decision, onClose }: { recheck: RecheckRequest; decision: "accept" | "reject"; onClose: () => void }) {
    const decide = useDecideRecheck();
    const [marks, setMarks] = useState(recheck.current_marks === null ? "" : String(Number(recheck.current_marks)));
    const [comment, setComment] = useState("");
    const [error, setError] = useState<string | null>(null);
    const accept = decision === "accept";
    return (
        <FormDialog
            open onOpenChange={(o) => !o && onClose()}
            title={accept ? "Accept the recheck" : "Reject the recheck"}
            description={`${recheck.student_name}, ${recheck.subject_name}: ${Number(recheck.original_marks)} of ${Number(recheck.max_marks)}. ${accept ? "The mark and the published result change, and the change is kept in the mark's history." : "The mark stays as it is."}`}
            submitLabel={accept ? "Accept" : "Reject"} pending={decide.isPending} error={error}
            onSubmit={() => {
                if (accept && (!/^\d+(\.\d{1,2})?$/.test(marks.trim()) || Number(marks) > Number(recheck.max_marks))) {
                    return setError(`Enter the marks after the recheck, from 0 to ${Number(recheck.max_marks)}.`);
                }
                if (!accept && !comment.trim()) return setError("Say why the recheck is rejected.");
                setError(null);
                decide.mutate(
                    { id: recheck.id, decision, revised_marks: accept ? marks.trim() : undefined, decision_comment: comment.trim() },
                    { onSuccess: onClose }
                );
            }}
        >
            {accept && <Field label="Marks after the recheck" htmlFor="dc-marks"><Input id="dc-marks" inputMode="decimal" value={marks} onChange={(e) => setMarks(e.target.value)} /></Field>}
            <Field label={accept ? "Comment (optional)" : "Why it is rejected"} htmlFor="dc-comment">
                <textarea id="dc-comment" className={TEXTAREA} maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
            </Field>
        </FormDialog>
    );
}

/** A student asks about one subject of a published examination, from their own results. */
function AskDialog({ studentId, onClose }: { studentId: string; onClose: () => void }) {
    const results = useStudentResults(studentId);
    const ask = useRequestRecheck();
    const [resultId, setResultId] = useState("");
    const [subject, setSubject] = useState("");
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    const result = results.data?.find((r) => r.id === resultId);
    return (
        <FormDialog
            open onOpenChange={(o) => !o && onClose()}
            title="Ask for a recheck" description="Choose the subject and say what should be re-checked."
            submitLabel="Ask" pending={ask.isPending} error={error}
            onSubmit={() => {
                if (!result || !subject) return setError("Choose the examination and the subject.");
                if (!reason.trim()) return setError("Say what should be re-checked.");
                setError(null);
                ask.mutate({ examination: result.examination, subject, reason: reason.trim() }, { onSuccess: onClose });
            }}
        >
            {results.isLoading ? <LoadingState className="py-6" /> : (
                <>
                    <Field label="Examination" htmlFor="ak-exam">
                        <select id="ak-exam" className={SELECT_CLASS} value={resultId} onChange={(e) => { setResultId(e.target.value); setSubject(""); }}>
                            <option value="">Choose an examination</option>
                            {(results.data ?? []).map((r) => <option key={r.id} value={r.id}>{r.examination_name || "Examination"} ({r.academic_year})</option>)}
                        </select>
                    </Field>
                    <Field label="Subject" htmlFor="ak-subject">
                        <select id="ak-subject" className={SELECT_CLASS} value={subject} disabled={!result} onChange={(e) => setSubject(e.target.value)}>
                            <option value="">Choose a subject</option>
                            {(result?.subject_breakdown ?? []).filter((b) => b.marks_obtained !== null).map((b) => (
                                <option key={b.subject} value={b.subject}>{b.subject_name} ({b.marks_obtained} of {b.max_marks})</option>
                            ))}
                        </select>
                    </Field>
                    <Field label="What should be re-checked" htmlFor="ak-reason">
                        <textarea id="ak-reason" className={TEXTAREA} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} />
                    </Field>
                </>
            )}
        </FormDialog>
    );
}

export default function RechecksPage() {
    const { data: me } = useMe();
    const { can, isOwner, activeRole } = usePermissions();
    const isStudent = activeRole === "student";
    const canDecide = isOwner || can("manage_marks");
    const [status, setStatus] = useState<RecheckStatus | "">(canDecide ? "pending" : "");
    const [page, setPage] = useState(1);
    const [deciding, setDeciding] = useState<{ recheck: RecheckRequest; decision: "accept" | "reject" } | null>(null);
    const [asking, setAsking] = useState(false);
    const { data, isLoading, isError, refetch } = useRechecks(status, page);
    const collect = useCollectRecheckFee();
    const collectFee = (r: RecheckRequest) => {
        const reference = window.prompt(`Record that the fee of ${Number(r.fee_amount)} was received. Receipt or reference (optional):`);
        if (reference !== null) collect.mutate({ id: r.id, reference: reference.trim() });
    };
    const refund = useRefundRecheckFee();
    const refundFee = (r: RecheckRequest) => {
        const reference = window.prompt(`The recheck changed the mark, so ${Number(r.fee_amount)} is owed back. Record that it was given back. Reference (optional):`);
        if (reference !== null) refund.mutate({ id: r.id, reference: reference.trim() });
    };
    const studentId = isStudent ? me?.profile?.student_id ?? "" : "";

    if (!(canDecide || can("view_results") || isStudent)) return <Unauthorized />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Rechecks</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {canDecide
                            ? "Requests to re-check published marks. Accepting changes the mark and the student's published result, on record."
                            : "Your requests to re-check published marks."}
                    </p>
                </div>
                {studentId && <Button onClick={() => setAsking(true)}>Ask for a recheck</Button>}
            </div>

            <select aria-label="Status" className={FILTER_SELECT_CLASS} value={status} onChange={(e) => { setPage(1); setStatus(e.target.value as RecheckStatus | ""); }}>
                <option value="">Any status</option>
                {(Object.keys(STATUS_LABELS) as RecheckStatus[]).map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>

            {isLoading ? <LoadingState className="py-16" /> : isError ? <ErrorState onRetry={refetch} /> : rows.length === 0 ? (
                <EmptyState title={status === "pending" ? "No rechecks are waiting." : "No rechecks yet."} className="py-12 text-slate-500 text-sm" />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        { key: "student", header: "Student", primary: true, cell: (r) => <>{r.student_name} <span className="text-xs text-slate-500">({r.enrollment_id})</span></> },
                        { key: "subject", header: "Subject", cell: (r) => <>{r.subject_name} <span className="block text-xs text-slate-500">{r.examination_name}</span></> },
                        {
                            key: "marks", header: "Marks", cell: (r) => (
                                <>{Number(r.original_marks)}{r.status === "accepted" && r.revised_marks !== null ? ` → ${Number(r.revised_marks)}` : ""} / {Number(r.max_marks)}</>
                            ),
                        },
                        {
                            key: "reason", header: "Reason", hideOnMobile: true, cell: (r) => (
                                <span className="text-sm">{r.reason}{r.decision_comment && <span className="block text-xs text-slate-500">Reply: {r.decision_comment}</span>}</span>
                            ),
                        },
                        {
                            key: "fee", header: "Fee", hideOnMobile: true, cell: (r) => Number(r.fee_amount) <= 0 ? <span className="text-xs text-slate-400">Free</span> : r.fee_paid_at ? (
                                <span className="text-xs text-emerald-700">
                                    {Number(r.fee_amount)} received{r.fee_reference ? ` (${r.fee_reference})` : ""}
                                    {r.fee_refunded_at ? ", refunded" : r.refund_due ? ", refund due" : ""}
                                </span>
                            ) : <span className="text-xs font-medium text-amber-700">{Number(r.fee_amount)} due</span>,
                        },
                        { key: "status", header: "Status", cell: (r) => <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[r.status]}`}>{STATUS_LABELS[r.status]}</span> },
                        { key: "when", header: "Asked", hideOnMobile: true, className: "text-slate-500", cell: (r) => formatDateTime(r.created_at) },
                    ]}
                    actionsHeader=""
                    actions={(r) => canDecide && r.status === "pending" && Number(r.fee_amount) > 0 && !r.fee_paid_at ? (
                        <Button size="sm" onClick={() => collectFee(r)} disabled={collect.isPending}>Fee received</Button>
                    ) : canDecide && r.refund_due ? (
                        <Button size="sm" variant="outline" onClick={() => refundFee(r)} disabled={refund.isPending}>Refund given</Button>
                    ) : canDecide && r.status === "pending" ? (
                        <div className="flex gap-2">
                            <Button size="sm" onClick={() => setDeciding({ recheck: r, decision: "accept" })}>Accept</Button>
                            <Button size="sm" variant="outline" onClick={() => setDeciding({ recheck: r, decision: "reject" })}>Reject</Button>
                        </div>
                    ) : null}
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />
            {deciding && <DecideDialog recheck={deciding.recheck} decision={deciding.decision} onClose={() => setDeciding(null)} />}
            {asking && studentId && <AskDialog studentId={studentId} onClose={() => setAsking(false)} />}
        </div>
    );
}
