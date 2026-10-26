"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { PageHeader, SELECT_CLASS, useCanUseBank } from "@/components/dashboard/question-bank/shared";
import { useStaffMembers } from "@/hooks/useStaff";
import {
    useAddReviewer, useChapters, useDeleteChapter, useDeleteTopic, useMyScope, useRemoveReviewer, useReviewers, useSaveChapter, useSaveTopic,
} from "@/hooks/useQuestionBank";
import { usePermissions } from "@/providers/PermissionProvider";
import { Chapter } from "@/types/QuestionBank";

function ChapterRow({ chapter, canEdit }: { chapter: Chapter; canEdit: boolean }) {
    const addTopic = useSaveTopic();
    const removeTopic = useDeleteTopic();
    const removeChapter = useDeleteChapter();
    const [topic, setTopic] = useState("");
    return (
        <li className="py-3 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
                <span className="w-6 text-slate-400">{chapter.order}</span>
                <span className="font-medium">{chapter.name}</span>
                {canEdit && <Button size="sm" variant="ghost" className="ml-auto text-red-600" disabled={removeChapter.isPending} onClick={() => removeChapter.mutate(chapter.id)}>Delete chapter</Button>}
            </div>
            <div className="pl-8 flex flex-wrap gap-2">
                {chapter.topics.map((t) => (
                    <span key={t.id} className="inline-flex items-center gap-1 rounded-full bg-slate-100 dark:bg-slate-800 px-3 py-1 text-xs">
                        {t.name}
                        {canEdit && <button type="button" aria-label={`Delete topic ${t.name}`} className="text-slate-400 hover:text-red-600" onClick={() => removeTopic.mutate(t.id)}>×</button>}
                    </span>
                ))}
                {chapter.topics.length === 0 && <span className="text-xs text-slate-500">No topics yet.</span>}
            </div>
            {canEdit && (
                <form
                    className="pl-8 flex gap-2"
                    onSubmit={(e) => {
                        e.preventDefault();
                        if (!topic.trim()) return;
                        addTopic.mutate({ chapter: chapter.id, name: topic.trim(), order: chapter.topics.length + 1 }, { onSuccess: () => setTopic("") });
                    }}
                >
                    <Input aria-label={`New topic in ${chapter.name}`} placeholder="Add a topic" value={topic} maxLength={150} onChange={(e) => setTopic(e.target.value)} />
                    <Button type="submit" size="sm" variant="outline" disabled={addTopic.isPending}>Add</Button>
                </form>
            )}
        </li>
    );
}

function Chapters({ canEdit }: { canEdit: boolean }) {
    const scope = useMyScope();
    const subjects = [...(scope.data?.can_write ?? []), ...(scope.data?.can_review ?? [])].filter((s, i, all) => all.findIndex((x) => x.id === s.id) === i);
    const [subject, setSubject] = useState("");
    const chapters = useChapters(subject);
    const save = useSaveChapter();
    const [name, setName] = useState("");
    const list = chapters.data ?? [];

    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
            <h2 className="font-semibold text-slate-900 dark:text-white">Chapters and topics</h2>
            <select aria-label="Subject" className={SELECT_CLASS} value={subject} onChange={(e) => setSubject(e.target.value)}>
                <option value="">Choose a subject</option>
                {subjects.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.level_name})</option>)}
            </select>
            {!subject ? (
                <p className="text-sm text-slate-500">Choose a subject to see its chapters.</p>
            ) : chapters.isLoading ? (
                <LoadingState className="py-4" />
            ) : (
                <>
                    {list.length === 0 && <p className="text-sm text-slate-500">No chapters yet for this subject.</p>}
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                        {list.map((c) => <ChapterRow key={c.id} chapter={c} canEdit={canEdit} />)}
                    </ul>
                    {canEdit && (
                        <form
                            className="flex gap-2"
                            onSubmit={(e) => {
                                e.preventDefault();
                                if (!name.trim()) return;
                                save.mutate({ input: { subject, name: name.trim(), order: list.length + 1 } }, { onSuccess: () => setName("") });
                            }}
                        >
                            <Input aria-label="New chapter" placeholder="Add a chapter, e.g. Fractions" value={name} maxLength={150} onChange={(e) => setName(e.target.value)} />
                            <Button type="submit" disabled={save.isPending}>Add chapter</Button>
                        </form>
                    )}
                </>
            )}
        </section>
    );
}

