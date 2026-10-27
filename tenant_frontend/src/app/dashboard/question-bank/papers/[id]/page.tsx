"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import {
    Field, FILTER_SELECT_CLASS, FormDialog, PageHeader, PaperStatusBadge, formatDateTime,
} from "@/components/dashboard/question-bank/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import {
    useAddPaperQuestion, useAddRule, useApprovePaper, useAutofillPaper, useChapters, useDeletePaper, useDeleteRule,
    useDeleteSection, usePaper, usePaperAccessLog, usePaperCandidates, useReleasePaper, useRemovePaperQuestion,
    useSaveSection, useSchedulePaper, useSendBackPaper, useSubmitPaper, useWithdrawPaper,
} from "@/hooks/useQuestionBank";
import { usePermissions } from "@/providers/PermissionProvider";
import { DIFFICULTY_LABELS, Difficulty, PaperSection, QuestionPaper, QuestionType, TYPE_LABELS } from "@/types/QuestionBank";

function RuleForm({ paper, section }: { paper: QuestionPaper; section: PaperSection }) {
    const add = useAddRule();
    const chapters = useChapters(paper.subject);
    const [count, setCount] = useState("5");
    const [type, setType] = useState("");
    const [difficulty, setDifficulty] = useState("");
    const [chapter, setChapter] = useState("");
    const [marks, setMarks] = useState("");
    return (
        <form
            className="flex flex-wrap items-end gap-2"
            onSubmit={(e) => {
                e.preventDefault();
                if (!/^\d+$/.test(count) || Number(count) < 1) return;
                if (marks.trim() && !/^\d+(\.5)?$/.test(marks.trim())) return;
                add.mutate({ section: section.id, count: Number(count), question_type: type, difficulty, chapter: chapter || null, marks: marks.trim() || null });
            }}
        >
            <Input aria-label="How many" className="w-20" inputMode="numeric" value={count} onChange={(e) => setCount(e.target.value)} />
            <Input aria-label="Marks each" placeholder="Marks each" className="w-28" inputMode="decimal" value={marks} onChange={(e) => setMarks(e.target.value)} />
            <select aria-label="Type" className={FILTER_SELECT_CLASS} value={type} onChange={(e) => setType(e.target.value)}>
                <option value="">Any type</option>
                {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
            </select>
            <select aria-label="Difficulty" className={FILTER_SELECT_CLASS} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                <option value="">Any difficulty</option>
                {(Object.keys(DIFFICULTY_LABELS) as Difficulty[]).map((d) => <option key={d} value={d}>{DIFFICULTY_LABELS[d]}</option>)}
            </select>
            <select aria-label="Chapter" className={FILTER_SELECT_CLASS} value={chapter} onChange={(e) => setChapter(e.target.value)}>
                <option value="">Any chapter</option>
                {(chapters.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <Button type="submit" size="sm" variant="outline" disabled={add.isPending}>Add rule</Button>
        </form>
    );
}

function PickerDialog({ paper, section, onClose }: { paper: QuestionPaper; section: PaperSection | null; onClose: () => void }) {
    const [search, setSearch] = useState("");
    const [type, setType] = useState("");
    const [difficulty, setDifficulty] = useState("");
    const [unused, setUnused] = useState(false);
    const candidates = usePaperCandidates(section ? paper.id : "", { search, question_type: type, difficulty, chapter: "", unused: unused ? "true" : "" });
    const add = useAddPaperQuestion();
    if (!section) return null;
    return (
        <FormDialog open wide onOpenChange={(o) => !o && onClose()} title={`Add questions to ${section.title}`}
            description="Approved questions of this subject that are not already in this paper (or, unless allowed, in another set)."
            submitLabel="Done" onSubmit={onClose}>
            <div className="flex flex-wrap gap-2">
                <Input aria-label="Search" placeholder="Search the question text" value={search} onChange={(e) => setSearch(e.target.value)} />
                <select aria-label="Type" className={FILTER_SELECT_CLASS} value={type} onChange={(e) => setType(e.target.value)}>
                    <option value="">Any type</option>
                    {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
                </select>
                <select aria-label="Difficulty" className={FILTER_SELECT_CLASS} value={difficulty} onChange={(e) => setDifficulty(e.target.value)}>
                    <option value="">Any difficulty</option>
                    {(Object.keys(DIFFICULTY_LABELS) as Difficulty[]).map((d) => <option key={d} value={d}>{DIFFICULTY_LABELS[d]}</option>)}
                </select>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={unused} onChange={(e) => setUnused(e.target.checked)} /> Never used</label>
            </div>
            {candidates.isLoading ? <LoadingState className="py-6" /> : (candidates.data?.results ?? []).length === 0 ? (
                <p className="text-sm text-slate-500">No approved question matches. Approve more questions in the bank first.</p>
            ) : (
                <ul className="divide-y divide-slate-100 dark:divide-slate-800 max-h-[50vh] overflow-y-auto">
                    {(candidates.data?.results ?? []).map((q) => (
                        <li key={q.id} className="py-2 flex items-start gap-3 text-sm">
                            <span className="flex-1">{q.body}<span className="block text-xs text-slate-500">{TYPE_LABELS[q.question_type]} · {DIFFICULTY_LABELS[q.difficulty]} · {Number(q.marks)} marks{q.chapter_name ? ` · ${q.chapter_name}` : ""} · {q.times_used ? `used ${q.times_used}×, last in ${q.last_used_in}` : "never used"}</span></span>
                            <Button type="button" size="sm" variant="outline" disabled={add.isPending}
                                onClick={() => add.mutate({ id: paper.id, body: { section: section.id, question: q.id } })}>Add</Button>
                        </li>
                    ))}
                </ul>
            )}
        </FormDialog>
    );
}

function SectionCard({ paper, section, editable, onPick }: { paper: QuestionPaper; section: PaperSection; editable: boolean; onPick: () => void }) {
    const removeRule = useDeleteRule();
    const removeItem = useRemovePaperQuestion();
    const removeSection = useDeleteSection();
    const autofill = useAutofillPaper();
    const marks = section.items.reduce((sum, i) => sum + Number(i.marks), 0);
    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
            <div className="flex flex-wrap items-center gap-2">
                <h2 className="font-semibold text-slate-900 dark:text-white">{section.title}</h2>
                <span className="text-xs text-slate-500">{section.items.length} questions · {marks} marks</span>
                {editable && (
                    <span className="ml-auto flex flex-wrap gap-1">
                        {section.rules.length > 0 && (
                            <Button size="sm" variant="outline" disabled={autofill.isPending} onClick={() => autofill.mutate({ id: paper.id, body: { section: section.id } })}>Generate questions from blueprint</Button>
                        )}
                        <Button size="sm" variant="outline" onClick={onPick}>Add questions</Button>
                        <Button size="sm" variant="ghost" className="text-red-600" disabled={removeSection.isPending} onClick={() => removeSection.mutate(section.id)}>Delete section</Button>
                    </span>
                )}
            </div>
            <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Blueprint</p>
                {section.rules.length === 0 ? <p className="text-sm text-slate-500">No rules. Questions are chosen by hand.</p> : (
                    <ul className="flex flex-wrap gap-2">
                        {section.rules.map((r) => (
                            <li key={r.id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs">
                                {r.description}
                                {editable && <button type="button" aria-label="Remove rule" className="text-slate-400 hover:text-red-600" onClick={() => removeRule.mutate(r.id)}>×</button>}
                            </li>
                        ))}
                    </ul>
                )}
                {editable && <RuleForm paper={paper} section={section} />}
            </div>
            {section.items.length > 0 && (
                <ol className="divide-y divide-slate-100 dark:divide-slate-800 text-sm">
                    {section.items.map((item, index) => (
                        <li key={item.id} className="py-2 flex items-start gap-3">
                            <span className="w-6 text-slate-400">{index + 1}.</span>
                            <span className="flex-1">{item.body}<span className="block text-xs text-slate-500">{TYPE_LABELS[item.question_type]} · {DIFFICULTY_LABELS[item.difficulty]}{item.chapter_name ? ` · ${item.chapter_name}` : ""}{item.question_status !== "approved" ? " · no longer approved" : ""}</span></span>
                            <span className="font-medium">{Number(item.marks)}</span>
                            {editable && <Button size="sm" variant="ghost" disabled={removeItem.isPending} onClick={() => removeItem.mutate({ id: paper.id, item: item.id })}>Remove</Button>}
                        </li>
                    ))}
                </ol>
            )}
        </section>
    );
}

function TextDialog({ title, label, open, pending, onClose, onSubmit }: {
    title: string; label: string; open: boolean; pending: boolean; onClose: () => void; onSubmit: (text: string) => void;
}) {
    const [text, setText] = useState("");
    if (!open) return null;
    return (
        <FormDialog open onOpenChange={(o) => !o && onClose()} title={title} submitLabel={title.split(" ")[0]} pending={pending}
            error={null} onSubmit={() => text.trim() && onSubmit(text.trim())}>
            <Field label={label} htmlFor="td-text"><Input id="td-text" maxLength={255} value={text} onChange={(e) => setText(e.target.value)} /></Field>
        </FormDialog>
    );
}

export default function PaperPage() {
    const { id } = useParams<{ id: string }>();
    const router = useRouter();
    const { can } = usePermissions();
    const { data: paper, isLoading, isError } = usePaper(id);
    const canPrepare = can("prepare_papers");
    const canApprove = can("approve_papers");
    const log = usePaperAccessLog(id, canApprove);
    const saveSection = useSaveSection();
    const submit = useSubmitPaper();
    const approve = useApprovePaper();
    const sendBack = useSendBackPaper();
    const release = useReleasePaper();
    const withdraw = useWithdrawPaper();
    const schedule = useSchedulePaper();
    const remove = useDeletePaper();
    const [picking, setPicking] = useState<PaperSection | null>(null);
    const [backOpen, setBackOpen] = useState(false);
    const [withdrawOpen, setWithdrawOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [releaseAt, setReleaseAt] = useState("");
    const [error, setError] = useState<string | null>(null);

    if (isLoading) return <LoadingState className="py-20" />;
    if (isError || !paper) return <ErrorState message="This paper was not found, or you cannot see it." />;

    const editable = canPrepare && paper.status === "draft";
    const sections = paper.sections ?? [];
    const problems = paper.problems ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title={`${paper.title} · Set ${paper.set_label}`}
                description={`${paper.subject_name} (${paper.level_name}) · ${paper.examination_name} · ${Number(paper.total_marks)} marks · ${paper.duration_minutes} minutes`}
                actions={
                    <>
                        <Button asChild variant="outline"><Link href={`/dashboard/question-bank/papers/${paper.id}/print`}>Print paper</Link></Button>
                        <Button asChild variant="outline"><Link href={`/dashboard/question-bank/papers/${paper.id}/print?key=1`}>Answer key</Link></Button>
                        {editable && <Button disabled={submit.isPending || problems.length > 0} onClick={() => submit.mutate({ id: paper.id })}>Submit for approval</Button>}
                        {canApprove && paper.status === "submitted" && !paper.is_mine && <Button disabled={approve.isPending} onClick={() => approve.mutate({ id: paper.id })}>Approve</Button>}
                        {canApprove && paper.status === "submitted" && <Button variant="outline" onClick={() => setBackOpen(true)}>Send back</Button>}
                        {canApprove && paper.status === "approved" && <Button disabled={release.isPending} onClick={() => release.mutate({ id: paper.id })}>Release now</Button>}
                        {canApprove && ["approved", "released"].includes(paper.status) && <Button variant="outline" className="text-red-600" onClick={() => setWithdrawOpen(true)}>Withdraw</Button>}
                        {editable && !paper.submitted_at && <Button variant="ghost" className="text-red-600" onClick={() => setDeleting(true)}>Delete draft</Button>}
                    </>
                }
            />
            <div className="flex flex-wrap items-center gap-3 text-sm">
                <PaperStatusBadge status={paper.status} />
                <span className="text-slate-500">{Number(paper.marks_so_far)} of {Number(paper.total_marks)} marks · {paper.question_count} questions</span>
                {paper.release_at && !paper.released_at && <span className="text-slate-500">· releases {formatDateTime(paper.release_at)}</span>}
                {paper.released_at && <span className="text-slate-500">· released {formatDateTime(paper.released_at)}</span>}
                <Link href="/dashboard/question-bank/papers" className="ml-auto text-sky-700 hover:underline">All papers</Link>
            </div>

            {paper.review_comment && paper.status === "draft" && (
                <section className="rounded-2xl border border-orange-300 bg-orange-50 dark:bg-orange-500/10 dark:border-orange-500/30 p-4 text-sm">
                    <p className="font-semibold">Sent back by the approver</p><p>{paper.review_comment}</p>
                </section>
            )}
            {paper.status === "withdrawn" && (
                <section className="rounded-2xl border border-red-300 bg-red-50 dark:bg-red-500/10 p-4 text-sm">Withdrawn: {paper.withdraw_reason}</section>
            )}
            {problems.length > 0 && ["draft", "submitted"].includes(paper.status) && (
                <section className="rounded-2xl border border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30 p-4 text-sm space-y-1">
                    <p className="font-semibold">Before this paper can be submitted</p>
                    <ul className="list-disc pl-5">{problems.map((p) => <li key={p}>{p}</li>)}</ul>
                </section>
            )}
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}

            {paper.blueprint && paper.blueprint.rules.length > 0 && (
                <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 text-sm space-y-1">
                    <p className="font-semibold">
                        Blueprint: {paper.blueprint.planned_marks === null ? "set marks on every rule to see the planned total" : `${Number(paper.blueprint.planned_marks)} of ${Number(paper.total_marks)} marks planned`}
                    </p>
                    <ul>
                        {paper.blueprint.rules.filter((r) => r.available < r.needed).map((r) => (
                            <li key={r.rule} className="text-amber-700">{r.section}: a rule needs {r.needed} questions but only {r.available} approved ones match.</li>
                        ))}
                    </ul>
                </section>
            )}

            {sections.map((section) => (
                <SectionCard key={section.id} paper={paper} section={section} editable={editable} onPick={() => setPicking(section)} />
            ))}
            {editable && (
                <Button variant="outline" disabled={saveSection.isPending}
                    onClick={() => saveSection.mutate({ input: { paper: paper.id, order: sections.length + 1, title: `Section ${String.fromCharCode(65 + sections.length)}` } })}>
                    Add a section
                </Button>
            )}

            {canApprove && ["draft", "submitted", "approved"].includes(paper.status) && (
                <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Release time</h2>
                    <p className="text-sm text-slate-500">Teachers of the subject can open the paper from this time, once it is approved. Leave it empty to release by hand.</p>
                    <div className="flex flex-wrap gap-2">
                        <Input type="datetime-local" aria-label="Release at" value={releaseAt} onChange={(e) => setReleaseAt(e.target.value)} className="w-auto" />
                        <Button variant="outline" disabled={schedule.isPending}
                            onClick={() => schedule.mutate({ id: paper.id, body: { release_at: releaseAt ? new Date(releaseAt).toISOString() : null } },
                                { onError: (e) => setError(inventoryErrorMessage(e, "Could not save the release time")) })}>
                            Save release time
                        </Button>
                    </div>
                </section>
            )}

            {canApprove && (
                <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-2">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Who opened this paper</h2>
                    {(log.data ?? []).length === 0 ? <p className="text-sm text-slate-500">Nobody has opened it yet.</p> : (
                        <ul className="text-sm space-y-1">
                            {(log.data ?? []).map((row, i) => (
                                <li key={i}>{row.user || "unknown"} {row.kind === "answer_key" ? "opened the answer key" : "opened the paper"} · {formatDateTime(row.at)} <span className="text-slate-500">({row.status})</span></li>
                            ))}
                        </ul>
                    )}
                </section>
            )}

            <PickerDialog paper={paper} section={picking} onClose={() => setPicking(null)} />
            <TextDialog title="Send back to the preparer" label="What should change" open={backOpen} pending={sendBack.isPending}
                onClose={() => setBackOpen(false)} onSubmit={(comment) => sendBack.mutate({ id: paper.id, body: { comment } }, { onSettled: () => setBackOpen(false) })} />
            <TextDialog title="Withdraw this paper" label="Reason, for example a suspected leak" open={withdrawOpen} pending={withdraw.isPending}
                onClose={() => setWithdrawOpen(false)} onSubmit={(reason) => withdraw.mutate({ id: paper.id, body: { reason } }, { onSettled: () => setWithdrawOpen(false) })} />
            <ConfirmationDialog open={deleting} onOpenChange={setDeleting} title="Delete this draft paper?" description="It has never been submitted. This cannot be undone."
                confirmLabel="Delete" isLoading={remove.isPending}
                onConfirm={() => remove.mutate(paper.id, { onSuccess: () => router.push("/dashboard/question-bank/papers"), onSettled: () => setDeleting(false) })} />
        </div>
    );
}
