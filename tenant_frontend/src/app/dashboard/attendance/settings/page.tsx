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

export default function AttendanceSettingsPage() {
    const { isOwner } = usePermissions();
    if (!isOwner) {
        return <Unauthorized />;
    }

    const { data, isLoading, isError, refetch } = useAttendanceSettings();
    const { mutate: update, isPending } = useUpdateAttendanceSettings();

    const [weights, setWeights] = useState<Record<string, string>>({});
    const [threshold, setThreshold] = useState("75.00");
    const [lockAfterDays, setLockAfterDays] = useState("0");

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
                        <div key={key} className="flex items-center justify-between gap-4">
                            <label className="text-sm font-medium">{label}</label>
                            <Input
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
                    <div className="flex items-center justify-between gap-4">
                        <label className="text-sm font-medium">Minimum attendance percentage</label>
                        <Input
                            type="number"
                            step="0.01"
                            className="w-32"
                            value={threshold}
                            onChange={(e) => setThreshold(e.target.value)}
                        />
                    </div>
                    <div className="flex items-center justify-between gap-4">
                        <label className="text-sm font-medium">Auto-lock after (days, 0 = never)</label>
                        <Input
                            type="number"
                            min={0}
                            className="w-32"
                            value={lockAfterDays}
                            onChange={(e) => setLockAfterDays(e.target.value)}
                        />
                    </div>
                </CardContent>
            </Card>

            <div className="flex justify-end">
                <Button onClick={handleSave} disabled={isPending} className="gap-2">
                    {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                    Save Settings
                </Button>
            </div>
        </div>
    );
}
