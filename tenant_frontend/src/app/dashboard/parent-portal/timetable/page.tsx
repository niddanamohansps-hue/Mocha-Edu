"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
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
                <ResponsiveList
                    rows={[...data.results].sort((a, b) => a.day_of_week - b.day_of_week || a.period_order - b.period_order)}
                    rowKey={(entry) => entry.id}
                    columns={[
                        { key: "day", header: "Day", primary: true, cell: (entry) => DAY_LABELS[entry.day_of_week] },
                        { key: "period", header: "Period", cell: (entry) => entry.period_name },
                        { key: "subject", header: "Subject", className: "font-medium", cell: (entry) => entry.subject_name },
                        { key: "instructor", header: "Teacher", className: "text-slate-500", cell: (entry) => entry.instructor_name || "—" },
                        { key: "room", header: "Room", className: "text-slate-500", cell: (entry) => entry.room_name || "—" },
                    ]}
                />
            )}
        </div>
    );
}