function Reviewers({ canEdit }: { canEdit: boolean }) {
    const reviewers = useReviewers();
    const scope = useMyScope();
    const add = useAddReviewer();
    const remove = useRemoveReviewer();
    const [search, setSearch] = useState("");
    const staff = useStaffMembers({ pageSize: 50, search, isActive: true });
    const [subject, setSubject] = useState("");
    const [person, setPerson] = useState("");
    const rows = reviewers.data ?? [];

    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
            <h2 className="font-semibold text-slate-900 dark:text-white">Subject reviewers</h2>
            <p className="text-sm text-slate-500">
                A reviewer approves the questions of their subjects. They also need the Review Questions permission in their role, and they never review their own questions.
            </p>
            {reviewers.isLoading ? <LoadingState className="py-4" /> : rows.length === 0 ? (
                <p className="text-sm text-slate-500">No reviewers yet, so no question can be approved.</p>
            ) : (
                <ul className="divide-y divide-slate-100 dark:divide-slate-800 text-sm">
                    {rows.map((r) => (
                        <li key={r.id} className="py-2 flex flex-wrap items-center gap-2">
                            <span className="font-medium">{r.staff_name}</span>
                            <span className="text-slate-500">reviews {r.subject_name} ({r.level_name})</span>
                            {canEdit && <Button size="sm" variant="ghost" className="ml-auto text-red-600" disabled={remove.isPending} onClick={() => remove.mutate(r.id)}>Remove</Button>}
                        </li>
                    ))}
                </ul>
            )}
            {canEdit && (
                <form
                    className="grid sm:grid-cols-3 gap-2 items-start"
                    onSubmit={(e) => {
                        e.preventDefault();
                        if (!subject || !person) return;
                        add.mutate({ subject, staff: person }, { onSuccess: () => setPerson("") });
                    }}
                >
                    <select aria-label="Subject to review" className={SELECT_CLASS} value={subject} onChange={(e) => setSubject(e.target.value)}>
                        <option value="">Subject</option>
                        {(scope.data?.can_write ?? []).map((s) => <option key={s.id} value={s.id}>{s.name} ({s.level_name})</option>)}
                    </select>
                    <div className="space-y-2">
                        <Input aria-label="Search staff" placeholder="Search staff" value={search} onChange={(e) => setSearch(e.target.value)} />
                        <select aria-label="Reviewer" className={SELECT_CLASS} value={person} onChange={(e) => setPerson(e.target.value)}>
                            <option value="">Choose a person</option>
                            {(staff.data?.results ?? []).map((s) => <option key={s.id} value={s.id}>{s.profile_details.first_name} {s.profile_details.last_name} ({s.employee_id})</option>)}
                        </select>
                    </div>
                    <Button type="submit" disabled={add.isPending || !subject || !person}>Add reviewer</Button>
                </form>
            )}
        </section>
    );
}

export default function QuestionBankSetupPage() {
    const canUse = useCanUseBank();
    const { can } = usePermissions();
    const canEdit = can("manage_question_bank");
    if (!canUse) return <ErrorState message="You do not have permission to use the question bank." />;
    return (
        <div className="space-y-6">
            <PageHeader title="Chapters & reviewers" description="The chapter and topic list of each subject, and who approves its questions." />
            <Chapters canEdit={canEdit} />
            <Reviewers canEdit={canEdit} />
        </div>
    );
}
