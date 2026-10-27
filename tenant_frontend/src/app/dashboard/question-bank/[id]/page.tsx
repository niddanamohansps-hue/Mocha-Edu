"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { QuestionEditor } from "@/components/dashboard/question-bank/QuestionEditor";
import { Field, FormDialog, PageHeader, StatusBadge, formatDateTime } from "@/components/dashboard/question-bank/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import {
    useArchiveQuestion, useDeleteQuestion, useMyScope, useQuestion, useQuestionHistory, useReviewQuestion, useSubmitQuestion,
} from "@/hooks/useQuestionBank";
import { CHOICE_TYPES, DIFFICULTY_LABELS, Question, ReviewDecision, TYPE_LABELS } from "@/types/QuestionBank";

const DECISION_LABELS: Record<ReviewDecision, string> = { approved: "Approved", changes_requested: "Changes requested", rejected: "Rejected" };

function ReviewDialog({ question, decision, onClose }: { question: Question; decision: ReviewDecision | null; onClose: () => void }) {
    return decision ? <ReviewForm key={decision} question={question} decision={decision} onClose={onClose} /> : null;
}

function ReviewForm({ question, decision, onClose }: { question: Question; decision: ReviewDecision; onClose: () => void }) {
    const review = useReviewQuestion();
    const [comment, setComment] = useState("");
    const [error, setError] = useState<string | null>(null);
    const needsComment = decision !== "approved";
    const title = { approved: "Approve this question", changes_requested: "Send back for changes", rejected: "Reject this question" }[decision];
    return (
        <FormDialog
            open
            onOpenChange={(o) => !o && onClose()}
            title={title}
            description={decision === "approved" ? "It can then be used in examination papers." : "The author sees your comment."}
            submitLabel={title.split(" ")[0]}
            pending={review.isPending}
            error={error}
            onSubmit={() => {
                if (needsComment && !comment.trim()) return setError("Write what should change, or why it is rejected.");
                setError(null);
                review.mutate({ id: question.id, decision, comment: comment.trim() }, { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the decision")) });
            }}
        >
            <Field label={needsComment ? "Comment for the author" : "Comment (optional)"} htmlFor="rv-comment">
                <textarea
                    id="rv-comment" maxLength={2000} value={comment} onChange={(e) => setComment(e.target.value)}
                    className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm min-h-[88px]"
                />
            </Field>
        </FormDialog>
    );
}

function Block({ label, children }: { label: string; children: React.ReactNode }) {
    return (
        <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
            <div className="text-sm whitespace-pre-wrap">{children}</div>
        </div>
    );
}

export default function QuestionPage() {
    const { id } = useParams<{ id: string }>();
    const router = useRouter();
    const { data: question, isLoading, isError } = useQuestion(id);
    const history = useQuestionHistory(id);
    const scope = useMyScope();
    const submit = useSubmitQuestion();
    const archive = useArchiveQuestion();
    const remove = useDeleteQuestion();
    const [editing, setEditing] = useState<Question | null | undefined>(undefined);
    const [decision, setDecision] = useState<ReviewDecision | null>(null);
    const [deleting, setDeleting] = useState(false);

    if (isLoading) return <LoadingState className="py-20" />;
    if (isError || !question) return <ErrorState message="This question was not found, or you cannot see it." />;

    const manager = !!scope.data?.is_manager;
    const canEdit = (question.is_mine || manager) && (question.status === "draft" || question.status === "changes_requested");
    // The server lists every subject for the owner here, and only named subjects for a reviewer.
    const reviewsSubject = (scope.data?.can_review ?? []).some((s) => s.id === question.subject);
    const canReview = question.status === "submitted" && !question.is_mine && reviewsSubject;
    const canArchive = (question.is_mine || manager || reviewsSubject) && !["submitted", "archived"].includes(question.status);
    const canDelete = (question.is_mine || manager) && question.status === "draft" && !question.submitted_at;
    const lastReview = history.data?.reviews[0];

    return (
        <div className="space-y-6">
            <PageHeader
                title={`${question.subject_name} question`}
                description={`${question.level_name} · ${TYPE_LABELS[question.question_type]} · ${DIFFICULTY_LABELS[question.difficulty]} · ${Number(question.marks)} mark${Number(question.marks) === 1 ? "" : "s"} · version ${question.version}`}
                actions={
                    <>
                        {canEdit && <Button variant="outline" onClick={() => setEditing(question)}>Edit</Button>}
                        {canEdit && <Button disabled={submit.isPending} onClick={() => submit.mutate(question.id)}>Submit for review</Button>}
                        {canReview && <Button onClick={() => setDecision("approved")}>Approve</Button>}
                        {canReview && <Button variant="outline" onClick={() => setDecision("changes_requested")}>Send back</Button>}
                        {canReview && <Button variant="outline" className="text-red-600" onClick={() => setDecision("rejected")}>Reject</Button>}
                        {canArchive && <Button variant="ghost" disabled={archive.isPending} onClick={() => archive.mutate(question.id)}>Archive</Button>}
                        {canDelete && <Button variant="ghost" className="text-red-600" onClick={() => setDeleting(true)}>Delete draft</Button>}
                    </>
                }
            />
            <div className="flex flex-wrap items-center gap-3 text-sm">
                <StatusBadge status={question.status} />
                <span className="text-slate-500">by {question.is_mine ? "you" : question.author_name || "unknown"}</span>
                {question.chapter_name && <span className="text-slate-500">· {question.chapter_name}{question.topic_name ? ` › ${question.topic_name}` : ""}</span>}
                {question.status === "approved" && <span className="text-slate-500">· {question.times_used ? `used in ${question.times_used} paper${question.times_used === 1 ? "" : "s"}, last in ${question.last_used_in}` : "not used in a paper yet"}</span>}
                <Link href="/dashboard/question-bank" className="ml-auto text-sky-700 hover:underline">Back to the bank</Link>
            </div>

            {question.status === "changes_requested" && lastReview?.decision === "changes_requested" && (
                <section className="rounded-2xl border border-orange-300 bg-orange-50 dark:bg-orange-500/10 dark:border-orange-500/30 p-4 text-sm">
                    <p className="font-semibold">{lastReview.reviewer_name || "The reviewer"} asked for changes</p>
                    <p className="whitespace-pre-wrap">{lastReview.comment}</p>
                </section>
            )}

            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-4">
                <Block label="Question">{question.body}</Block>
                {CHOICE_TYPES.includes(question.question_type) && (
                    <div className="space-y-1">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Options</p>
                        <ol className="list-[upper-alpha] pl-6 text-sm space-y-1">
                            {question.options.map((o, i) => (
                                <li key={i} className={o.is_correct ? "font-semibold text-emerald-700 dark:text-emerald-400" : ""}>
                                    {o.text}{o.is_correct ? " ✓" : ""}
                                </li>
                            ))}
                        </ol>
                    </div>
                )}
                {question.answer && <Block label={CHOICE_TYPES.includes(question.question_type) ? "Answer note" : "Expected answer"}>{question.answer}</Block>}
                {question.marking_scheme && <Block label="Marking scheme">{question.marking_scheme}</Block>}
                {question.explanation && <Block label="Explanation">{question.explanation}</Block>}
                {question.learning_outcome && <Block label="Learning outcome">{question.learning_outcome}</Block>}
            </section>

            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                <h2 className="font-semibold text-slate-900 dark:text-white">History</h2>
                {history.isLoading ? <LoadingState className="py-4" /> : (
                    <ul className="text-sm space-y-2">
                        {(history.data?.reviews ?? []).map((r) => (
                            <li key={r.id}>
                                <span className="font-medium">{DECISION_LABELS[r.decision]}</span> (version {r.version}) by {r.reviewer_name || "a reviewer"}, {formatDateTime(r.created_at)}
                                {r.comment && <span className="block text-slate-500 whitespace-pre-wrap">{r.comment}</span>}
                            </li>
                        ))}
                        {(history.data?.versions ?? []).map((v) => (
                            <li key={v.id} className="text-slate-500">Version {v.number} saved {formatDateTime(v.created_at)}</li>
                        ))}
                    </ul>
                )}
            </section>

            <QuestionEditor question={editing} onClose={() => setEditing(undefined)} />
            <ReviewDialog question={question} decision={decision} onClose={() => setDecision(null)} />
            <ConfirmationDialog
                open={deleting}
                onOpenChange={setDeleting}
                title="Delete this draft?"
                description="It has never been submitted, so nothing else refers to it. This cannot be undone."
                confirmLabel="Delete"
                isLoading={remove.isPending}
                onConfirm={() => remove.mutate(question.id, { onSuccess: () => router.push("/dashboard/question-bank"), onSettled: () => setDeleting(false) })}
            />
        </div>
    );
}
