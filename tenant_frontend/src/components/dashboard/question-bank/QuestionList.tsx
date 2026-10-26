"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { FILTER_SELECT_CLASS, Pager, StatusBadge, formatDate } from "@/components/dashboard/question-bank/shared";
import { QuestionFilters, useMyScope, useQuestions } from "@/hooks/useQuestionBank";
import { DIFFICULTY_LABELS, QuestionStatus, QuestionType, STATUS_LABELS, TYPE_LABELS } from "@/types/QuestionBank";

const EMPTY: QuestionFilters = { page: 1, search: "", subject: "", status: "", question_type: "", difficulty: "", mine: false, to_review: false };

/** The question table, shared by the bank and the review queue. */
export function QuestionList({ reviewQueue = false, emptyTitle, emptyHint, action }: {
    reviewQueue?: boolean; emptyTitle: string; emptyHint: string; action?: React.ReactNode;
}) {
    const [filters, setFilters] = useState<QuestionFilters>({ ...EMPTY, to_review: reviewQueue });
    const [searchText, setSearchText] = useState("");
    const { data, isLoading, isError, refetch } = useQuestions(filters);
    const scope = useMyScope();
    const set = (patch: Partial<QuestionFilters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));
    const rows = data?.results ?? [];
    const subjects = [...(scope.data?.can_write ?? []), ...(scope.data?.can_review ?? [])].filter((s, i, all) => all.findIndex((x) => x.id === s.id) === i);
    const filtered = filters.search || filters.subject || filters.status || filters.question_type || filters.difficulty || filters.mine;

    return (
        <div className="space-y-4">
            <FilterBar onSubmit={() => set({ search: searchText.trim() })}>
                <Input type="text" placeholder="Search the question text, chapter or topic" aria-label="Search questions" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Subject" className={FILTER_SELECT_CLASS} value={filters.subject} onChange={(e) => set({ subject: e.target.value })}>
                    <option value="">All subjects</option>
                    {subjects.map((s) => <option key={s.id} value={s.id}>{s.name} ({s.level_name})</option>)}
                </select>
                {!reviewQueue && (
                    <select aria-label="Status" className={FILTER_SELECT_CLASS} value={filters.status} onChange={(e) => set({ status: e.target.value as QuestionStatus | "" })}>
                        <option value="">Any status</option>
                        {(Object.keys(STATUS_LABELS) as QuestionStatus[]).map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
                    </select>
                )}
                <select aria-label="Type" className={FILTER_SELECT_CLASS} value={filters.question_type} onChange={(e) => set({ question_type: e.target.value as QuestionType | "" })}>
                    <option value="">Any type</option>
                    {(Object.keys(TYPE_LABELS) as QuestionType[]).map((t) => <option key={t} value={t}>{TYPE_LABELS[t]}</option>)}
                </select>
                {!reviewQueue && (
                    <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={filters.mine} onChange={(e) => set({ mine: e.target.checked })} />
                        Only mine
                    </label>
                )}
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load the questions. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint title={filtered ? "No question matches." : emptyTitle} hint={filtered ? "Try a different search or filter." : emptyHint} action={filtered ? undefined : action} />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        {
                            key: "body", header: "Question", primary: true,
                            cell: (r) => <Link href={`/dashboard/question-bank/${r.id}`} className="hover:underline">{r.body.length > 110 ? `${r.body.slice(0, 110)}…` : r.body}</Link>,
                        },
                        { key: "subject", header: "Subject", cell: (r) => <>{r.subject_name} <span className="text-xs text-slate-500">({r.level_name})</span></> },
                        { key: "chapter", header: "Chapter", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.chapter_name || "-" },
                        { key: "type", header: "Type", hideOnMobile: true, className: "text-slate-500", cell: (r) => `${TYPE_LABELS[r.question_type]} · ${DIFFICULTY_LABELS[r.difficulty]} · ${Number(r.marks)} mark${Number(r.marks) === 1 ? "" : "s"}` },
                        { key: "author", header: "Author", hideOnMobile: true, className: "text-slate-500", cell: (r) => (r.is_mine ? "You" : r.author_name || "-") },
                        { key: "status", header: "Status", cell: (r) => <StatusBadge status={r.status} /> },
                        { key: "updated", header: "Updated", hideOnMobile: true, className: "text-slate-500", cell: (r) => formatDate(r.updated_at) },
                    ]}
                    actionsHeader=""
                    actions={(r) => <Button asChild size="sm" variant="outline"><Link href={`/dashboard/question-bank/${r.id}`}>{reviewQueue ? "Review" : "Open"}</Link></Button>}
                />
            )}
            <Pager data={data} page={filters.page} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
        </div>
    );
}
