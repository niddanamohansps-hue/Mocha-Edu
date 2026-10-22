"use client";

import { useEffect, useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useAttendanceSettings, useUpdateAttendanceSettings } from "@/hooks/useAttendance";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

const STATUS_LABELS: Record<string, string> = {
    present: "Present",
    absent: "Absent",
    late: "Late",
    half_day: "Half Day",
    leave: "Leave",
};

// Python weekday numbers, in the order a school week is usually written.
const WEEKDAYS: { value: number; label: string }[] = [
    { value: 6, label: "Sunday" },
    { value: 0, label: "Monday" },
    { value: 1, label: "Tuesday" },
    { value: 2, label: "Wednesday" },
    { value: 3, label: "Thursday" },
    { value: 4, label: "Friday" },
    { value: 5, label: "Saturday" },
];

export default function AttendanceSettingsPage() {
    const { isOwner } = usePermissions();
    if (!isOwner) {
        return <Unauthorized />;
    }
    return <AttendanceSettingsForm />;
}

// A separate component, so its hooks always run in the same order (the owner check above comes first).
function AttendanceSettingsForm() {
    const { data, isLoading, isError, refetch } = useAttendanceSettings();
    const { mutate: update, isPending } = useUpdateAttendanceSettings();

    const [weights, setWeights] = useState<Record<string, string>>({});
    const [threshold, setThreshold] = useState("75.00");
    const [lockAfterDays, setLockAfterDays] = useState("0");
    const [weeklyOff, setWeeklyOff] = useState<number[]>([6]);

    useEffect(() => {
        if (!data) return;
        const w: Record<string, string> = {};
        for (const key of Object.keys(STATUS_LABELS)) {
            const value = (data.status_weights as any)[key];
            w[key] = value === null || value === undefined ? "" : String(value);
        }
        setWeights(w);
        setThreshold(data.minimum_attendance_percentage);
        setLockAfterDays(String(data.lock_after_days));
        setWeeklyOff(data.weekly_off_days ?? [6]);
    }, [data]);

    const handleSave = () => {
        const status_weights: Record<string, number | null> = {};
        for (const key of Object.keys(weights)) {
            status_weights[key] = weights[key] === "" ? null : parseFloat(weights[key]);
        }
        update({
            status_weights,
            minimum_attendance_percentage: threshold,
            lock_after_days: parseInt(lockAfterDays, 10) || 0,
            weekly_off_days: weeklyOff,
        });
    };

    if (isLoading) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} />;
    }

    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Attendance Settings</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Configure how each status counts toward the attendance percentage. Leave a weight blank to
                    exclude that status from the percentage entirely.
                </p>
            </div>

            <Card className="border-none shadow-md">
                <CardContent className="p-6 space-y-4">
                    {Object.entries(STATUS_LABELS).map(([key, label]) => (
                        <div key={key} className="flex flex-wrap items-center justify-between gap-4">
                            <label className="text-sm font-medium">{label}</label>
                            <Input aria-label="Excluded"
                                type="number"
                                step="0.1"
                                min={0}
                                max={1}
                                placeholder="Excluded"
                                className="w-32"
                                value={weights[key] ?? ""}
                                onChange={(e) => setWeights((prev) => ({ ...prev, [key]: e.target.value }))}
                            />
                        </div>
                    ))}
                </CardContent>
            </Card>

            <Card className="border-none shadow-md">
                <CardContent className="p-6 space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <label htmlFor="f-minimum-attendance-percentage" className="text-sm font-medium">Minimum attendance percentage</label>
                        <Input id="f-minimum-attendance-percentage"
                            type="number"
                            step="0.01"
                            className="w-32"
                            value={threshold}
                            onChange={(e) => setThreshold(e.target.value)}
                        />
                    </div>
                    <div className="flex flex-wrap items-center justify-between gap-4">
                        <label htmlFor="f-auto-lock-after-days-0-never" className="text-sm font-medium">Auto-lock after (days, 0 = never)</label>
                        <Input id="f-auto-lock-after-days-0-never"
                            type="number"
                            min={0}
                            className="w-32"
                            value={lockAfterDays}
                            onChange={(e) => setLockAfterDays(e.target.value)}
                        />
                    </div>
                </CardContent>
            </Card>

            <Card className="border-none shadow-md">
                <CardContent className="p-6 space-y-3">
                    <div>
                        <h2 className="font-semibold text-slate-900 dark:text-white">Weekly off days</h2>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                            The days your school is closed every week. They are not counted as working days for leave, and
                            leave cannot be taken on them. Tick every day that applies. Changing this does not recalculate
                            leave that was already approved.
                        </p>
                    </div>
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {WEEKDAYS.map((day) => {
                            const checked = weeklyOff.includes(day.value);
                            return (
                                <label key={day.value} className="flex items-center gap-2 text-sm">
                                    <input
                                        type="checkbox"
                                        checked={checked}
                                        onChange={(e) =>
                                            setWeeklyOff((prev) =>
                                                e.target.checked ? [...prev, day.value] : prev.filter((d) => d !== day.value)
                                            )
                                        }
                                    />
                                    {day.label}
                                </label>
                            );
                        })}
                    </div>
                    {weeklyOff.length >= 7 && (
                        <p role="alert" className="text-sm text-red-600">
                            At least one day of the week must be a working day.
                        </p>
                    )}
                </CardContent>
            </Card>

            <div className="flex justify-end">
                <Button onClick={handleSave} disabled={isPending || weeklyOff.length >= 7} className="gap-2">
                    {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                    Save Settings
                </Button>
            </div>
        </div>
    );
}
