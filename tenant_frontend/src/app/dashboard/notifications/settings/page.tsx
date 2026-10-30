"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
    BellRing,
    Calendar,
    Clock,
    CreditCard,
    Info,
    Loader2,
    Mail,
    RotateCcw,
    Save,
    Shield,
    Sparkles,
    UserX,
    Users,
} from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { useNotificationSettings, useUpdateNotificationSettings } from "@/hooks/useNotifications";
import { usePermissions } from "@/providers/PermissionProvider";
import { NotificationSettings } from "@/types/Notifications";

type SwitchKey = "fee_reminders_enabled" | "absence_alerts_enabled" | "payment_receipts_enabled";

interface SwitchItem {
    key: SwitchKey;
    label: string;
    description: string;
    icon: typeof UserX;
    tone: "rose" | "emerald" | "sky";
}

const SWITCHES: SwitchItem[] = [
    {
        key: "absence_alerts_enabled",
        label: "Daily Absence Dispatch",
        description: "Automatically notifies parents and students the same afternoon whenever an unexcused absence is marked during daily attendance roll call.",
        icon: UserX,
        tone: "rose",
    },
    {
        key: "payment_receipts_enabled",
        label: "Instant Fee Payment Receipts",
        description: "Dispatches instant digital receipts via email and portal notifications upon physical counter cash collection or successful online gateway settlement.",
        icon: CreditCard,
        tone: "emerald",
    },
    {
        key: "fee_reminders_enabled",
        label: "Scheduled Fee Dues & Arrears Reminders",
        description: "Sends proactive notifications before installment deadlines and automated recurring follow-ups for outstanding institutional fee heads.",
        icon: Clock,
        tone: "sky",
    },
];

function whole(value: string, min: number, max: number) {
    return /^\d+$/.test(value.trim()) && Number(value) >= min && Number(value) <= max;
}

function TimingForm({ data, canEdit }: { data: NotificationSettings; canEdit: boolean }) {
    const update = useUpdateNotificationSettings();
    const [before, setBefore] = useState(String(data.fee_reminder_days_before));
    const [interval, setInterval] = useState(String(data.overdue_reminder_interval_days));
    const [max, setMax] = useState(String(data.max_overdue_reminders));
    const [error, setError] = useState<string | null>(null);

    const save = () => {
        if (!whole(before, 0, 30)) {
            return setError("Days before due date must be between 0 and 30.");
        }
        if (!whole(interval, 1, 30)) {
            return setError("Days between overdue reminders must be between 1 and 30.");
        }
        if (!whole(max, 1, 10)) {
            return setError("Maximum overdue reminders must be between 1 and 10.");
        }
        setError(null);
        update.mutate(
            {
                fee_reminder_days_before: Number(before),
                overdue_reminder_interval_days: Number(interval),
                max_overdue_reminders: Number(max),
            },
            {
                onSuccess: () => {
                    toast.success("Fee reminder schedule updated successfully.");
                },
                onError: () => {
                    toast.error("Failed to update schedule parameters.");
                },
            }
        );
    };

    return (
        <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 p-6 space-y-5 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-4">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 border border-sky-100 dark:border-sky-900 shrink-0">
                        <Clock className="h-5 w-5" />
                    </div>
                    <div>
                        <h3 className="text-base font-semibold text-slate-900 dark:text-white">
                            Fee Reminder Cadence & Thresholds
                        </h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            Configure automatic dispatch timing to balance timely collections with parent communication comfort.
                        </p>
                    </div>
                </div>

                {canEdit && (
                    <Button
                        size="sm"
                        onClick={save}
                        disabled={update.isPending}
                        className="shrink-0 h-9 font-medium text-xs bg-sky-600 hover:bg-sky-700 text-white"
                    >
                        {update.isPending ? (
                            <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                        ) : (
                            <Save className="h-3.5 w-3.5 mr-2" />
                        )}
                        Save Cadence Settings
                    </Button>
                )}
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
                <div className="space-y-1.5">
                    <Label htmlFor="days-before" className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Advance Notice (Days Before Due)
                    </Label>
                    <Input
                        id="days-before"
                        inputMode="numeric"
                        disabled={!canEdit}
                        value={before}
                        className="h-9 text-xs font-mono"
                        onChange={(e) => setBefore(e.target.value)}
                    />
                    <p className="text-[11px] text-slate-400">e.g. 5 days before invoice deadline (0–30)</p>
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="interval-days" className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Recurring Overdue Cadence (Days)
                    </Label>
                    <Input
                        id="interval-days"
                        inputMode="numeric"
                        disabled={!canEdit}
                        value={interval}
                        className="h-9 text-xs font-mono"
                        onChange={(e) => setInterval(e.target.value)}
                    />
                    <p className="text-[11px] text-slate-400">Repeat frequency once invoice is past due (1–30)</p>
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="max-reminders" className="text-xs font-medium text-slate-700 dark:text-slate-300">
                        Max Reminder Dispatches
                    </Label>
                    <Input
                        id="max-reminders"
                        inputMode="numeric"
                        disabled={!canEdit}
                        value={max}
                        className="h-9 text-xs font-mono"
                        onChange={(e) => setMax(e.target.value)}
                    />
                    <p className="text-[11px] text-slate-400">Cease automatic nudges after limit (1–10)</p>
                </div>
            </div>

            {error && (
                <div className="p-3 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900 text-xs text-rose-700 dark:text-rose-300 font-medium">
                    {error}
                </div>
            )}
        </div>
    );
}

