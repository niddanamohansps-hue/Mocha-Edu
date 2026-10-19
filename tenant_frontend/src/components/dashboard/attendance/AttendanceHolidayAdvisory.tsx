"use client";

import React from "react";
import { format, parseISO, differenceInCalendarDays } from "date-fns";
import {
    AlertTriangle,
    Sparkles,
    Calendar,
    MapPin,
    AlertCircle,
    RotateCw,
    Info,
} from "lucide-react";
import { useAttendanceHolidayAdvisory } from "@/hooks/useCalendarEvents";
import { CalendarEventItem } from "@/types/Calendar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface AttendanceHolidayAdvisoryProps {
    date: string; // YYYY-MM-DD
    className?: string;
}

function formatDateRange(startStr: string, endStr: string): string {
    try {
        const start = parseISO(startStr);
        const end = parseISO(endStr);
        if (startStr === endStr) {
            return format(start, "d MMMM yyyy");
        }
        const days = differenceInCalendarDays(end, start) + 1;
        return `${format(start, "d MMM yyyy")} – ${format(end, "d MMM yyyy")} (${days} days)`;
    } catch {
        return startStr === endStr ? startStr : `${startStr} to ${endStr}`;
    }
}

export function AttendanceHolidayAdvisory({
    date,
    className = "",
}: AttendanceHolidayAdvisoryProps) {
    const {
        data: events = [],
        isLoading,
        isError,
        refetch,
        isFetching,
    } = useAttendanceHolidayAdvisory(date);

    if (isLoading) {
        return (
            <div
                className={`flex items-center gap-2 p-3 text-xs text-slate-500 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800 rounded-xl animate-pulse ${className}`}
                aria-live="polite"
            >
                <Info className="h-4 w-4 shrink-0 text-slate-400" />
                <span>Checking school calendar for {date}...</span>
            </div>
        );
    }

    if (isError) {
        return (
            <div
                role="status"
                aria-live="polite"
                className={`flex items-center justify-between gap-3 p-3 text-xs bg-amber-50/70 dark:bg-amber-950/20 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-900/40 rounded-xl ${className}`}
            >
                <div className="flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 text-amber-600 dark:text-amber-400 shrink-0" />
                    <span>
                        Calendar advisory check unavailable for {date}. You may still proceed with marking attendance.
                    </span>
                </div>
                <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => refetch()}
                    disabled={isFetching}
                    className="h-7 text-xs px-2 text-amber-800 dark:text-amber-300 hover:bg-amber-100 dark:hover:bg-amber-900/30"
                >
                    <RotateCw className={`h-3 w-3 mr-1 ${isFetching ? "animate-spin" : ""}`} />
                    Retry
                </Button>
            </div>
        );
    }

    if (!events || events.length === 0) {
        return null;
    }

    return (
        <section
            role="region"
            aria-label="Attendance Date Advisory"
            className={`space-y-2.5 ${className}`}
        >
            {events.map((event: CalendarEventItem) => {
                const isClosure = (event.event_type || "").toUpperCase() === "CLOSURE";
                const dateDisplay = formatDateRange(event.start_date, event.end_date);

                if (isClosure) {
                    return (
                        <div
                            key={event.id}
                            className="p-4 rounded-xl border border-amber-300 dark:border-amber-800/70 bg-amber-50/80 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 shadow-sm"
                        >
                            <div className="flex items-start gap-3">
                                <div className="p-2 rounded-lg bg-amber-100 dark:bg-amber-900/50 text-amber-700 dark:text-amber-300 shrink-0 mt-0.5">
                                    <AlertTriangle className="h-5 w-5" />
                                </div>
                                <div className="space-y-1 flex-1 min-w-0">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <Badge
                                            variant="outline"
                                            className="bg-amber-200/60 dark:bg-amber-900/70 text-amber-900 dark:text-amber-200 border-amber-300 dark:border-amber-700 text-xs font-semibold"
                                        >
                                            School Closure Advisory
                                        </Badge>
                                        <span className="text-xs text-amber-800 dark:text-amber-300 flex items-center gap-1">
                                            <Calendar className="h-3.5 w-3.5" />
                                            {dateDisplay}
                                        </span>
                                    </div>

                                    <h3 className="text-sm font-bold text-amber-950 dark:text-amber-100">
                                        School Closure Advisory: &ldquo;{event.title}&rdquo; covers the selected attendance date ({dateDisplay}).
                                    </h3>

                                    <p className="text-xs text-amber-800/90 dark:text-amber-300/90 leading-relaxed">
                                        Please verify school closure instructions before proceeding with attendance recording.
                                    </p>

                                    {event.description && (
                                        <div className="text-xs mt-2 pt-1.5 border-t border-amber-200/80 dark:border-amber-800/50 text-amber-900 dark:text-amber-200 whitespace-pre-wrap">
                                            <span className="font-semibold">Reason / Details:</span> {event.description}
                                        </div>
                                    )}

                                    {event.location && (
                                        <div className="text-xs flex items-center gap-1 text-amber-800 dark:text-amber-300 pt-0.5">
                                            <MapPin className="h-3 w-3 shrink-0" />
                                            <span>{event.location}</span>
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    );
                }

                // Standard Holiday Advisory
                return (
                    <div
                        key={event.id}
                        className="p-4 rounded-xl border border-rose-300 dark:border-rose-800/70 bg-rose-50/80 dark:bg-rose-950/30 text-rose-900 dark:text-rose-200 shadow-sm"
                    >
                        <div className="flex items-start gap-3">
                            <div className="p-2 rounded-lg bg-rose-100 dark:bg-rose-900/50 text-rose-700 dark:text-rose-300 shrink-0 mt-0.5">
                                <Sparkles className="h-5 w-5" />
                            </div>
                            <div className="space-y-1 flex-1 min-w-0">
                                <div className="flex flex-wrap items-center gap-2">
                                    <Badge
                                        variant="outline"
                                        className="bg-rose-200/60 dark:bg-rose-900/70 text-rose-900 dark:text-rose-200 border-rose-300 dark:border-rose-700 text-xs font-semibold"
                                    >
                                        Holiday Advisory
                                    </Badge>
                                    <span className="text-xs text-rose-800 dark:text-rose-300 flex items-center gap-1">
                                        <Calendar className="h-3.5 w-3.5" />
                                        {dateDisplay}
                                    </span>
                                </div>

                                <h3 className="text-sm font-bold text-rose-950 dark:text-rose-100">
                                    Holiday Advisory: &ldquo;{event.title}&rdquo; is scheduled for {dateDisplay}.
                                </h3>

                                <p className="text-xs text-rose-800/90 dark:text-rose-300/90 leading-relaxed">
                                    Please verify the school academic calendar before marking attendance for this date.
                                </p>

                                {event.description && (
                                    <div className="text-xs mt-2 pt-1.5 border-t border-rose-200/80 dark:border-rose-800/50 text-rose-900 dark:text-rose-200 whitespace-pre-wrap">
                                        <span className="font-semibold">Description:</span> {event.description}
                                    </div>
                                )}

                                {event.location && (
                                    <div className="text-xs flex items-center gap-1 text-rose-800 dark:text-rose-300 pt-0.5">
                                        <MapPin className="h-3 w-3 shrink-0" />
                                        <span>{event.location}</span>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                );
            })}
        </section>
    );
}

export default AttendanceHolidayAdvisory;

