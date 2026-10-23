"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { EmptyHint } from "@/components/common/PageLayout";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { PayslipView } from "@/components/dashboard/payroll/PayslipView";
import { PageHeader, Pager, formatMoney } from "@/components/dashboard/payroll/shared";
import { openProtectedFile, useMyPayslip, useMyPayslips } from "@/hooks/usePayroll";

function Selected({ id, onClose }: { id: string; onClose: () => void }) {
    const { data, isLoading, isError } = useMyPayslip(id);
    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-4">
            <Button variant="ghost" size="sm" onClick={onClose}>← Back to the list</Button>
            {isLoading ? (
                <LoadingState className="py-10" />
            ) : isError || !data ? (
                <ErrorState message="Could not load this payslip." />
            ) : (
                <PayslipView payslip={data} onPdf={() => openProtectedFile(`/payroll/my-payslips/${data.id}/pdf/`, "payslip.pdf", "open")} />
            )}
        </section>
    );
}

export default function MyPayslipsPage() {
    const [page, setPage] = useState(1);
    const [selected, setSelected] = useState<string | null>(null);
    const { data, isLoading, isError, error, refetch } = useMyPayslips(page);
    const status = (error as { response?: { status?: number } } | null)?.response?.status;

    if (status === 403) {
        return <ErrorState message="Payslips are only available to staff members." description="If you are staff and cannot see yours, ask the school to check your account." />;
    }
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6 max-w-3xl">
            <PageHeader title="My payslips" description="Your pay for each month, once the school has approved it. Only you can see these." />
            {selected ? (
                <Selected id={selected} onClose={() => setSelected(null)} />
            ) : isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load your payslips. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint title="No payslips yet." hint="Your payslip appears here after the school approves the month's payroll. You will get a notification." />
            ) : (
                <ul className="space-y-3">
                    {rows.map((slip) => (
                        <li key={slip.id}>
                            <button
                                type="button"
                                onClick={() => setSelected(slip.id)}
                                className="w-full text-left rounded-2xl border border-slate-200 dark:border-slate-800 p-4 flex flex-wrap items-center justify-between gap-2 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                            >
                                <span className="font-semibold text-slate-900 dark:text-white">{slip.month_label}</span>
                                <span className="text-xs text-slate-500">{slip.run_status === "paid" ? "Paid" : "Approved"}</span>
                                <span className="font-bold">NPR {formatMoney(slip.net_amount)}</span>
                            </button>
                        </li>
                    ))}
                </ul>
            )}
            {!selected && <Pager data={data} page={page} onPage={setPage} />}
        </div>
    );
}
