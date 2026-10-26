"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import {
    FILTER_SELECT_CLASS, Field, FormDialog, PageHeader, Pager, PaperStatusBadge, SELECT_CLASS, formatDateTime,
} from "@/components/dashboard/question-bank/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { usePaperChoices, usePapers, useSavePaper } from "@/hooks/useQuestionBank";
import { usePermissions } from "@/providers/PermissionProvider";
import { PAPER_STATUS_LABELS, PaperStatus } from "@/types/QuestionBank";

function NewPaperDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
    return open ? <NewPaperForm onClose={onClose} /> : null;
}

function NewPaperForm({ onClose }: { onClose: () => void }) {
    const router = useRouter();
    const choices = usePaperChoices(true);
    const save = useSavePaper();
    const [examination, setExamination] = useState("");
    const [subject, setSubject] = useState("");
    const [label, setLabel] = useState("A");
    const [title, setTitle] = useState("");
    const [total, setTotal] = useState("");
    const [duration, setDuration] = useState("120");
    const [instructions, setInstructions] = useState("Answer all questions. Write neatly.");
    const [shared, setShared] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const subjectName = (choices.data?.subjects ?? []).find((s) => s.id === subject);
    const examName = (choices.data?.examinations ?? []).find((e) => e.id === examination);

    return (
        <FormDialog
            open
            onOpenChange={(o) => !o && onClose()}
            title="New question paper"
            description="One set (A, B, ...) of the paper for a subject in an examination. Add sections and questions next."
            submitLabel="Create paper"
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                if (!examination || !subject) return setError("Choose the examination and the subject.");
                if (!/^\d+(\.\d{1,2})?$/.test(total.trim()) || Number(total) <= 0) return setError("Enter the total marks.");
                if (!/^\d+$/.test(duration.trim()) || Number(duration) < 1) return setError("Enter the duration in minutes.");
                setError(null);
                const name = title.trim() || `${subjectName?.name ?? "Paper"} - ${examName?.name ?? ""}`.trim();
                save.mutate(
                    { input: { examination, subject, set_label: label.trim() || "A", title: name, total_marks: total.trim(),
                               duration_minutes: Number(duration), instructions: instructions.trim(), allow_shared_questions: shared } },
                    {
                        onSuccess: (paper) => { onClose(); router.push(`/dashboard/question-bank/papers/${paper.id}`); },
                        onError: (e) => setError(inventoryErrorMessage(e, "Could not create the paper")),
                    }
                );
            }}
        >
            {choices.isLoading ? <LoadingState className="py-6" /> : (
                <>
                    <Field label="Examination" htmlFor="np-exam">
                        <select id="np-exam" className={SELECT_CLASS} value={examination} onChange={(e) => setExamination(e.target.value)}>
                            <option value="">Choose an examination</option>
                            {(choices.data?.examinations ?? []).map((e) => <option key={e.id} value={e.id}>{e.name} ({e.academic_year})</option>)}
                        </select>
                    </Field>
                    <Field label="Subject" htmlFor="np-subject">
                        <select id="np-subject" className={SELECT_CLASS} value={subject} onChange={(e) => setSubject(e.target.value)}>
                            <option value="">Choose a subject</option>
                            {(choices.data?.subjects ?? []).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.level_name})</option>)}
                        </select>
                    </Field>
                    <div className="grid grid-cols-3 gap-3">
                        <Field label="Set" htmlFor="np-set"><Input id="np-set" maxLength={10} value={label} onChange={(e) => setLabel(e.target.value)} /></Field>
                        <Field label="Total marks" htmlFor="np-total" hint="Must match the exam schedule, if one exists."><Input id="np-total" inputMode="decimal" value={total} onChange={(e) => setTotal(e.target.value)} /></Field>
                        <Field label="Minutes" htmlFor="np-dur"><Input id="np-dur" inputMode="numeric" value={duration} onChange={(e) => setDuration(e.target.value)} /></Field>
                    </div>
                    <Field label="Title (optional)" htmlFor="np-title"><Input id="np-title" maxLength={200} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to subject and examination" /></Field>
                    <Field label="Instructions to students" htmlFor="np-instr">
                        <textarea id="np-instr" className="w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm min-h-[70px]" maxLength={2000} value={instructions} onChange={(e) => setInstructions(e.target.value)} />
                    </Field>
                    <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={shared} onChange={(e) => setShared(e.target.checked)} />
                        Allow questions that are also in another set of this paper
                    </label>
                </>
            )}
        </FormDialog>
    );
}

export default function PapersPage() {
    const { can } = usePermissions();
    const canPrepare = can("prepare_papers");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [status, setStatus] = useState<PaperStatus | "">("");
    const [creating, setCreating] = useState(false);
    const { data, isLoading, isError, refetch } = usePapers({ page, search, status });

    if (!(canPrepare || can("approve_papers") || can("view_examinations"))) {
        return <ErrorState message="You do not have permission to see question papers." />;
    }
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Question papers"
                description="Papers are built from approved questions, approved by someone other than their preparer, then frozen. Teachers of the subject can open a paper once it is released."
                actions={canPrepare && <Button onClick={() => setCreating(true)}>New paper</Button>}
            />
            <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                <Input type="text" placeholder="Search title, subject or examination" aria-label="Search papers" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Status" className={FILTER_SELECT_CLASS} value={status} onChange={(e) => { setPage(1); setStatus(e.target.value as PaperStatus | ""); }}>
                    <option value="">Any status</option>
                    {(Object.keys(PAPER_STATUS_LABELS) as PaperStatus[]).map((s) => <option key={s} value={s}>{PAPER_STATUS_LABELS[s]}</option>)}
                </select>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>
            {isLoading ? <LoadingState className="py-20" /> : isError ? (
                <ErrorState message="Failed to load the papers. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={search || status ? "No paper matches." : "No question papers yet."}
                    hint={canPrepare ? "Create a paper for a subject in an examination, then fill it from approved questions." : "Released papers of your subjects will appear here."}
                    action={canPrepare && !search && !status ? <Button onClick={() => setCreating(true)}>Create the first paper</Button> : undefined}
                />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        { key: "title", header: "Paper", primary: true, cell: (r) => <Link href={`/dashboard/question-bank/papers/${r.id}`} className="hover:underline">{r.title} · Set {r.set_label}</Link> },
                        { key: "subject", header: "Subject", cell: (r) => <>{r.subject_name} <span className="text-xs text-slate-500">({r.level_name})</span></> },
                        { key: "exam", header: "Examination", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.examination_name },
                        { key: "marks", header: "Marks", hideOnMobile: true, className: "text-slate-500", cell: (r) => `${Number(r.marks_so_far)} / ${Number(r.total_marks)} · ${r.question_count} questions` },
                        { key: "status", header: "Status", cell: (r) => <PaperStatusBadge status={r.status} /> },
                        { key: "release", header: "Release", hideOnMobile: true, className: "text-slate-500", cell: (r) => (r.released_at ? formatDateTime(r.released_at) : r.release_at ? `from ${formatDateTime(r.release_at)}` : "-") },
                    ]}
                    actionsHeader=""
                    actions={(r) => <Button asChild size="sm" variant="outline"><Link href={`/dashboard/question-bank/papers/${r.id}`}>Open</Link></Button>}
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />
            <NewPaperDialog open={creating} onClose={() => setCreating(false)} />
        </div>
    );
}
