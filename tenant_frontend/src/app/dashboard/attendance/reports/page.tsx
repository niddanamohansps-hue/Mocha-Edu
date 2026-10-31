"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { LoaderCircle } from "lucide-react";
import { useSections } from "@/hooks/useAcademics";
import { useBelowThresholdReport, useSectionAttendanceSummary, useTenantAttendanceSummary } from "@/hooks/useAttendance";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function AttendanceReportsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_attendance_reports")) {
        return <Unauthorized />;
    }
    return <AttendanceReportsPageContent />;
}

function AttendanceReportsPageContent() {
    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    const { data: sections } = useSections();

    // sectionId is URL state - an absent/empty param means "All sections",
    // the existing default, so it's kept out of the URL at that value.
    const sectionId = searchParams.get("sectionId") || "";

    const updateParams = (updates: Record<string, string | null>) => {
        const params = new URLSearchParams(searchParams.toString());
        for (const [key, value] of Object.entries(updates)) {
            if (value === null || value === "") {
                params.delete(key);
            } else {
                params.set(key, value);
            }
        }
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
    };

    const { data: tenantSummary, isLoading: loadingTenant } = useTenantAttendanceSummary();
    const { data: sectionSummary, isLoading: loadingSection } = useSectionAttendanceSummary(sectionId || undefined);
    const { data: belowThreshold, isLoading: loadingThreshold, isError: belowThresholdError, refetch: refetchBelowThreshold } = useBelowThresholdReport(sectionId || undefined);

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Attendance Reports</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Today's tenant-wide summary, section comparisons, and students below threshold
                </p>
            </div>

            <Card className="border-none shadow-md">
                <CardContent className="p-6">
                    <p className="text-xs text-slate-500 uppercase font-bold mb-2">Today's Tenant Attendance</p>
                    {loadingTenant ? (
                        <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                    ) : (
                        <p className="text-4xl font-black">
                            {tenantSummary?.percentage !== null && tenantSummary?.percentage !== undefined
                                ? `${tenantSummary.percentage}%`
                                : "—"}
                        </p>
                    )}
                </CardContent>
            </Card>

            <div className="w-72">
                <label className="text-xs font-medium text-slate-500 mb-1 block">Section</label>
                <Select value={sectionId} onValueChange={(v) => updateParams({ sectionId: v })}>
                    <SelectTrigger>
                        <SelectValue placeholder="All sections" />
                    </SelectTrigger>
                    <SelectContent>
                        {sections?.map((s) => (
                            <SelectItem key={s.id} value={s.id}>
                                {s.level_name} - {s.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
            </div>

            {sectionId && (
                <Card className="border-none shadow-md">
                    <CardContent className="p-6">
                        <p className="text-xs text-slate-500 uppercase font-bold mb-2">Section Attendance</p>
                        {loadingSection ? (
                            <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                        ) : (
                            <p className="text-3xl font-black">
                                {sectionSummary?.percentage !== null && sectionSummary?.percentage !== undefined
                                    ? `${sectionSummary.percentage}%`
                                    : "—"}
                            </p>
                        )}
                    </CardContent>
                </Card>
            )}

            <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-white mb-3">
                    Below Threshold {belowThreshold ? `(< ${belowThreshold.threshold}%)` : ""}
                </h2>
                {loadingThreshold ? (
                    <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                ) : belowThresholdError ? (
                    <ErrorState onRetry={refetchBelowThreshold} />
                ) : !belowThreshold || belowThreshold.students.length === 0 ? (
                    <EmptyState title="No students are currently below the threshold." className="py-6 text-slate-500 text-sm" />
                ) : (
                        <ResponsiveList
                            rows={belowThreshold.students}
                            rowKey={(s) => String(s.student)}
                            columns={[
                                { key: "c0", header: "Student", primary: true, className: "font-medium", cell: (s) => (<>{s.full_name}</>), },
                                { key: "c1", header: "Enrollment ID", className: "text-slate-500", cell: (s) => (<>{s.enrollment_id}</>), },
                                { key: "c2", header: "Percentage", className: "text-red-600 font-bold", cell: (s) => (<>{s.percentage}%</>), },
                            ]}
                        />
                )}
            </div>
        </div>
    );
}
