"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import {
    useChildAttendance,
    useChildUpcomingExams,
    useChildReportCard,
    useLinkedChildren,
} from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

function todayISODate() {
    return new Date().toISOString().slice(0, 10);
}

export default function ParentPortalDashboardPage() {
    const { can, isOwner } = usePermissions();
    const canViewChildren = isOwner || can("view_own_children");
    const canViewAttendance = isOwner || can("view_child_attendance");
    const canViewResults = isOwner || can("view_child_results");

    const { data: children, isLoading: loadingChildren, isError: childrenError, refetch: refetchChildren } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);

    const attendanceChildId = canViewAttendance ? selectedChildId : undefined;
    const resultsChildId = canViewResults ? selectedChildId : undefined;

    const { data: attendance, isLoading: loadingAttendance } = useChildAttendance(attendanceChildId);
    const { data: upcomingExams, isLoading: loadingUpcoming } = useChildUpcomingExams(resultsChildId);
    const { data: reportCard, isLoading: loadingReportCard } = useChildReportCard(resultsChildId);

    if (!canViewChildren) {
        return <Unauthorized />;
    }

    const selectedChild = children?.find((c) => c.student_id === selectedChildId);
    const today = todayISODate();
    const todaysAttendance = attendance?.records.find((r) => r.date === today);
    const latestResult = reportCard?.examinations[0];

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Parent Dashboard</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    A quick overview for your selected child
                </p>
            </div>

            <ChildSwitcher
                childOptions={children || []}
                selectedId={selectedChildId}
                onChange={setSelectedChildId}
            />

            {loadingChildren ? (
                <LoadingState className="py-20" />
            ) : childrenError ? (
                <ErrorState onRetry={refetchChildren} />
            ) : !children || children.length === 0 ? (
                <EmptyState title="No children are linked to your account yet." className="py-16 text-slate-500 text-sm" />
            ) : !selectedChildId ? (
                <EmptyState title="Select a child to see their overview." className="py-16 text-slate-500 text-sm" />
            ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <Card className="border-none shadow-md">
                        <CardContent className="p-5 space-y-1">
                            <p className="text-xs text-slate-500 uppercase font-bold">Child</p>
                            <p className="text-xl font-black text-slate-900 dark:text-white">
                                {selectedChild?.full_name ?? "—"}
                            </p>
                            <p className="text-xs text-slate-500">
                                {selectedChild?.level || "—"}{" "}
                                {selectedChild?.section ? `· Section ${selectedChild.section}` : ""}
                            </p>
                        </CardContent>
                    </Card>

                    <Card className="border-none shadow-md">
                        <CardContent className="p-5 space-y-1">
                            <p className="text-xs text-slate-500 uppercase font-bold">Today&apos;s Attendance</p>
                            {!canViewAttendance ? (
                                <p className="text-sm text-slate-400">No permission to view</p>
                            ) : loadingAttendance ? (
                                <LoaderCircle className="h-5 w-5 animate-spin text-indigo-600" />
                            ) : (
                                <p className="text-xl font-black text-slate-900 dark:text-white capitalize">
                                    {todaysAttendance ? todaysAttendance.status.replace("_", " ") : "Not marked yet"}
                                </p>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="border-none shadow-md">
                        <CardContent className="p-5 space-y-1">
                            <p className="text-xs text-slate-500 uppercase font-bold">Latest Published Result</p>
                            {!canViewResults ? (
                                <p className="text-sm text-slate-400">No permission to view</p>
                            ) : loadingReportCard ? (
                                <LoaderCircle className="h-5 w-5 animate-spin text-indigo-600" />
                            ) : latestResult ? (
                                <p className="text-xl font-black text-slate-900 dark:text-white">
                                    {latestResult.examination_name}: {latestResult.percentage}%
                                </p>
                            ) : (
                                <p className="text-sm text-slate-400">No published results yet</p>
                            )}
                        </CardContent>
                    </Card>

                    <Card className="border-none shadow-md sm:col-span-2 lg:col-span-3">
                        <CardContent className="p-5 space-y-3">
                            <p className="text-xs text-slate-500 uppercase font-bold">Upcoming Examinations</p>
                            {!canViewResults ? (
                                <p className="text-sm text-slate-400">No permission to view</p>
                            ) : loadingUpcoming ? (
                                <LoaderCircle className="h-5 w-5 animate-spin text-indigo-600" />
                            ) : !upcomingExams || upcomingExams.length === 0 ? (
                                <p className="text-sm text-slate-400">No upcoming examinations scheduled</p>
                            ) : (
                                <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {upcomingExams.map((exam) => (
                                        <li key={exam.id} className="py-2 flex justify-between text-sm">
                                            <span className="font-medium">
                                                {exam.examination_name} — {exam.subject_name}
                                            </span>
                                            <span className="text-slate-500">
                                                {exam.date} · {exam.start_time}
                                            </span>
                                        </li>
                                    ))}
                                </ul>
                            )}
                        </CardContent>
                    </Card>
                </div>
            )}
        </div>
    );
}
