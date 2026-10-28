"use client";

import { AlertTriangle, CalendarClock, CheckCircle2, Download, Loader2, RefreshCcw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import Unauthorized from "@/components/Unauthorized";
import { downloadInvoice, useCancelAutopay, useMyBilling, usePayNow, useStartAutopay } from "@/hooks/useBilling";
import { usePermissions } from "@/providers/PermissionProvider";

const CYCLE = { monthly: "Monthly", yearly: "Yearly", one_time: "One-time" } as const;
const TONE = {
    good: "bg-emerald-50 text-emerald-800 border-emerald-200 dark:bg-emerald-500/10 dark:text-emerald-300 dark:border-emerald-900",
    warn: "bg-amber-50 text-amber-800 border-amber-200 dark:bg-amber-500/10 dark:text-amber-300 dark:border-amber-900",
    bad: "bg-red-50 text-red-800 border-red-200 dark:bg-red-500/10 dark:text-red-300 dark:border-red-900",
};

const date = (value: string | null) =>
    value ? new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "";
const daysLeft = (value: string | null) =>
    value ? Math.max(0, Math.ceil((new Date(value).getTime() - Date.now()) / 86_400_000)) : 0;
const rupees = (value: string) => `₹${Number(value).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export default function BillingPage() {
    const { can } = usePermissions();
    const { data, isLoading, isError, refetch } = useMyBilling();
    const payNow = usePayNow();
    const startAutopay = useStartAutopay();
    const cancelAutopay = useCancelAutopay();

    if (!can("manage_billing")) return <Unauthorized />;
    if (isLoading) return <LoadingState className="py-16" />;
    if (isError || !data) return <ErrorState onRetry={refetch} />;

    const sub = data.subscription;
    const busy = payNow.isPending || startAutopay.isPending || cancelAutopay.isPending;

    let banner: { tone: keyof typeof TONE; icon: typeof CheckCircle2; text: string } | null = null;
    if (sub?.is_legacy) banner = { tone: "good", icon: CheckCircle2, text: "Your school has full access. There is nothing to pay right now." };
    else if (sub?.status === "trial") banner = { tone: "warn", icon: CalendarClock, text: `Free trial: ${daysLeft(sub.trial_ends_at)} days left (until ${date(sub.trial_ends_at)}). Pay to keep using EduSekai without a break.` };
    else if (sub?.status === "active") banner = { tone: "good", icon: CheckCircle2, text: sub.paid_until ? `Paid until ${date(sub.paid_until)}.${sub.autopay ? " It renews automatically." : ""}` : "Paid for life." };
    else if (sub?.status === "past_due") banner = { tone: "warn", icon: AlertTriangle, text: `Payment is overdue. Everything still works for ${daysLeft(sub.grace_ends_at)} more days (until ${date(sub.grace_ends_at)}); after that the school becomes read-only.` };
    else if (sub?.status === "read_only") banner = { tone: "bad", icon: XCircle, text: "The school is read-only because payment is overdue. Everyone can still see everything, but nothing can be changed. Pay now to unlock it at once. No data has been deleted." };
    else if (sub?.status === "pending") banner = { tone: "warn", icon: AlertTriangle, text: "The first payment has not been received yet." };
    else if (sub?.status === "cancelled") banner = { tone: "bad", icon: XCircle, text: "The subscription has ended. Pay to start it again; your data is still here." };

    const needsPayment = sub && !sub.is_legacy && ["trial", "past_due", "read_only", "pending", "cancelled"].includes(sub.status);
    const canAutopay = sub && !sub.is_legacy && sub.cycle !== "one_time";

    return (
        <div className="space-y-6 max-w-5xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Billing</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">Your school&apos;s EduSekai plan, payments and invoices.</p>
            </div>

            {!sub ? (
                <p className="text-sm text-slate-500">No plan is set up for this school yet. Please contact EduSekai support.</p>
            ) : (
                <>
                    {banner && (
                        <div className={`flex items-start gap-3 rounded-2xl border px-4 py-3 text-sm ${TONE[banner.tone]}`}>
                            <banner.icon className="h-5 w-5 shrink-0 mt-0.5" /> <span>{banner.text}</span>
                        </div>
                    )}

                    <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 p-5 grid gap-4 sm:grid-cols-3">
                        <div><p className="text-xs uppercase text-slate-500">Plan</p><p className="text-lg font-semibold text-slate-900 dark:text-white">{sub.plan}</p></div>
                        <div><p className="text-xs uppercase text-slate-500">Billing</p><p className="text-lg font-semibold text-slate-900 dark:text-white">{CYCLE[sub.cycle]}</p></div>
                        <div><p className="text-xs uppercase text-slate-500">Students allowed</p><p className="text-lg font-semibold text-slate-900 dark:text-white">{sub.student_limit ? sub.student_limit.toLocaleString("en-IN") : "Unlimited"}</p></div>
                    </div>

                    {!sub.is_legacy && (
                        <div className="flex flex-wrap gap-2">
                            {needsPayment && (
                                <Button onClick={() => payNow.mutate(undefined)} disabled={busy}>
                                    {payNow.isPending && <Loader2 className="h-4 w-4 mr-2 animate-spin" />} Pay now
                                </Button>
                            )}
                            {!needsPayment && sub.cycle !== "one_time" && !sub.autopay && (
                                <Button variant="outline" onClick={() => payNow.mutate(undefined)} disabled={busy}>Pay next period in advance</Button>
                            )}
                            {canAutopay && !sub.autopay && (
                                <Button variant="outline" onClick={() => startAutopay.mutate()} disabled={busy}>
                                    <RefreshCcw className="h-4 w-4 mr-2" /> Turn on automatic renewal
                                </Button>
                            )}
                            {sub.autopay && (
                                <Button variant="ghost" onClick={() => {
                                    if (window.confirm("Stop automatic renewal? Access continues until the end of the paid period.")) cancelAutopay.mutate();
                                }} disabled={busy}>Stop automatic renewal</Button>
                            )}
                        </div>
                    )}
                    {canAutopay && !sub.autopay && (
                        <p className="text-xs text-slate-500">Automatic renewal uses UPI AutoPay or a card mandate through Razorpay: you approve it once and each {sub.cycle === "monthly" ? "month" : "year"} is paid on time, with a GST invoice every time.</p>
                    )}

                    <div className="space-y-2">
                        <h2 className="text-lg font-semibold text-slate-900 dark:text-white">Invoices</h2>
                        {data.invoices.length === 0 ? (
                            <p className="text-sm text-slate-500">No invoices yet.</p>
                        ) : (
                            <ResponsiveList
                                rows={data.invoices}
                                rowKey={(r) => r.id}
                                columns={[
                                    { key: "number", header: "Invoice", primary: true, cell: (r) => <span className="font-mono text-sm">{r.number}</span> },
                                    { key: "date", header: "Paid on", cell: (r) => date(r.paid_at) },
                                    { key: "period", header: "Period", hideOnMobile: true, cell: (r) => r.period_end ? `${date(r.period_start)} – ${date(r.period_end)}` : `From ${date(r.period_start)}` },
                                    { key: "total", header: "Total (incl. GST)", cell: (r) => rupees(r.total) },
                                ]}
                                actionsHeader=""
                                actions={(r) => (
                                    <Button size="sm" variant="outline" onClick={() => downloadInvoice(r).catch(() => toast.error("Could not download the invoice."))}>
                                        <Download className="h-4 w-4 mr-1" /> PDF
                                    </Button>
                                )}
                            />
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
