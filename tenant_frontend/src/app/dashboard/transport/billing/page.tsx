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
import { Field, PageHeader, Pager, formatMoney, monthValue } from "@/components/dashboard/transport/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useBills, useRunBilling } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { BillRunResult } from "@/types/Transport";

function ResultCard({ result }: { result: BillRunResult }) {
    return (
        <section className="rounded-2xl border border-emerald-300 bg-emerald-50 dark:bg-emerald-500/10 dark:border-emerald-500/30 p-4 text-sm space-y-1">
            <p className="font-semibold text-emerald-900 dark:text-emerald-300">
                {result.billed === 0 ? "Nothing new to bill." : `Billed ${result.billed} student${result.billed === 1 ? "" : "s"}, ${CURRENCY} ${formatMoney(result.total)} in all.`}
            </p>
            {result.already_billed > 0 && <p>{result.already_billed} already billed earlier, left alone.</p>}
            {result.no_fee > 0 && <p>{result.no_fee} use a stop with no fee, so were not billed.</p>}
            {result.no_enrollment.length > 0 && (
                <p className="text-amber-800 dark:text-amber-300">
                    Not billed because they are not enrolled in a class this year: {result.no_enrollment.join(", ")}.
                </p>
            )}
            <p className="text-xs text-slate-500">The fees are in Fees under the Transport head, ready for payment.</p>
        </section>
    );
}

export default function TransportBillingPage() {
    const { can } = usePermissions();
    const canBill = can("bill_transport");
    const [month, setMonth] = useState(() => monthValue());
    const [dueDate, setDueDate] = useState("");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [confirming, setConfirming] = useState(false);
    const [result, setResult] = useState<BillRunResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const run = useRunBilling();
    const { data, isLoading, isError, refetch } = useBills({ page, month, search });

    if (!can("view_transport")) return <ErrorState message="You do not have permission to view transport." />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Transport billing"
                description="Once a month, add the transport fee to every student who has a seat. Running it again never bills anyone twice."
            />

            {canBill && (
                <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Bill a month</h2>
                    <div className="grid sm:grid-cols-3 gap-3 items-end">
                        <Field label="Month" htmlFor="bill-month"><Input id="bill-month" type="month" value={month} onChange={(e) => { setMonth(e.target.value); setResult(null); setPage(1); }} /></Field>
                        <Field label="Due date (optional)" htmlFor="bill-due" hint="Leave empty for the last day of the month.">
                            <Input id="bill-due" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
                        </Field>
                        <Button disabled={!month || run.isPending} onClick={() => { setError(null); setConfirming(true); }}>Bill this month</Button>
                    </div>
                    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
                </section>
            )}
            {result && <ResultCard result={result} />}

            <section className="space-y-3">
                <h2 className="font-semibold text-slate-900 dark:text-white">Billed for this month</h2>
                <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                    <Input type="text" placeholder="Search name or ID" aria-label="Search students" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                    <Button type="submit" variant="outline">Search</Button>
                </FilterBar>
                {isLoading ? (
                    <LoadingState className="py-10" />
                ) : isError ? (
                    <ErrorState message="Failed to load the bills. Please try again." onRetry={refetch} />
                ) : rows.length === 0 ? (
                    <EmptyHint title="Nothing billed for this month yet." hint={canBill ? "Use Bill this month above." : "Ask someone who can run the billing."} />
                ) : (
                    <ResponsiveList
                        rows={rows}
                        rowKey={(r) => r.id}
                        columns={[
                            { key: "name", header: "Student", primary: true, cell: (r) => <>{r.student_name} <span className="text-xs font-normal text-slate-500">({r.enrollment_id})</span></> },
                            { key: "route", header: "Route", cell: (r) => r.route_name },
                            { key: "stop", header: "Stop", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.stop_name || "-" },
                            { key: "amount", header: "Billed", className: "font-bold", cell: (r) => formatMoney(r.amount) },
                        ]}
                    />
                )}
                <Pager data={data} page={page} onPage={setPage} />
            </section>

            <ConfirmationDialog
                open={confirming}
                onOpenChange={setConfirming}
                title={`Bill transport for ${month}?`}
                description="This adds a fee to each student with a seat in that month. Anyone already billed for the month is skipped."
                confirmLabel="Bill month"
                isLoading={run.isPending}
                onConfirm={() =>
                    run.mutate(
                        { month, ...(dueDate ? { due_date: dueDate } : {}) },
                        {
                            onSuccess: (r) => setResult(r),
                            onError: (e) => setError(inventoryErrorMessage(e, "Could not bill the month")),
                            onSettled: () => setConfirming(false),
                        }
                    )
                }
            />
        </div>
    );
}
