"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { AdjustmentDialog, CancelRunDialog, PayDialog } from "@/components/dashboard/payroll/RunDialogs";
import { PageHeader, Pager, RunStatusBadge, formatDate, formatMoney } from "@/components/dashboard/payroll/shared";
import {
    openProtectedFile, useRemoveAdjustment, useRun, useRunAction, useRunAdjustments, useRunPayslips, useRunSummary,
} from "@/hooks/usePayroll";
import { usePermissions } from "@/providers/PermissionProvider";
import { PAYMENT_METHOD_LABELS, PaymentMethod, RunStatus } from "@/types/Payroll";

const STEPS: { status: RunStatus; label: string }[] = [
    { status: "draft", label: "Started" },
    { status: "calculated", label: "Calculated" },
    { status: "approved", label: "Approved" },
    { status: "paid", label: "Paid" },
];

function Stepper({ status }: { status: RunStatus }) {
    if (status === "cancelled") return null;
    const current = STEPS.findIndex((s) => s.status === status);
    return (
        <ol className="flex flex-wrap gap-2" aria-label="Progress">
            {STEPS.map((step, index) => (
                <li
                    key={step.status}
                    aria-current={index === current ? "step" : undefined}
                    className={`rounded-full px-3 py-1 text-xs font-semibold ${
                        index < current ? "bg-emerald-100 text-emerald-700" : index === current ? "bg-sky-600 text-white" : "bg-slate-100 text-slate-500"
                    }`}
                >
                    {index + 1}. {step.label}
                </li>
            ))}
        </ol>
    );
}

