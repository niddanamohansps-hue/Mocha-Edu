"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { PageHeader } from "@/components/common/PageLayout";
import { useNotificationSettings, useUpdateNotificationSettings } from "@/hooks/useNotifications";
import { usePermissions } from "@/providers/PermissionProvider";
import { NotificationSettings } from "@/types/Notifications";

type Switch = "fee_reminders_enabled" | "absence_alerts_enabled" | "payment_receipts_enabled";

const SWITCHES: { key: Switch; label: string; hint: string }[] = [
    { key: "absence_alerts_enabled", label: "Absence alerts", hint: "When a student is marked absent, tell the student and their parents the same day." },
    { key: "payment_receipts_enabled", label: "Payment receipts", hint: "When a fee payment is recorded or paid online, tell the student and their parents." },
    { key: "fee_reminders_enabled", label: "Fee reminders", hint: "Remind the student and their parents before a fee is due, and again while it stays unpaid." },
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
        if (!whole(before, 0, 30)) return setError("Days before the due date must be a whole number from 0 to 30.");
        if (!whole(interval, 1, 30)) return setError("Days between overdue reminders must be a whole number from 1 to 30.");
        if (!whole(max, 1, 10)) return setError("Overdue reminders must be a whole number from 1 to 10.");
        setError(null);
        update.mutate({ fee_reminder_days_before: Number(before), overdue_reminder_interval_days: Number(interval), max_overdue_reminders: Number(max) });
    };

    return (
        <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
            <h2 className="font-semibold text-slate-900 dark:text-white">Fee reminder timing</h2>
            <div className="grid sm:grid-cols-3 gap-3">
                <label className="space-y-1 text-sm">
                    <span>Remind this many days before the due date</span>
                    <Input inputMode="numeric" disabled={!canEdit} value={before} onChange={(e) => setBefore(e.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                    <span>Then every this many days once overdue</span>
                    <Input inputMode="numeric" disabled={!canEdit} value={interval} onChange={(e) => setInterval(e.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                    <span>Stop after this many overdue reminders</span>
                    <Input inputMode="numeric" disabled={!canEdit} value={max} onChange={(e) => setMax(e.target.value)} />
                </label>
            </div>
            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            {canEdit && <Button size="sm" disabled={update.isPending} onClick={save}>Save timing</Button>}
        </section>
    );
}

export default function NotificationSettingsPage() {
    const router = useRouter();
    const { can } = usePermissions();
    const canEdit = can("manage_notification_settings");
    const { data, isLoading, isError, refetch } = useNotificationSettings();
    const update = useUpdateNotificationSettings();

    if (!canEdit && !can("view_notification_log")) return <ErrorState message="You do not have permission to view alert settings." />;

    return (
        <div className="space-y-6">
            <PageHeader
                title="Automatic alerts"
                description="Choose which messages the school sends by itself. Each one is off until you switch it on, and nobody is ever sent the same message twice."
                actions={
                    can("view_notification_log") ? (
                        <Button
                            variant="outline"
                            onClick={() => router.push("/dashboard/notifications/alert-log")}
                            className="rounded-xl"
                        >
                            View Alert Log
                        </Button>
                    ) : undefined
                }
            />
            {isLoading ? (
                <LoadingState className="py-10" />
            ) : isError || !data ? (
                <ErrorState message="Failed to load the alert settings." onRetry={refetch} />
            ) : (
                <>
                    <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                        <h2 className="font-semibold text-slate-900 dark:text-white">Alerts</h2>
                        {SWITCHES.map((s) => (
                            <label key={s.key} className="flex items-start gap-2 text-sm">
                                <input type="checkbox" className="mt-1" disabled={!canEdit || update.isPending} checked={data[s.key]} onChange={(e) => update.mutate({ [s.key]: e.target.checked })} />
                                <span>{s.label}<span className="block text-xs text-slate-500">{s.hint}</span></span>
                            </label>
                        ))}
                        <p className="text-xs text-slate-500">
                            Messages go to the student&apos;s own account and to the parents linked to the student. Everyone with an account sees it in the app, and by email too if they have an address. People with no account are skipped.
                        </p>
                    </section>
                    <TimingForm key={`${data.fee_reminder_days_before}-${data.overdue_reminder_interval_days}-${data.max_overdue_reminders}`} data={data} canEdit={canEdit} />
                </>
            )}
        </div>
    );
}
