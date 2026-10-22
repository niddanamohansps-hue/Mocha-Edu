"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useMyTimetable } from "@/hooks/useTimetable";
import { DAY_LABELS } from "@/types/Timetable";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function MySchedulePage() {
    const { data, isLoading, isError, refetch } = useMyTimetable();

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">My Schedule</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Your own weekly timetable, read-only
                </p>
            </div>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !data || data.role === null ? (
                <EmptyState title="No timetable is linked to your account yet." className="py-16 text-slate-500 text-sm" />
            ) : data.results.length === 0 ? (
                <EmptyState title="No timetable entries have been scheduled yet." className="py-16 text-slate-500 text-sm" />
            ) : (
                <ResponsiveList
                    rows={[...data.results].sort((a, b) => a.day_of_week - b.day_of_week || a.period_order - b.period_order)}
                    rowKey={(entry) => entry.id}
                    columns={[
                        { key: "day", header: "Day", primary: true, cell: (entry) => DAY_LABELS[entry.day_of_week] },
                        { key: "period", header: "Period", cell: (entry) => entry.period_name },
                        { key: "subject", header: "Subject", className: "font-medium", cell: (entry) => entry.subject_name },
                        ...(data.role === "student"
                            ? [{ key: "instructor", header: "Teacher", className: "text-slate-500", cell: (entry: (typeof data.results)[number]) => entry.instructor_name || "—" }]
                            : []),
                        ...(data.role === "instructor"
                            ? [{ key: "section", header: "Class", className: "text-slate-500", cell: (entry: (typeof data.results)[number]) => entry.section_name }]
                            : []),
                        { key: "room", header: "Room", className: "text-slate-500", cell: (entry) => entry.room_name || "—" },
                    ]}
                />
            )}
        </div>
    );
}
