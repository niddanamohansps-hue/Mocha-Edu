"use client";

import { CURRENCY } from "@/lib/currency";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { Field, FILTER_SELECT_CLASS, FormDialog, PageHeader, Pager, Pill, formatDate, formatMoney } from "@/components/dashboard/library/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useBillFine, useCollectFine, useFines, useWaiveFine } from "@/hooks/useLibrary";
import { usePermissions } from "@/providers/PermissionProvider";
import { FINE_STATUS_LABELS, Fine, FineStatus } from "@/types/Library";

const STATUS_STYLES: Record<FineStatus, string> = {
    pending: "bg-amber-100 text-amber-700",
    billed: "bg-sky-100 text-sky-700",
    collected: "bg-emerald-100 text-emerald-700",
    waived: "bg-slate-200 text-slate-600",
};

function WaiveDialog({ fine, onClose }: { fine: Fine | null; onClose: () => void }) {
    return fine ? <WaiveForm key={fine.id} fine={fine} onClose={onClose} /> : null;
}

function WaiveForm({ fine, onClose }: { fine: Fine; onClose: () => void }) {
    const waive = useWaiveFine();
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(o) => !o && onClose()}
            title="Waive this fine"
            description={`${CURRENCY} ${formatMoney(fine.amount)} for ${fine.borrower_name}. The fine is cancelled and nothing is charged.`}
            submitLabel="Waive fine"
            pending={waive.isPending}
            error={error}
            onSubmit={() => {
                if (!reason.trim()) return setError("Give the reason. It is kept on record.");
                setError(null);
                waive.mutate({ id: fine.id, reason: reason.trim() }, { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not waive the fine")) });
            }}
        >
            <Field label="Reason" htmlFor="wv-reason"><Input id="wv-reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} /></Field>
        </FormDialog>
    );
}

export default function FinesPage() {
    const { can } = usePermissions();
    const canManage = can("manage_library_fines");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [status, setStatus] = useState<FineStatus | "">("pending");
    const { data, isLoading, isError, refetch } = useFines({ page, search, status });
    const bill = useBillFine();
    const collect = useCollectFine();
    const [billing, setBilling] = useState<Fine | null>(null);
    const [waiving, setWaiving] = useState<Fine | null>(null);

    if (!can("view_library")) return <ErrorState message="You do not have permission to view the library." />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Fines"
                description="Raised when a book comes back late or is lost. A student's fine is added to Fees, where it is paid and receipted. A staff member's is collected here."
            />
            <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                <Input type="text" placeholder="Search borrower or book" aria-label="Search fines" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Fine status" className={FILTER_SELECT_CLASS} value={status} onChange={(e) => { setPage(1); setStatus(e.target.value as FineStatus | ""); }}>
                    <option value="pending">Waiting for action</option>
                    <option value="billed">Billed in Fees</option>
                    <option value="collected">Collected</option>
                    <option value="waived">Waived</option>
                    <option value="">All</option>
                </select>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load fines. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={search || status !== "pending" ? "No fines match." : "No fines are waiting."}
                    hint={search || status !== "pending" ? "Try a different search or status." : "Fines appear here when a book is returned late or lost. Set the daily rate under Setup."}
                />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        {
                            key: "who", header: "Borrower", primary: true,
                            cell: (r) => <>{r.borrower_name} <span className="text-xs font-normal text-slate-500">({r.borrower_ref}{r.borrower_type === "staff" ? ", staff" : ""})</span></>,
                        },
                        { key: "book", header: "Book", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.book_title },
                        {
                            key: "why", header: "Reason", hideOnMobile: true, className: "text-slate-500",
                            cell: (r) => (r.kind === "lost" ? "Lost book" : `${r.days_overdue} day${r.days_overdue === 1 ? "" : "s"} late`),
                        },
                        { key: "amount", header: "Amount", className: "font-bold", cell: (r) => formatMoney(r.amount) },
                        {
                            key: "status", header: "Status",
                            cell: (r) => (
                                <>
                                    <Pill className={STATUS_STYLES[r.status]}>{FINE_STATUS_LABELS[r.status]}</Pill>
                                    {r.status === "waived" && r.waive_reason && <span className="ml-2 text-xs text-slate-500">{r.waive_reason}</span>}
                                    {r.resolved_at && r.status !== "waived" && <span className="ml-2 text-xs text-slate-500">{formatDate(r.resolved_at)}</span>}
                                </>
                            ),
                        },
                    ]}
                    actionsHeader="Actions"
                    actions={(r) =>
                        canManage && r.status === "pending" ? (
                            <div className="flex flex-wrap justify-end gap-1">
                                {r.borrower_type === "student" ? (
                                    <Button size="sm" variant="outline" disabled={bill.isPending} onClick={() => setBilling(r)}>Bill in Fees</Button>
                                ) : (
                                    <Button size="sm" variant="outline" disabled={collect.isPending} onClick={() => collect.mutate(r.id)}>Mark collected</Button>
                                )}
                                <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setWaiving(r)}>Waive</Button>
                            </div>
                        ) : null
                    }
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />

            <WaiveDialog fine={waiving} onClose={() => setWaiving(null)} />
            <ConfirmationDialog
                open={!!billing}
                onOpenChange={(o) => !o && setBilling(null)}
                title={`Bill ${CURRENCY} ${formatMoney(billing?.amount)} to ${billing?.borrower_name ?? ""}?`}
                description="A Library fee is added to the student's fees. They pay it there, and the receipt comes from Fees."
                confirmLabel="Bill in Fees"
                isLoading={bill.isPending}
                onConfirm={() => billing && bill.mutate(billing.id, { onSettled: () => setBilling(null) })}
            />
        </div>
    );
}
