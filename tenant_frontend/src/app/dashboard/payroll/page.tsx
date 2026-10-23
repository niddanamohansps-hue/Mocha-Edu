"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { EmptyHint } from "@/components/common/PageLayout";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import {
    FILTER_SELECT_CLASS, Field, FormDialog, MONTHS, PageHeader, Pager, RunStatusBadge, SELECT_CLASS, formatMoney, previousMonth,
} from "@/components/dashboard/payroll/shared";
import { Input } from "@/components/ui/input";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useCreateRun, useRuns } from "@/hooks/usePayroll";
import { usePermissions } from "@/providers/PermissionProvider";
import { RUN_STATUS_LABELS, RunStatus } from "@/types/Payroll";

function NewRunDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
    return open ? <NewRunForm onClose={onClose} /> : null;
}

function NewRunForm({ onClose }: { onClose: () => void }) {
    const start = previousMonth();
    const create = useCreateRun();
    const [year, setYear] = useState(String(start.year));
    const [month, setMonth] = useState(String(start.month));
    const [notes, setNotes] = useState("");
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title="Start a payroll"
            description="Pick the month you are paying. You can calculate it, check it and fix problems before anyone is paid."
            submitLabel="Start payroll"
            pending={create.isPending}
            error={error}
            onSubmit={() => {
                const y = Number(year);
                if (!Number.isInteger(y) || y < 2000 || y > 2200) return setError("Enter a real year.");
                setError(null);
                create.mutate(
                    { year: y, month: Number(month), notes: notes.trim() },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not start the payroll")) }
                );
            }}
        >
            <div className="grid grid-cols-2 gap-3">
                <Field label="Month" htmlFor="run-month">
                    <select id="run-month" className={SELECT_CLASS} value={month} onChange={(e) => setMonth(e.target.value)}>
                        {MONTHS.map((name, index) => (
                            <option key={name} value={index + 1}>{name}</option>
                        ))}
                    </select>
                </Field>
                <Field label="Year" htmlFor="run-year">
                    <Input id="run-year" inputMode="numeric" value={year} onChange={(e) => setYear(e.target.value)} />
                </Field>
            </div>
            <Field label="Note (optional)" htmlFor="run-notes">
                <Input id="run-notes" value={notes} maxLength={255} onChange={(e) => setNotes(e.target.value)} />
            </Field>
        </FormDialog>
    );
}

export default function PayrollRunsPage() {
    const { can } = usePermissions();
    const [page, setPage] = useState(1);
    const [status, setStatus] = useState<RunStatus | "">("");
    const [creating, setCreating] = useState(false);
    const { data, isLoading, isError, refetch } = useRuns({ page, status });

    if (!can("view_payroll")) return <ErrorState message="You do not have permission to view payroll. You can still see your own payslips." />;
    const runs = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Payroll runs"
                description="One run pays everyone for one month. Start it, calculate it, check it, get it approved and then record the payment."
                actions={can("run_payroll") && <Button onClick={() => setCreating(true)}>Start a payroll</Button>}
            />
            <div className="flex flex-wrap gap-3">
                <select aria-label="Status" className={FILTER_SELECT_CLASS} value={status} onChange={(e) => { setPage(1); setStatus(e.target.value as RunStatus | ""); }}>
                    <option value="">All payrolls</option>
                    {(Object.keys(RUN_STATUS_LABELS) as RunStatus[]).map((s) => (
                        <option key={s} value={s}>{RUN_STATUS_LABELS[s]}</option>
                    ))}
                </select>
            </div>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load the payroll runs. Please try again." onRetry={refetch} />
            ) : runs.length === 0 ? (
                <EmptyHint
                    title={status ? "No payroll in this state." : "No payroll yet."}
                    hint={status ? "Try another filter." : "Before you start: set each person's salary on the Salaries tab, and make sure staff attendance and leave are up to date for the month."}
                    action={!status && can("run_payroll") ? <Button onClick={() => setCreating(true)}>Start your first payroll</Button> : undefined}
                />
            ) : (
                <div className="grid gap-3 md:grid-cols-2">
                    {runs.map((run) => (
                        <Link
                            key={run.id}
                            href={`/dashboard/payroll/runs/${run.id}`}
                            className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3 hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors"
                        >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <h2 className="text-lg font-bold text-slate-900 dark:text-white">{run.month_label}</h2>
                                <RunStatusBadge status={run.status} />
                            </div>
                            <dl className="grid grid-cols-3 gap-3 text-sm">
                                <div><dt className="text-xs text-slate-500">People</dt><dd className="font-semibold">{run.payslip_count}</dd></div>
                                <div><dt className="text-xs text-slate-500">Deductions</dt><dd className="font-semibold">{formatMoney(run.total_deductions)}</dd></div>
                                <div><dt className="text-xs text-slate-500">To pay (net)</dt><dd className="font-bold">{formatMoney(run.total_net)}</dd></div>
                            </dl>
                            {(run.calculation_notes.negative_net ?? 0) > 0 && run.status === "calculated" && (
                                <p className="text-xs text-red-600">{run.calculation_notes.negative_net} payslip(s) have pay below zero. Fix before approving.</p>
                            )}
                        </Link>
                    ))}
                </div>
            )}

            <Pager data={data} page={page} onPage={setPage} />
            <NewRunDialog open={creating} onClose={() => setCreating(false)} />
        </div>
    );
}