export default function NotificationSettingsPage() {
    const router = useRouter();
    const { can } = usePermissions();
    const canEdit = can("manage_notification_settings");
    const { data, isLoading, isError, refetch } = useNotificationSettings();
    const update = useUpdateNotificationSettings();

    if (!canEdit && !can("view_notification_log")) {
        return <ErrorState message="You do not have permission to view institutional alert settings." />;
    }

    const handleToggle = (key: SwitchKey, checked: boolean) => {
        update.mutate(
            { [key]: checked },
            {
                onSuccess: () => {
                    toast.success(checked ? "Alert enabled." : "Alert disabled.");
                },
                onError: () => {
                    toast.error("Could not update alert setting.");
                },
            }
        );
    };

    return (
        <div className="space-y-6 max-w-5xl">
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 dark:border-slate-800 pb-5">
                <div>
                    <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-sky-600 text-white shadow-sm">
                            <BellRing className="h-5 w-5" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                            Automated Alerts & Dispatch Settings
                        </h1>
                        <Badge variant="outline" className="border-sky-300 dark:border-sky-800 text-sky-700 dark:text-sky-300 bg-sky-50 dark:bg-sky-950/50 text-xs">
                            System Triggers
                        </Badge>
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Configure automated institutional communications dispatched to students and parent guardians.
                    </p>
                </div>

                {can("view_notification_log") && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => router.push("/dashboard/notifications/alert-log")}
                        className="shrink-0 h-9 font-medium text-xs bg-white dark:bg-slate-800 shadow-sm"
                    >
                        View Alert Transmission Log
                    </Button>
                )}
            </div>

            {isLoading ? (
                <LoadingState className="py-16" />
            ) : isError || !data ? (
                <ErrorState message="Failed to load institutional alert parameters." onRetry={refetch} />
            ) : (
                <>
                    {/* Routing Explainer Callout */}
                    <div className="flex items-start gap-3.5 p-4 rounded-2xl bg-slate-50 dark:bg-slate-900/60 border border-slate-200/80 dark:border-slate-800">
                        <div className="p-2 rounded-xl bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-900 shrink-0 mt-0.5">
                            <Info className="h-4 w-4" />
                        </div>
                        <div className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                            <strong className="text-slate-900 dark:text-white block mb-0.5">
                                Automated Dispatch Channels & Recipient Resolution
                            </strong>
                            Alerts are targeted directly to the student&apos;s portal profile and all linked parent/guardian mobile profiles. Dispatches are delivered immediately inside the app and mirrored over outbound email where a valid email address is registered. Recipients without verified portal accounts are skipped gracefully without error.
                        </div>
                    </div>

                    {/* Alert Trigger Toggles */}
                    <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 divide-y divide-slate-100 dark:divide-slate-800 shadow-sm">
                        {SWITCHES.map((s) => {
                            const Icon = s.icon;
                            const isEnabled = Boolean(data[s.key]);
                            return (
                                <div
                                    key={s.key}
                                    className="p-5 flex items-start justify-between gap-4 transition hover:bg-slate-50/50 dark:hover:bg-slate-800/30"
                                >
                                    <div className="flex items-start gap-3.5">
                                        <div
                                            className={`p-2.5 rounded-xl border shrink-0 mt-0.5 ${
                                                s.tone === "rose"
                                                    ? "bg-rose-50 dark:bg-rose-950/50 text-rose-600 dark:text-rose-400 border-rose-200 dark:border-rose-900"
                                                    : s.tone === "emerald"
                                                    ? "bg-emerald-50 dark:bg-emerald-950/50 text-emerald-600 dark:text-emerald-400 border-emerald-200 dark:border-emerald-900"
                                                    : "bg-sky-50 dark:bg-sky-950/50 text-sky-600 dark:text-sky-400 border-sky-200 dark:border-sky-900"
                                            }`}
                                        >
                                            <Icon className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <h3 className="text-sm font-semibold text-slate-900 dark:text-white">
                                                    {s.label}
                                                </h3>
                                                <Badge
                                                    variant="outline"
                                                    className={`text-[10px] ${
                                                        isEnabled
                                                            ? "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950 dark:text-emerald-300"
                                                            : "text-slate-400 bg-slate-50 dark:bg-slate-800"
                                                    }`}
                                                >
                                                    {isEnabled ? "Active" : "Disabled"}
                                                </Badge>
                                            </div>
                                            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-2xl leading-relaxed">
                                                {s.description}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="shrink-0 pt-1">
                                        <Switch
                                            checked={isEnabled}
                                            disabled={!canEdit || update.isPending}
                                            onCheckedChange={(checked) => handleToggle(s.key, checked)}
                                        />
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Fee Reminder Timing Settings */}
                    <TimingForm
                        key={`${data.fee_reminder_days_before}-${data.overdue_reminder_interval_days}-${data.max_overdue_reminders}`}
                        data={data}
                        canEdit={canEdit}
                    />
                </>
            )}
        </div>
    );
}
