"use client";

import { CURRENCY } from "@/lib/currency";
import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { IssueDialog } from "@/components/dashboard/library/IssueDialog";
import { FILTER_SELECT_CLASS, PageHeader, Pager, Pill, formatDate, formatMoney } from "@/components/dashboard/library/shared";
import { useLoans, useRenewLoan, useReportLost, useReturnBook } from "@/hooks/useLibrary";
import { usePermissions } from "@/providers/PermissionProvider";
import { ClosedLoanResult, Loan, LoanState } from "@/types/Library";

function StatusPill({ loan }: { loan: Loan }) {
    if (!loan.is_open) {
        return loan.outcome === "lost"
            ? <Pill className="bg-red-100 text-red-700">Lost</Pill>
            : <Pill className="bg-slate-200 text-slate-600">Returned</Pill>;
    }
    return loan.is_overdue
        ? <Pill className="bg-amber-100 text-amber-700">{loan.days_overdue} day{loan.days_overdue === 1 ? "" : "s"} late</Pill>
        : <Pill className="bg-emerald-100 text-emerald-700">On loan</Pill>;
}

function ClosedNotice({ result, onDismiss }: { result: ClosedLoanResult; onDismiss: () => void }) {
    const lost = result.outcome === "lost";
    return (
        <section className={`rounded-2xl border p-4 text-sm space-y-1 ${result.fine ? "border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30" : "border-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 dark:border-emerald-500/30"}`}>
            <p className="font-semibold">
                {lost ? `${result.book_title} was recorded as lost.` : `${result.book_title} is back on the shelf.`}
            </p>
            {result.fine ? (
                <p>
                    A fine of {CURRENCY} {formatMoney(result.fine.amount)} was raised for {result.borrower_name}
                    {result.fine.kind === "overdue" ? ` (${result.fine.days_overdue} days late)` : " (lost book)"}.{" "}
                    <Link href="/dashboard/library/fines" className="underline font-medium">Go to Fines</Link> to bill, collect or waive it.
                </p>
            ) : (
                <p>No fine was raised.</p>
            )}
            <Button size="sm" variant="ghost" onClick={onDismiss}>Dismiss</Button>
        </section>
    );
}

export default function LoansPage() {
    const { can } = usePermissions();
    const canLend = can("lend_library_books");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [state, setState] = useState<LoanState>("open");
    const { data, isLoading, isError, refetch } = useLoans({ page, search, state });
    const giveBack = useReturnBook();
    const lose = useReportLost();
    const renew = useRenewLoan();
    const [issuing, setIssuing] = useState(false);
    const [losing, setLosing] = useState<Loan | null>(null);
    const [result, setResult] = useState<ClosedLoanResult | null>(null);

    if (!can("view_library")) return <ErrorState message="You do not have permission to view the library." />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Loans"
                description="Books lent out, and taken back. A late return raises a fine when the school charges one."
                actions={canLend && <Button onClick={() => setIssuing(true)}>Issue a book</Button>}
            />
            {result && <ClosedNotice result={result} onDismiss={() => setResult(null)} />}
            <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                <Input type="text" placeholder="Search borrower, title or accession number" aria-label="Search loans" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Loan status" className={FILTER_SELECT_CLASS} value={state} onChange={(e) => { setPage(1); setState(e.target.value as LoanState); }}>
                    <option value="open">On loan now</option>
                    <option value="overdue">Overdue</option>
                    <option value="closed">Returned or lost</option>
                    <option value="">All</option>
                </select>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load loans. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={search || state !== "open" ? "No loans match." : "Nothing is on loan."}
                    hint={search || state !== "open" ? "Try a different search or status." : "Issue a book to start."}
                    action={!search && state === "open" && canLend ? <Button onClick={() => setIssuing(true)}>Issue the first book</Button> : undefined}
                />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        { key: "book", header: "Book", primary: true, cell: (r) => <>{r.book_title} <span className="text-xs font-normal text-slate-500">({r.accession_number})</span></> },
                        {
                            key: "who", header: "Borrower",
                            cell: (r) => <>{r.borrower_name} <span className="text-xs font-normal text-slate-500">({r.borrower_ref}{r.borrower_type === "staff" ? ", staff" : ""})</span></>,
                        },
                        { key: "issued", header: "Issued", hideOnMobile: true, className: "text-slate-500", cell: (r) => formatDate(r.issued_on) },
                        { key: "due", header: "Due / returned", className: "text-slate-500", cell: (r) => formatDate(r.is_open ? r.due_on : r.returned_on) },
                        { key: "status", header: "Status", cell: (r) => <StatusPill loan={r} /> },
                    ]}
                    actionsHeader="Actions"
                    actions={(r) =>
                        canLend && r.is_open ? (
                            <div className="flex flex-wrap justify-end gap-1">
                                <Button size="sm" variant="outline" disabled={giveBack.isPending} onClick={() => giveBack.mutate(r.id, { onSuccess: setResult })}>Take back</Button>
                                {!r.is_overdue && <Button size="sm" variant="ghost" disabled={renew.isPending} onClick={() => renew.mutate(r.id)}>Renew</Button>}
                                <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setLosing(r)}>Lost</Button>
                            </div>
                        ) : null
                    }
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />

            <IssueDialog open={issuing} onClose={() => setIssuing(false)} />
            <ConfirmationDialog
                open={!!losing}
                onOpenChange={(o) => !o && setLosing(null)}
                title={`Record ${losing?.book_title ?? "the book"} as lost?`}
                description="The loan closes, the copy leaves the shelf, and the borrower is charged the book's price if it has one."
                confirmLabel="Record as lost"
                isLoading={lose.isPending}
                onConfirm={() => losing && lose.mutate(losing.id, { onSuccess: setResult, onSettled: () => setLosing(null) })}
            />
        </div>
    );
}
