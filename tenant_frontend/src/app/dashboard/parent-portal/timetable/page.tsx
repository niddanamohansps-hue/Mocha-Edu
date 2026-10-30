"use client";

import { useState, useMemo } from "react";
import {
    Clock,
    Calendar,
    BookOpen,
    User,
    MapPin,
    Filter,
} from "lucide-react";
import { useChildTimetable, useLinkedChildren } from "@/hooks/useParentPortal";
import { DAY_LABELS } from "@/types/ParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const DAYS = [
    { value: "all", label: "All Days" },
    { value: "1", label: "Monday" },
    { value: "2", label: "Tuesday" },
    { value: "3", label: "Wednesday" },
    { value: "4", label: "Thursday" },
    { value: "5", label: "Friday" },
    { value: "6", label: "Saturday" },
];

export default function ParentPortalTimetablePage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_child_timetable");

    const { data: children } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);
    const [activeDayFilter, setActiveDayFilter] = useState<string>("all");

    const effectiveChildId = selectedChildId || children?.[0]?.student_id;
    const { data, isLoading, isError, refetch } = useChildTimetable(effectiveChildId);

    if (!canView) {
        return <Unauthorized />;
    }

    const sortedEntries = useMemo(() => {
        if (!data?.results) return [];
        return [...data.results]
            .sort((a, b) => a.day_of_week - b.day_of_week || a.period_order - b.period_order)
            .filter((entry) => {
                if (activeDayFilter === "all") return true;
                return String(entry.day_of_week) === activeDayFilter;
            });
    }, [data, activeDayFilter]);

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Clock className="w-6 h-6 text-sky-600 dark:text-sky-400" />
                        <span>Class Timetable Schedule</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Weekly period distribution, allocated subject teachers, and classroom locations.
                    </p>
                </div>

                <div className="flex items-center gap-3 self-start sm:self-auto">
                    <ChildSwitcher
                        childOptions={children || []}
                        selectedId={effectiveChildId}
                        onChange={setSelectedChildId}
                    />
                </div>
            </div>

            {/* Filter Pills Bar */}
            {data && data.results.length > 0 && (
                <div className="p-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar py-0.5">
                        {DAYS.map((day) => (
                            <button
                                key={day.value}
                                type="button"
                                onClick={() => setActiveDayFilter(day.value)}
                                className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition cursor-pointer ${
                                    activeDayFilter === day.value
                                        ? "bg-sky-600 text-white shadow-2xs"
                                        : "bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 hover:bg-slate-200"
                                }`}
                            >
                                {day.label}
                            </button>
                        ))}
                    </div>

                    <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 shrink-0">
                        <span>Cohort:</span>
                        <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300 border border-sky-200/80 text-[11px] py-0.5">
                            {data.section}
                        </Badge>
                    </div>
                </div>
            )}

            {!effectiveChildId ? (
                <EmptyState
                    title={
                        children && children.length === 0
                            ? "No children are linked to your parent account."
                            : "Select a child to view their class timetable."
                    }
                    className="py-16"
                />
            ) : isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !data || !data.section ? (
                <EmptyState
                    title="Student not enrolled in an active section."
                    description="This student record has not been assigned to a classroom section yet."
                    className="py-16"
                />
            ) : data.results.length === 0 ? (
                <EmptyState
                    title="No timetable periods configured."
                    description="The academic section schedule has not been published yet."
                    className="py-16"
                />
            ) : (
                <TableShell>
                    <Table>
                        <TableHeader>
                            <TableRow className="bg-slate-50/75 dark:bg-slate-900/60">
                                <TableHead className="w-28 text-xs font-bold text-slate-700 dark:text-slate-300">
                                    Day
                                </TableHead>
                                <TableHead className="w-24 text-xs font-bold text-slate-700 dark:text-slate-300">
                                    Period
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                    Subject
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                    Instructor / Teacher
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">
                                    Room / Hall
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {sortedEntries.map((entry) => (
                                <TableRow key={entry.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                    <TableCell>
                                        <Badge
                                            variant="outline"
                                            className="text-xs font-semibold bg-slate-50 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                                        >
                                            {DAY_LABELS[entry.day_of_week] || `Day ${entry.day_of_week}`}
                                        </Badge>
                                    </TableCell>
                                    <TableCell className="text-xs font-bold text-slate-900 dark:text-white">
                                        {entry.period_name}
                                    </TableCell>
                                    <TableCell>
                                        <div className="flex items-center gap-2">
                                            <div className="p-1 rounded-md bg-sky-50 dark:bg-sky-950 text-sky-600 dark:text-sky-400">
                                                <BookOpen className="w-3.5 h-3.5" />
                                            </div>
                                            <span className="text-xs font-bold text-slate-900 dark:text-white">
                                                {entry.subject_name}
                                            </span>
                                        </div>
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-600 dark:text-slate-300">
                                        {entry.instructor_name ? (
                                            <div className="flex items-center gap-1.5">
                                                <User className="w-3.5 h-3.5 text-slate-400" />
                                                <span>{entry.instructor_name}</span>
                                            </div>
                                        ) : (
                                            <span className="text-slate-400">—</span>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-xs text-slate-500 dark:text-slate-400">
                                        {entry.room_name ? (
                                            <div className="flex items-center gap-1.5">
                                                <MapPin className="w-3.5 h-3.5 text-slate-400" />
                                                <span>{entry.room_name}</span>
                                            </div>
                                        ) : (
                                            <span className="text-slate-400">—</span>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableShell>
            )}
        </div>
    );
}
