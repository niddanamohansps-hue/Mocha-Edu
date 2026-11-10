"use client";

import {
    AlertTriangle,
    CalendarClock,
    CheckCircle2,
    Download,
    Loader2,
    RefreshCcw,
    XCircle,
    CreditCard,
    Shield,
    Receipt,
    Calendar,
    Users,
    Zap,
    Sparkles,
    ShieldCheck,
    ArrowUpRight,
    HelpCircle,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TableShell } from "@/components/common/table/TableShell";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import Unauthorized from "@/components/Unauthorized";
import { GstDetails } from "@/components/dashboard/billing/GstDetails";
import { downloadInvoice, useCancelAutopay, useMyBilling, usePayNow, useStartAutopay } from "@/hooks/useBilling";
import { usePermissions } from "@/providers/PermissionProvider";

const CYCLE = { monthly: "Monthly", yearly: "Yearly", one_time: "One-time" } as const;

const STATUS_CONFIG: Record<
    string,
    { label: string; badge: string; bg: string; border: string; text: string }
> = {
    active: {
        label: "Active Subscription",
        badge: "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300",
        bg: "bg-emerald-500/10",
        border: "border-emerald-200 dark:border-emerald-900",
        text: "text-emerald-700 dark:text-emerald-300",
    },
    trial: {
        label: "Evaluation Trial",
        badge: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950 dark:text-amber-300",
        bg: "bg-amber-500/10",
        border: "border-amber-200 dark:border-amber-900",
        text: "text-amber-700 dark:text-amber-300",
    },
    past_due: {
        label: "Past Due - Grace Period",
        badge: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950 dark:text-rose-300",
        bg: "bg-rose-500/10",
        border: "border-rose-200 dark:border-rose-900",
        text: "text-rose-700 dark:text-rose-300",
    },
    read_only: {
        label: "Locked / Read Only",
        badge: "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950 dark:text-rose-300",
        bg: "bg-rose-500/10",
        border: "border-rose-200 dark:border-rose-900",
        text: "text-rose-700 dark:text-rose-300",
    },
    pending: {
        label: "Payment Pending",
        badge: "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950 dark:text-amber-300",
        bg: "bg-amber-500/10",
        border: "border-amber-200 dark:border-amber-900",
        text: "text-amber-700 dark:text-amber-300",
    },
    cancelled: {
        label: "Subscription Expired",
        badge: "bg-slate-100 text-slate-700 border-slate-300 dark:bg-slate-800 dark:text-slate-300",
        bg: "bg-slate-500/10",
        border: "border-slate-200 dark:border-slate-800",
        text: "text-slate-700 dark:text-slate-300",
    },
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

    let banner: { tone: "good" | "warn" | "bad"; icon: typeof CheckCircle2; title: string; text: string } | null = null;
    if (sub?.is_legacy) {
        banner = {
            tone: "good",
            icon: CheckCircle2,
            title: "Lifetime Institutional Access",
            text: "Your school has unrestricted institutional access under the founding tier. No ongoing renewal fee is required.",
        };
    } else if (sub?.status === "trial") {
        banner = {
            tone: "warn",
            icon: CalendarClock,
            title: "Evaluation Period Active",
            text: `You have ${daysLeft(sub.trial_ends_at)} days remaining in your trial (valid until ${date(sub.trial_ends_at)}). Activate an institutional plan to keep uninterrupted access for staff and parents.`,
        };
    } else if (sub?.status === "active") {
        banner = {
            tone: "good",
            icon: CheckCircle2,
            title: "Subscription in Good Standing",
            text: sub.paid_until
                ? `Paid through ${date(sub.paid_until)}.${sub.autopay ? " Automatic UPI/Card mandate renewal is enabled." : ""}`
                : "Active lifetime license.",
        };
    } else if (sub?.status === "past_due") {
        banner = {
            tone: "warn",
            icon: AlertTriangle,
            title: "Payment Overdue - Grace Period Running",
            text: `Your renewal payment is overdue. Uninterrupted access will continue for ${daysLeft(sub.grace_ends_at)} more days (until ${date(sub.grace_ends_at)}); afterwards the workspace enters read-only archival mode.`,
        };
    } else if (sub?.status === "read_only") {
        banner = {
            tone: "bad",
            icon: XCircle,
            title: "Account Restricted to Read-Only Mode",
            text: "The institutional workspace is in read-only mode due to overdue renewal. Faculty and parents can view records, but modifications and new admissions are locked. Pay now to instantly unlock full access without data loss.",
        };
    } else if (sub?.status === "pending") {
        banner = {
            tone: "warn",
            icon: AlertTriangle,
            title: "Initial Mandate Pending",
            text: "Your institutional plan invoice has been generated and is awaiting first payment confirmation from Razorpay.",
        };
    } else if (sub?.status === "cancelled") {
        banner = {
            tone: "bad",
            icon: XCircle,
            title: "Subscription Inactive",
            text: "The subscription has lapsed. Renew your plan to reactivate operational features; all your school records and audit logs are securely preserved.",
        };
    }

    const needsPayment = sub && !sub.is_legacy && ["trial", "past_due", "read_only", "pending", "cancelled"].includes(sub.status);
    const canAutopay = sub && !sub.is_legacy && sub.cycle !== "one_time";
    const statusInfo = sub ? (STATUS_CONFIG[sub.status] ?? STATUS_CONFIG.active) : STATUS_CONFIG.active;

    return (
        <div className="space-y-6 max-w-6xl">
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 dark:border-slate-800 pb-5">
                <div>
                    <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-sky-600 text-white shadow-sm">
                            <CreditCard className="h-5 w-5" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                            Billing & Subscriptions
                        </h1>
                        <Badge variant="outline" className="border-sky-300 dark:border-sky-800 text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/50 text-xs">
                            SaaS Account
                        </Badge>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Manage your school&apos;s EduSekai cloud subscription, automated renewal mandates, and official GST tax invoices.
                    </p>
                </div>

                {needsPayment && (
                    <Button
                        size="sm"
                        onClick={() => payNow.mutate(undefined)}
                        disabled={busy}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-xs shadow-sm h-9"
                    >
                        {payNow.isPending ? (
                            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        ) : (
                            <CreditCard className="h-4 w-4 mr-2" />
                        )}
                        Complete Payment Now
                    </Button>
                )}
            </div>

            {!sub ? (
                <div className="p-8 rounded-2xl border border-slate-200 dark:border-slate-800 text-center space-y-3 bg-white dark:bg-slate-900">
                    <p className="text-sm text-slate-500">
                        No active subscription tier found for this school campus. Please contact EduSekai support to assign a plan.
                    </p>
                </div>
            ) : (
                <>
                    {/* Status Alert Banner */}
                    {banner && (
                        <div
                            className={`flex items-start gap-3.5 p-4 rounded-2xl border ${
                                banner.tone === "good"
                                    ? "bg-emerald-50/80 text-emerald-900 border-emerald-200 dark:bg-emerald-950/30 dark:text-emerald-200 dark:border-emerald-900"
                                    : banner.tone === "warn"
                                    ? "bg-amber-50/80 text-amber-900 border-amber-200 dark:bg-amber-950/30 dark:text-amber-200 dark:border-amber-900"
                                    : "bg-rose-50/80 text-rose-900 border-rose-200 dark:bg-rose-950/30 dark:text-rose-200 dark:border-rose-900"
                            }`}
                        >
                            <banner.icon className="h-5 w-5 shrink-0 mt-0.5" />
                            <div className="min-w-0">
                                <h4 className="text-xs font-bold uppercase tracking-wider">{banner.title}</h4>
                                <p className="text-xs mt-0.5 leading-relaxed">{banner.text}</p>
                            </div>
                        </div>
                    )}

                    {/* Subscription Hero Card */}
                    <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 shadow-sm space-y-6">
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-5">
                            <div>
                                <div className="flex items-center gap-2">
                                    <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                                        {sub.plan}
                                    </h2>
                                    <Badge className={`text-xs ${statusInfo.badge}`}>
                                        {sub.is_legacy ? "Lifetime Plan" : statusInfo.label}
                                    </Badge>
                                    {sub.autopay && (
                                        <Badge variant="outline" className="text-[10px] bg-sky-50 text-sky-700 border-sky-300 dark:bg-sky-950 dark:text-sky-300">
                                            Auto-Renew On
                                        </Badge>
                                    )}
                                </div>
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
                                    EduSekai Managed Cloud Hosting & Institutional ERP
                                </p>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                                {needsPayment && (
                                    <Button
                                        size="sm"
                                        onClick={() => payNow.mutate(undefined)}
                                        disabled={busy}
                                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs h-9 shadow-sm"
                                    >
                                        {payNow.isPending ? (
                                            <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                                        ) : (
                                            <CreditCard className="h-3.5 w-3.5 mr-2" />
                                        )}
                                        Pay Overdue Balance
                                    </Button>
                                )}
                                {!needsPayment && sub.cycle !== "one_time" && !sub.autopay && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => payNow.mutate(undefined)}
                                        disabled={busy}
                                        className="text-xs h-9"
                                    >
                                        Renew Next Period in Advance
                                    </Button>
                                )}
                                {canAutopay && !sub.autopay && (
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => startAutopay.mutate()}
                                        disabled={busy}
                                        className="text-xs h-9 border-sky-300 dark:border-sky-800 text-sky-700 dark:text-sky-300 hover:bg-sky-50"
                                    >
                                        <RefreshCcw className="h-3.5 w-3.5 mr-2" /> Enable Auto-Renewal
                                    </Button>
                                )}
                                {sub.autopay && (
                                    <Button
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => {
                                            if (
                                                window.confirm(
                                                    "Cancel automatic renewal mandate? School access will continue smoothly until the end of the paid period."
                                                )
                                            ) {
                                                cancelAutopay.mutate();
                                            }
                                        }}
                                        disabled={busy}
                                        className="text-xs text-slate-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30 h-9"
                                    >
                                        Cancel Auto-Renewal
                                    </Button>
                                )}
                            </div>
                        </div>

                        {/* Vital Subscription Metrics */}
                        <div className="grid gap-4 sm:grid-cols-4">
                            <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                    <span className="text-[11px] font-medium uppercase tracking-wider">Billing Frequency</span>
                                    <Calendar className="h-4 w-4 text-slate-400" />
                                </div>
                                <p className="text-base font-bold text-slate-900 dark:text-white">
                                    {CYCLE[sub.cycle]}
                                </p>
                                <p className="text-[11px] text-slate-500 mt-0.5">Recurring cycle</p>
                            </div>

                            <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                    <span className="text-[11px] font-medium uppercase tracking-wider">Student Capacity</span>
                                    <Users className="h-4 w-4 text-slate-400" />
                                </div>
                                <p className="text-base font-bold text-slate-900 dark:text-white">
                                    {sub.student_limit ? sub.student_limit.toLocaleString("en-IN") : "Unlimited"}
                                </p>
                                <p className="text-[11px] text-slate-500 mt-0.5">Active enrollments allowed</p>
                            </div>

                            <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                    <span className="text-[11px] font-medium uppercase tracking-wider">Subscription Valid Till</span>
                                    <CalendarClock className="h-4 w-4 text-slate-400" />
                                </div>
                                <p className="text-base font-bold text-slate-900 dark:text-white">
                                    {sub.is_legacy ? "Lifetime Access" : sub.paid_until ? date(sub.paid_until) : date(sub.trial_ends_at)}
                                </p>
                                <p className="text-[11px] text-slate-500 mt-0.5">
                                    {sub.is_legacy ? "No expiry" : `${daysLeft(sub.paid_until ?? sub.trial_ends_at)} days remaining`}
                                </p>
                            </div>

                            <div className="p-4 rounded-xl bg-slate-50/70 dark:bg-slate-800/40 border border-slate-200/60 dark:border-slate-800">
                                <div className="flex items-center justify-between text-slate-500 mb-1">
                                    <span className="text-[11px] font-medium uppercase tracking-wider">Operational Mode</span>
                                    <ShieldCheck className="h-4 w-4 text-emerald-500" />
                                </div>
                                <p className="text-base font-bold text-slate-900 dark:text-white">
                                    {sub.can_write ? "Full Read / Write" : "Read-Only Archive"}
                                </p>
                                <p className="text-[11px] text-slate-500 mt-0.5">
                                    {sub.can_write ? "Unrestricted school operations" : "Locked for modifications"}
                                </p>
                            </div>
                        </div>

                        {canAutopay && !sub.autopay && (
                            <div className="p-3.5 rounded-xl bg-sky-50 dark:bg-sky-950/30 border border-sky-100 dark:border-sky-900 text-xs text-sky-800 dark:text-sky-300 flex items-center gap-2.5">
                                <Zap className="h-4 w-4 text-sky-600 shrink-0" />
                                <span>
                                    <strong>Recommendation:</strong> Turn on automatic renewal via UPI AutoPay or credit card mandate (powered securely by Razorpay) to avoid accidental grace period lockouts during end-of-term exams.
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Institutional GST Tax Profile */}
                    {!sub.is_legacy && <GstDetails state={sub.billing_state} gstin={sub.billing_gstin} />}

                    {/* Official Tax Invoices Registry */}
                    <div className="space-y-3">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Receipt className="h-5 w-5 text-slate-700 dark:text-slate-300" />
                                <h2 className="text-base font-bold text-slate-900 dark:text-white">
                                    Official Tax Invoices
                                </h2>
                                <Badge variant="outline" className="text-xs">
                                    {data.invoices.length} {data.invoices.length === 1 ? "Invoice" : "Invoices"}
                                </Badge>
                            </div>
                            <p className="text-xs text-slate-500">
                                Download compliant GST invoices with tax breakdown for school audit and accounting.
                            </p>
                        </div>

                        {data.invoices.length === 0 ? (
                            <div className="p-8 rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 text-center space-y-2">
                                <Receipt className="h-8 w-8 text-slate-300 dark:text-slate-600 mx-auto" />
                                <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">No Tax Invoices Yet</h3>
                                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                                    Invoices are generated automatically each time a subscription payment or renewal is completed.
                                </p>
                            </div>
                        ) : (
                            <TableShell>
                                <Table>
                                    <TableHeader>
                                        <TableRow>
                                            <TableHead className="w-36 font-semibold text-xs">Invoice #</TableHead>
                                            <TableHead className="w-32 font-semibold text-xs">Paid On</TableHead>
                                            <TableHead className="font-semibold text-xs">Coverage Period</TableHead>
                                            <TableHead className="w-28 font-semibold text-xs">Plan Tier</TableHead>
                                            <TableHead className="w-32 text-right font-semibold text-xs">Total (incl. GST)</TableHead>
                                            <TableHead className="w-24 text-center font-semibold text-xs">Status</TableHead>
                                            <TableHead className="w-28 text-right font-semibold text-xs">Action</TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {data.invoices.map((inv) => (
                                            <TableRow key={inv.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/50">
                                                <TableCell>
                                                    <span className="font-mono text-xs font-semibold text-slate-900 dark:text-slate-100">
                                                        {inv.number}
                                                    </span>
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                                                    {date(inv.paid_at)}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-600 dark:text-slate-400">
                                                    {inv.period_end
                                                        ? `${date(inv.period_start)} – ${date(inv.period_end)}`
                                                        : `From ${date(inv.period_start)}`}
                                                </TableCell>
                                                <TableCell className="text-xs font-medium text-slate-700 dark:text-slate-300">
                                                    {inv.plan_name}
                                                </TableCell>
                                                <TableCell className="text-right text-xs font-semibold font-mono text-slate-900 dark:text-white">
                                                    {rupees(inv.total)}
                                                </TableCell>
                                                <TableCell className="text-center">
                                                    <Badge className="bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300 text-[10px]">
                                                        Paid
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() =>
                                                            downloadInvoice(inv).catch(() =>
                                                                toast.error("Could not download the official invoice PDF.")
                                                            )
                                                        }
                                                        className="h-7 text-xs px-2.5 hover:bg-sky-50 dark:hover:bg-slate-800 hover:text-sky-700 font-medium"
                                                    >
                                                        <Download className="h-3.5 w-3.5 mr-1 text-slate-500" /> PDF
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableShell>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
