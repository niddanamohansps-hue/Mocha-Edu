"use client";

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
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                    <table className="w-full text-sm">
                        <thead className="bg-slate-50 dark:bg-slate-900">
                            <tr className="text-left text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                <th className="px-4 py-3">Day</th>
                                <th className="px-4 py-3">Period</th>
                                <th className="px-4 py-3">Subject</th>
                                {data.role === "student" && <th className="px-4 py-3">Instructor</th>}
                                {data.role === "instructor" && <th className="px-4 py-3">Section</th>}
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
                                        {data.role === "student" && (
                                            <td className="px-4 py-2 text-slate-500">{entry.instructor_name || "—"}</td>
                                        )}
                                        {data.role === "instructor" && (
                                            <td className="px-4 py-2 text-slate-500">{entry.section_name}</td>
                                        )}
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
