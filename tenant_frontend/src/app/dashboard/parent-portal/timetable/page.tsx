"use client";

import { useState } from "react";
import { useChildTimetable, useLinkedChildren } from "@/hooks/useParentPortal";
import { DAY_LABELS } from "@/types/ParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function ParentPortalTimetablePage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_child_timetable");

    const { data: children } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);

    const { data, isLoading, isError, refetch } = useChildTimetable(selectedChildId);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Child Timetable</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Weekly timetable for your selected child
                </p>
            </div>

            <ChildSwitcher
                childOptions={children || []}
                selectedId={selectedChildId}
                onChange={setSelectedChildId}
            />

            {!selectedChildId ? (
                <EmptyState
                    title={
                        children && children.length === 0
                            ? "No children are linked to your account yet."
                            : "Select a child to view their timetable."
                    }
                    className="py-16 text-slate-500 text-sm"
                />
            ) : isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !data || !data.section ? (
                <EmptyState title="This child is not currently enrolled in a section." className="py-16 text-slate-500 text-sm" />
            ) : data.results.length === 0 ? (
                <EmptyState
                    title="No timetable entries have been scheduled for this section yet."
                    className="py-16 text-slate-500 text-sm"
                />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 dark:bg-slate-900">
                            <tr className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                <th className="px-4 py-3">Day</th>
                                <th className="px-4 py-3">Period</th>
                                <th className="px-4 py-3">Subject</th>
                                <th className="px-4 py-3">Instructor</th>
                                <th className="px-4 py-3">Room</th>
                            </tr>
                        </thead>
                        <tbody>
                            {[...data.results]
                                .sort((a, b) => a.day_of_week - b.day_of_week || a.period_order - b.period_order)
                                .map((entry) => (
                                    <tr key={entry.id} className="border-t border-slate-100 dark:border-slate-800">
                                        <td className="px-4 py-2">{DAY_LABELS[entry.day_of_week]}</td>
                                        <td className="px-4 py-2">{entry.period_name}</td>
                                        <td className="px-4 py-2 font-medium">{entry.subject_name}</td>
                                        <td className="px-4 py-2 text-slate-500">{entry.instructor_name || "—"}</td>
                                        <td className="px-4 py-2 text-slate-500">{entry.room_name || "—"}</td>
                                    </tr>
                                ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}