export default function PayrollRunPage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const { can } = usePermissions();
    const { data: run, isLoading, isError, refetch } = useRun(id);
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [problemsOnly, setProblemsOnly] = useState(false);
    const [paying, setPaying] = useState(false);
    const [cancelling, setCancelling] = useState(false);
    const [adding, setAdding] = useState(false);
    const [showSummary, setShowSummary] = useState(false);
    const payslips = useRunPayslips(id, { page, search, problems: problemsOnly });
    const adjustments = useRunAdjustments(id);
    const summary = useRunSummary(id, showSummary);
    const action = useRunAction();
    const removeAdjustment = useRemoveAdjustment();

    if (!can("view_payroll")) return <ErrorState message="You do not have permission to view payroll." />;
    if (isLoading) return <LoadingState className="py-20" />;
    if (isError || !run) return <ErrorState message="Could not load this payroll." onRetry={refetch} />;

    const notes = run.calculation_notes;
    const editable = run.status === "draft" || run.status === "calculated";
    const locked = run.status === "approved" || run.status === "paid";
    const negative = notes.negative_net ?? 0;
    const unmarked = notes.unmarked_staff ?? 0;
    const skipped = notes.skipped_no_salary ?? [];
    const canCancel = run.status !== "paid" && run.status !== "cancelled" && (run.status === "approved" ? can("run_payroll") && can("approve_payroll") : can("run_payroll"));
    const slips = payslips.data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title={`${run.month_label} payroll`}
                description={`${formatDate(run.period_start)} to ${formatDate(run.period_end)}${run.working_days ? ` · ${run.working_days} working days` : ""}`}
                actions={<Button asChild variant="outline"><Link href="/dashboard/payroll">Back to all payrolls</Link></Button>}
            />
            <div className="flex flex-wrap items-center gap-3">
                <RunStatusBadge status={run.status} />
                <Stepper status={run.status} />
            </div>

            {/* What to do next, in plain words */}
            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                {run.status === "draft" && <p className="text-sm">This payroll has not been calculated yet. Calculating works out everyone&apos;s pay for the month from their salary, attendance and leave.</p>}
                {run.status === "calculated" && <p className="text-sm">Check the payslips below. Fix anything that looks wrong (change a salary, correct attendance, or add a one-off amount) and calculate again. When it looks right, ask someone else to approve it.</p>}
                {run.status === "approved" && <p className="text-sm">Approved and locked. Nothing can be changed now. Pay the staff, then record the payment here.</p>}
                {run.status === "paid" && <p className="text-sm">Paid on {formatDate(run.paid_on)} by {PAYMENT_METHOD_LABELS[run.payment_method as PaymentMethod] ?? run.payment_method}{run.payment_reference ? ` (${run.payment_reference})` : ""}. This payroll is closed.</p>}
                {run.status === "cancelled" && <p className="text-sm text-red-600">Cancelled: {run.cancellation_reason}. You can start a new payroll for this month.</p>}

                <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 [&>*]:w-full sm:[&>*]:w-auto">
                    {editable && can("run_payroll") && (
                        <Button disabled={action.isPending} onClick={() => action.mutate({ id: run.id, action: "calculate" })}>
                            {run.status === "draft" ? "Calculate payroll" : "Calculate again"}
                        </Button>
                    )}
                    {run.status === "calculated" && can("approve_payroll") && (
                        <Button disabled={action.isPending || negative > 0 || run.payslip_count === 0} onClick={() => action.mutate({ id: run.id, action: "approve" })}>
                            Approve payroll
                        </Button>
                    )}
                    {run.status === "approved" && can("record_payroll_payment") && <Button onClick={() => setPaying(true)}>Record payment</Button>}
                    {locked && (
                        <Button variant="outline" onClick={() => openProtectedFile(`/payroll/runs/${run.id}/export/`, `payroll-${run.year}-${String(run.month).padStart(2, "0")}.csv`, "save")}>
                            Download list (CSV)
                        </Button>
                    )}
                    {canCancel && <Button variant="outline" className="text-red-600" onClick={() => setCancelling(true)}>Cancel payroll</Button>}
                </div>
                {run.status === "calculated" && negative > 0 && <p className="text-xs text-red-600">It cannot be approved while any pay is below zero.</p>}
            </section>

            {/* Totals */}
            {run.payslip_count > 0 && (
                <dl className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {[["People", String(run.payslip_count)], ["Total earnings", formatMoney(run.total_gross)], ["Total deductions", formatMoney(run.total_deductions)], ["Total to pay (net)", formatMoney(run.total_net)]].map(([label, value]) => (
                        <div key={label} className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4">
                            <dt className="text-xs text-slate-500">{label}</dt>
                            <dd className="text-xl font-bold">{value}</dd>
                        </div>
                    ))}
                </dl>
            )}

            {/* Things worth a look */}
            {run.status === "calculated" && (negative > 0 || unmarked > 0 || skipped.length > 0) && (
                <section className="rounded-2xl border border-amber-300 bg-amber-50 dark:bg-amber-500/5 p-5 space-y-2 text-sm">
                    <h2 className="font-semibold text-amber-900 dark:text-amber-300">Please check before approving</h2>
                    {negative > 0 && <p>{negative} payslip(s) have pay below zero (shown in red below).</p>}
                    {unmarked > 0 && <p>{unmarked} staff member(s) have working days with no attendance marked. Those days are paid as normal. Mark attendance and calculate again if that is wrong.</p>}
                    {skipped.length > 0 && <p>{skipped.length} staff record(s) have no salary and are not in this payroll: {skipped.slice(0, 8).join(", ")}{skipped.length > 8 ? " and more" : ""}.</p>}
                </section>
            )}

            {/* Payslips */}
            <section className="space-y-3">
                <h2 className="text-lg font-bold">Payslips</h2>
                <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                    <Input type="text" placeholder="Search name or ID" aria-label="Search payslips" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                    <label className="flex items-center gap-2 text-sm">
                        <input type="checkbox" checked={problemsOnly} onChange={(e) => { setPage(1); setProblemsOnly(e.target.checked); }} />
                        Only ones to check
                    </label>
                    <Button type="submit" variant="outline">Search</Button>
                </FilterBar>
                {payslips.isLoading ? (
                    <LoadingState className="py-10" />
                ) : slips.length === 0 ? (
                    <EmptyHint title={run.status === "draft" ? "No payslips yet." : "No payslips match."} hint={run.status === "draft" ? "Calculate the payroll to create them." : "Try a different search."} />
                ) : (
                    <ResponsiveList
                        rows={slips}
                        rowKey={(p) => p.id}
                        columns={[
                            { key: "name", header: "Staff member", primary: true, cell: (p) => <>{p.staff_name} <span className="text-xs font-normal text-slate-500">({p.employee_id})</span></> },
                            { key: "net", header: "Net pay", className: "font-bold", cell: (p) => <span className={p.net_is_negative ? "text-red-600" : ""}>{formatMoney(p.net_amount)}</span> },
                            { key: "gross", header: "Earnings", cell: (p) => formatMoney(p.gross_amount) },
                            { key: "ded", header: "Deductions", cell: (p) => formatMoney(p.deductions_amount) },
                            { key: "unpaid", header: "Unpaid days", cell: (p) => Number(p.unpaid_days) > 0 ? p.unpaid_days.replace(/\.0$/, "") : "-" },
                            { key: "unmarked", header: "Attendance not marked", hideOnMobile: true, cell: (p) => Number(p.unmarked_days) > 0 ? `${p.unmarked_days.replace(/\.0$/, "")} days` : "-" },
                        ]}
                        actionsHeader="Payslip"
                        actions={(p) => (
                            <>
                                <Button asChild size="sm" variant="outline"><Link href={`/dashboard/payroll/payslips/${p.id}`}>View</Link></Button>
                                <Button size="sm" variant="ghost" onClick={() => openProtectedFile(`/payroll/payslips/${p.id}/pdf/`, "payslip.pdf", "open")}>PDF</Button>
                            </>
                        )}
                    />
                )}
                <Pager data={payslips.data} page={page} onPage={setPage} />
            </section>

            {/* One-off amounts */}
            <section className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-lg font-bold">One-off amounts</h2>
                    {editable && can("run_payroll") && <Button size="sm" variant="outline" onClick={() => setAdding(true)}>Add a one-off amount</Button>}
                </div>
                {(adjustments.data?.results ?? []).length === 0 ? (
                    <p className="text-sm text-slate-500">None. Use these for a bonus, an advance being recovered, or a correction.</p>
                ) : (
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800">
                        {(adjustments.data?.results ?? []).map((a) => (
                            <li key={a.id} className="p-3 flex flex-wrap items-center gap-2 text-sm">
                                <span className="font-medium">{a.staff_name}</span>
                                <span className="text-slate-500">{a.name} · {a.reason}</span>
                                <span className={`ml-auto font-bold ${a.kind === "deduction" ? "text-red-600" : "text-emerald-600"}`}>
                                    {a.kind === "deduction" ? "−" : "+"}{formatMoney(a.amount)}
                                </span>
                                {editable && can("run_payroll") && (
                                    <Button size="sm" variant="ghost" disabled={removeAdjustment.isPending} onClick={() => removeAdjustment.mutate(a.id)}>Remove</Button>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            {/* Summary */}
            {run.payslip_count > 0 && (
                <section className="space-y-3">
                    <Button variant="outline" onClick={() => setShowSummary((v) => !v)} aria-expanded={showSummary}>
                        {showSummary ? "Hide the summary" : "Show the summary by department and pay item"}
                    </Button>
                    {showSummary && summary.data && (
                        <div className="grid lg:grid-cols-2 gap-6 text-sm">
                            <div className="space-y-2">
                                <h3 className="font-semibold">By department</h3>
                                <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800">
                                    {summary.data.by_department.map((d) => (
                                        <li key={d.department} className="p-3 flex justify-between gap-3">
                                            <span>{d.department} <span className="text-slate-500">({d.people})</span></span>
                                            <span className="font-semibold">{formatMoney(d.net)}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                            <div className="space-y-2">
                                <h3 className="font-semibold">By pay item</h3>
                                <ul className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800">
                                    {summary.data.by_component.map((c) => (
                                        <li key={c.code + c.name} className="p-3 flex justify-between gap-3">
                                            <span>{c.name} <span className="text-slate-500">({c.people})</span></span>
                                            <span className={`font-semibold ${c.kind === "deduction" ? "text-red-600" : ""}`}>{c.kind === "deduction" ? "−" : ""}{formatMoney(c.total)}</span>
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        </div>
                    )}
                </section>
            )}

            <PayDialog run={paying ? run : null} onClose={() => setPaying(false)} />
            <CancelRunDialog run={cancelling ? run : null} onClose={() => setCancelling(false)} />
            <AdjustmentDialog run={run} open={adding} onClose={() => setAdding(false)} />
        </div>
    );
}
