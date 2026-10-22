"use client";

import React, { useState, useMemo } from "react";
import {
    format,
    addMonths,
    subMonths,
    startOfMonth,
    endOfMonth,
    startOfWeek,
    endOfWeek,
    eachDayOfInterval,
    isSameMonth,
    isSameDay,
    isToday,
    parseISO,
} from "date-fns";
import {
    Calendar as CalendarIcon,
    ChevronLeft,
    ChevronRight,
    Plus,
    Filter,
    Search,
    Sparkles,
    AlertCircle,
    Clock,
    MapPin,
    CalendarDays,
    ListFilter,
    Layers,
    GraduationCap,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useCalendarEvents, useUpcomingEvents } from "@/hooks/useCalendarEvents";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    CalendarEventItem,
    CalendarEventType,
    CalendarAudience,
} from "@/types/Calendar";
import { EventFormModal } from "@/components/dashboard/calendar/EventFormModal";
import { EventDetailModal } from "@/components/dashboard/calendar/EventDetailModal";

const EVENT_TYPE_STYLES: Record<
    CalendarEventType,
    { bg: string; text: string; border: string; dot: string; label: string }
> = {
    holiday: {
        bg: "bg-rose-50 dark:bg-rose-950/40",
        text: "text-rose-700 dark:text-rose-300",
        border: "border-rose-200 dark:border-rose-900/60",
        dot: "bg-rose-500",
        label: "Holiday",
    },
    closure: {
        bg: "bg-amber-50 dark:bg-amber-950/40",
        text: "text-amber-700 dark:text-amber-300",
        border: "border-amber-200 dark:border-amber-900/60",
        dot: "bg-amber-500",
        label: "School Closure",
    },
    exam: {
        bg: "bg-purple-50 dark:bg-purple-950/40",
        text: "text-purple-700 dark:text-purple-300",
        border: "border-purple-200 dark:border-purple-900/60",
        dot: "bg-purple-500",
        label: "Examination",
    },
    meeting: {
        bg: "bg-indigo-50 dark:bg-indigo-950/40",
        text: "text-indigo-700 dark:text-indigo-300",
        border: "border-indigo-200 dark:border-indigo-900/60",
        dot: "bg-indigo-500",
        label: "Meeting",
    },
    activity: {
        bg: "bg-emerald-50 dark:bg-emerald-950/40",
        text: "text-emerald-700 dark:text-emerald-300",
        border: "border-emerald-200 dark:border-emerald-900/60",
        dot: "bg-emerald-500",
        label: "Activity",
    },
    academic: {
        bg: "bg-sky-50 dark:bg-sky-950/40",
        text: "text-sky-700 dark:text-sky-300",
        border: "border-sky-200 dark:border-sky-900/60",
        dot: "bg-sky-500",
        label: "Academic",
    },
};

export default function AcademicCalendarPage() {
    const { selectedYear } = useAcademicYear();
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("manage_calendar_events");

    // Navigation and view state
    const [currentDate, setCurrentDate] = useState<Date>(new Date());
    const [viewMode, setViewMode] = useState<"month" | "list">("month");

    // Filters
    const [selectedType, setSelectedType] = useState<CalendarEventType | "">("");
    const [selectedAudience, setSelectedAudience] = useState<CalendarAudience | "">("");
    const [holidaysOnly, setHolidaysOnly] = useState(false);
    const [searchQuery, setSearchQuery] = useState("");

    // Modals
    const [isCreateOpen, setIsCreateOpen] = useState(false);
    const [createDefaultDate, setCreateDefaultDate] = useState<string>("");
    const [detailEvent, setDetailEvent] = useState<CalendarEventItem | null>(null);
    const [editingEvent, setEditingEvent] = useState<CalendarEventItem | null>(null);

    // Calculate month boundary strings (YYYY-MM-DD)
    const monthStart = startOfMonth(currentDate);
    const monthEnd = endOfMonth(currentDate);
    const calendarStart = startOfWeek(monthStart, { weekStartsOn: 0 }); // Sunday
    const calendarEnd = endOfWeek(monthEnd, { weekStartsOn: 0 });

    const dateFromStr = format(calendarStart, "yyyy-MM-dd");
    const dateToStr = format(calendarEnd, "yyyy-MM-dd");

    // Query events covering the visible calendar range
    const {
        data: events = [],
        isLoading,
        isError,
    } = useCalendarEvents({
        date_from: dateFromStr,
        date_to: dateToStr,
        academic_year: selectedYear?.id,
        event_type: selectedType,
        audience: selectedAudience,
        is_holiday: holidaysOnly ? true : "",
        search: searchQuery.trim(),
    });

    const { data: upcomingEvents = [] } = useUpcomingEvents(5);

    // Generate grid of days for the month view
    const daysInView = useMemo(() => {
        return eachDayOfInterval({ start: calendarStart, end: calendarEnd });
    }, [calendarStart, calendarEnd]);

    // Fast lookup map: date string (YYYY-MM-DD) -> events occurring on that day
    const eventsByDate = useMemo(() => {
        const map = new Map<string, CalendarEventItem[]>();
        events.forEach((evt) => {
            const startStr = evt.start_date;
            const endStr = evt.end_date;
            daysInView.forEach((day) => {
                const dayStr = format(day, "yyyy-MM-dd");
                if (dayStr >= startStr && dayStr <= endStr) {
                    const existing = map.get(dayStr) || [];
                    existing.push(evt);
                    map.set(dayStr, existing);
                }
            });
        });
        return map;
    }, [events, daysInView]);

    const handlePrevMonth = () => setCurrentDate((prev) => subMonths(prev, 1));
    const handleNextMonth = () => setCurrentDate((prev) => addMonths(prev, 1));
    const handleToday = () => setCurrentDate(new Date());

    const handleDayClick = (day: Date) => {
        if (!canManage) return;
        setCreateDefaultDate(format(day, "yyyy-MM-dd"));
        setEditingEvent(null);
        setIsCreateOpen(true);
    };

    const handleEditFromDetail = (event: CalendarEventItem) => {
        setDetailEvent(null);
        setEditingEvent(event);
        setIsCreateOpen(true);
    };

    return (
        <div className="space-y-6 pb-12">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2">
                        <CalendarIcon className="h-6 w-6 text-sky-600" />
                        Academic Calendar & Holidays
                    </h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Track school terms, holidays, examinations, closures, and institutional events.
                        {selectedYear && (
                            <span className="ml-2 inline-flex items-center gap-1 font-medium text-slate-700 dark:text-slate-300">
                                <GraduationCap className="h-3.5 w-3.5 text-sky-500" />
                                {selectedYear.name}
                            </span>
                        )}
                    </p>
                </div>

                <div className="flex items-center gap-2">
                    {canManage && (
                        <Button
                            onClick={() => {
                                setEditingEvent(null);
                                setCreateDefaultDate(format(new Date(), "yyyy-MM-dd"));
                                setIsCreateOpen(true);
                            }}
                            className="bg-sky-600 hover:bg-sky-700 text-white"
                        >
                            <Plus className="h-4 w-4 mr-1.5" /> Add Event
                        </Button>
                    )}
                </div>
            </div>

            {/* Quick Stats / Overview */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card className="shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs uppercase tracking-wider font-semibold text-slate-500">
                            Current Month
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-slate-900 dark:text-slate-100">
                            {format(currentDate, "MMMM yyyy")}
                        </div>
                        <p className="text-xs text-slate-500 mt-1">
                            {events.length} event{events.length === 1 ? "" : "s"} scheduled
                        </p>
                    </CardContent>
                </Card>

                <Card className="shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs uppercase tracking-wider font-semibold text-slate-500">
                            Holidays
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-rose-600 dark:text-rose-400">
                            {events.filter((e) => e.is_holiday).length}
                        </div>
                        <p className="text-xs text-slate-500 mt-1">Holidays in visible range</p>
                    </CardContent>
                </Card>

                <Card className="shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs uppercase tracking-wider font-semibold text-slate-500">
                            Examinations
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-purple-600 dark:text-purple-400">
                            {events.filter((e) => e.event_type === "exam").length}
                        </div>
                        <p className="text-xs text-slate-500 mt-1">Exam periods scheduled</p>
                    </CardContent>
                </Card>

                <Card className="shadow-sm">
                    <CardHeader className="pb-2">
                        <CardTitle className="text-xs uppercase tracking-wider font-semibold text-slate-500">
                            School Status
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        {(() => {
                            const todayStr = format(new Date(), "yyyy-MM-dd");
                            const todayEvents = events.filter(
                                (e) =>
                                    todayStr >= e.start_date &&
                                    todayStr <= e.end_date &&
                                    (e.is_holiday || e.event_type === "closure")
                            );
                            if (todayEvents.length > 0) {
                                return (
                                    <>
                                        <div className="text-lg font-bold text-rose-600 dark:text-rose-400">
                                            Closed Today
                                        </div>
                                        <p className="text-xs text-slate-500 mt-1 truncate">
                                            {todayEvents[0].title}
                                        </p>
                                    </>
                                );
                            }
                            return (
                                <>
                                    <div className="text-lg font-bold text-emerald-600 dark:text-emerald-400">
                                        Open & Operating
                                    </div>
                                    <p className="text-xs text-slate-500 mt-1">Regular academic operations</p>
                                </>
                            );
                        })()}
                    </CardContent>
                </Card>
            </div>

            {/* Filter Bar & Controls */}
            <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4 bg-white dark:bg-slate-900 p-4 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
                {/* Month navigation */}
                <div className="flex items-center gap-2">
                    <Button variant="outline" size="sm" onClick={handlePrevMonth}>
                        <ChevronLeft className="h-4 w-4" />
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleToday}>
                        Today
                    </Button>
                    <Button variant="outline" size="sm" onClick={handleNextMonth}>
                        <ChevronRight className="h-4 w-4" />
                    </Button>
                    <span className="text-base font-semibold ml-2 text-slate-800 dark:text-slate-200 min-w-[140px]">
                        {format(currentDate, "MMMM yyyy")}
                    </span>
                </div>

                {/* Filters */}
                <div className="flex flex-wrap items-center gap-2.5">
                    <div className="relative w-44">
                        <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                        <Input aria-label="Search events..."
                            placeholder="Search events..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="h-8 pl-8 text-xs"
                        />
                    </div>

                    <select
                        value={selectedType}
                        onChange={(e) => setSelectedType(e.target.value as CalendarEventType | "")}
                        className="h-8 rounded-md border border-input bg-background px-2.5 text-xs"
                    >
                        <option value="">All Categories</option>
                        <option value="holiday">Holidays</option>
                        <option value="academic">Academic</option>
                        <option value="closure">School Closures</option>
                        <option value="exam">Exams</option>
                        <option value="meeting">Meetings</option>
                        <option value="activity">Activities</option>
                    </select>

                    <Button
                        size="sm"
                        variant={holidaysOnly ? "default" : "outline"}
                        onClick={() => setHolidaysOnly(!holidaysOnly)}
                        className={`h-8 text-xs flex items-center gap-1 ${
                            holidaysOnly
                                ? "bg-rose-600 hover:bg-rose-700 text-white"
                                : "text-rose-700 dark:text-rose-300 border-rose-200 dark:border-rose-900"
                        }`}
                    >
                        <Sparkles className="h-3 w-3" />
                        Holidays Only
                    </Button>

                    <div className="flex items-center border border-slate-200 dark:border-slate-800 rounded-md p-0.5">
                        <Button
                            size="sm"
                            variant={viewMode === "month" ? "secondary" : "ghost"}
                            className="h-7 px-2.5 text-xs"
                            onClick={() => setViewMode("month")}
                        >
                            <CalendarDays className="h-3.5 w-3.5 mr-1" /> Month
                        </Button>
                        <Button
                            size="sm"
                            variant={viewMode === "list" ? "secondary" : "ghost"}
                            className="h-7 px-2.5 text-xs"
                            onClick={() => setViewMode("list")}
                        >
                            <ListFilter className="h-3.5 w-3.5 mr-1" /> List
                        </Button>
                    </div>
                </div>
            </div>

            {/* Main Content Layout */}
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
                {/* Calendar / Events view (3 cols on large screen) */}
                <div className="lg:col-span-3 space-y-4">
                    {isLoading ? (
                        <div className="h-96 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex items-center justify-center">
                            <div className="text-center text-slate-500">
                                <CalendarDays className="h-8 w-8 animate-pulse mx-auto mb-2 text-sky-500" />
                                <p className="text-sm">Loading calendar events...</p>
                            </div>
                        </div>
                    ) : isError ? (
                        <div className="p-8 text-center bg-rose-50 dark:bg-rose-950/20 rounded-xl border border-rose-200 dark:border-rose-900">
                            <AlertCircle className="h-8 w-8 mx-auto text-rose-500 mb-2" />
                            <p className="text-sm text-rose-700 dark:text-rose-300 font-medium">
                                Failed to load calendar events. Please try again.
                            </p>
                        </div>
                    ) : viewMode === "month" ? (
                        /* Month Grid View */
                        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                            {/* Days of week header */}
                            <div className="grid grid-cols-7 border-b border-slate-200 dark:border-slate-800 text-center bg-slate-50/50 dark:bg-slate-800/40 py-2 text-xs font-semibold text-slate-600 dark:text-slate-400">
                                <div>Sun</div>
                                <div>Mon</div>
                                <div>Tue</div>
                                <div>Wed</div>
                                <div>Thu</div>
                                <div>Fri</div>
                                <div>Sat</div>
                            </div>

                            {/* Days grid */}
                            <div className="grid grid-cols-7 auto-rows-fr divide-x divide-y divide-slate-100 dark:divide-slate-800">
                                {daysInView.map((day) => {
                                    const dayStr = format(day, "yyyy-MM-dd");
                                    const dayEvents = eventsByDate.get(dayStr) || [];
                                    const isCurrentMonth = isSameMonth(day, currentDate);
                                    const isTodayDate = isToday(day);

                                    return (
                                        <div
                                            key={dayStr}
                                            onClick={() => handleDayClick(day)}
                                            className={`min-h-[110px] p-1.5 flex flex-col transition-colors cursor-pointer group relative ${
                                                isCurrentMonth
                                                    ? "bg-white dark:bg-slate-900 hover:bg-slate-50/80 dark:hover:bg-slate-800/50"
                                                    : "bg-slate-50/40 dark:bg-slate-950/40 text-slate-400 dark:text-slate-600"
                                            }`}
                                        >
                                            <div className="flex items-center justify-between mb-1">
                                                <span
                                                    className={`inline-flex items-center justify-center text-xs font-medium rounded-full h-6 w-6 ${
                                                        isTodayDate
                                                            ? "bg-sky-600 text-white font-bold"
                                                            : isCurrentMonth
                                                            ? "text-slate-800 dark:text-slate-200"
                                                            : "text-slate-400 dark:text-slate-600"
                                                    }`}
                                                >
                                                    {format(day, "d")}
                                                </span>
                                                {canManage && (
                                                    <span className="opacity-0 group-hover:opacity-100 text-[10px] text-sky-600 dark:text-sky-400 pr-1">
                                                        + Add
                                                    </span>
                                                )}
                                            </div>

                                            {/* Event pills */}
                                            <div className="space-y-1 flex-1 overflow-hidden">
                                                {dayEvents.slice(0, 3).map((evt) => {
                                                    const style =
                                                        EVENT_TYPE_STYLES[evt.event_type] ||
                                                        EVENT_TYPE_STYLES.academic;
                                                    return (
                                                        <div
                                                            key={evt.id}
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                setDetailEvent(evt);
                                                            }}
                                                            className={`text-[11px] px-1.5 py-0.5 rounded truncate border font-medium flex items-center gap-1 transition-transform hover:scale-[1.02] ${style.bg} ${style.text} ${style.border}`}
                                                            title={`${evt.title} (${evt.event_type_display})`}
                                                        >
                                                            <span
                                                                className={`h-1.5 w-1.5 rounded-full shrink-0 ${style.dot}`}
                                                            />
                                                            <span className="truncate">{evt.title}</span>
                                                        </div>
                                                    );
                                                })}
                                                {dayEvents.length > 3 && (
                                                    <div className="text-[10px] text-slate-500 font-medium pl-1">
                                                        +{dayEvents.length - 3} more
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    ) : (
                        /* List View */
                        <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm divide-y divide-slate-100 dark:divide-slate-800">
                            {events.length === 0 ? (
                                <div className="p-12 text-center text-slate-500">
                                    <CalendarDays className="h-8 w-8 mx-auto mb-2 text-slate-400" />
                                    <p className="text-base font-medium">No events found</p>
                                    <p className="text-xs text-slate-400 mt-1">
                                        Try adjusting your filters or date range.
                                    </p>
                                </div>
                            ) : (
                                events.map((evt) => {
                                    const style =
                                        EVENT_TYPE_STYLES[evt.event_type] ||
                                        EVENT_TYPE_STYLES.academic;
                                    return (
                                        <div
                                            key={evt.id}
                                            onClick={() => setDetailEvent(evt)}
                                            className="p-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 hover:bg-slate-50/70 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                                        >
                                            <div className="space-y-1">
                                                <div className="flex items-center gap-2">
                                                    <span
                                                        className={`text-xs px-2 py-0.5 rounded-full font-medium border ${style.bg} ${style.text} ${style.border}`}
                                                    >
                                                        {evt.event_type_display}
                                                    </span>
                                                    {evt.is_holiday && (
                                                        <Badge className="bg-rose-500 text-white text-[10px] px-1.5 py-0 h-4">
                                                            Holiday
                                                        </Badge>
                                                    )}
                                                    <h3 className="font-semibold text-slate-900 dark:text-slate-100 text-sm">
                                                        {evt.title}
                                                    </h3>
                                                </div>

                                                {evt.description && (
                                                    <p className="text-xs text-slate-500 line-clamp-1 max-w-xl">
                                                        {evt.description}
                                                    </p>
                                                )}

                                                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                                                    <span className="flex items-center gap-1">
                                                        <CalendarIcon className="h-3.5 w-3.5 text-slate-400" />
                                                        {evt.start_date === evt.end_date
                                                            ? format(parseISO(evt.start_date), "MMM d, yyyy")
                                                            : `${format(parseISO(evt.start_date), "MMM d")} – ${format(
                                                                  parseISO(evt.end_date),
                                                                  "MMM d, yyyy"
                                                              )}`}
                                                    </span>
                                                    <span className="flex items-center gap-1">
                                                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                                                        {evt.is_all_day ? "All Day" : evt.start_time?.slice(0, 5)}
                                                    </span>
                                                    {evt.location && (
                                                        <span className="flex items-center gap-1">
                                                            <MapPin className="h-3.5 w-3.5 text-slate-400" />
                                                            {evt.location}
                                                        </span>
                                                    )}
                                                </div>
                                            </div>

                                            <div className="shrink-0 flex items-center gap-2">
                                                <Badge
                                                    variant={
                                                        evt.status === "published"
                                                            ? "default"
                                                            : evt.status === "cancelled"
                                                            ? "destructive"
                                                            : "secondary"
                                                    }
                                                    className="text-xs"
                                                >
                                                    {evt.status_display}
                                                </Badge>
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </div>
                    )}
                </div>

                {/* Right sidebar: Upcoming Events & Legend */}
                <div className="space-y-6">
                    {/* Upcoming Events Box */}
                    <Card className="shadow-sm">
                        <CardHeader className="pb-3 border-b border-slate-100 dark:border-slate-800">
                            <CardTitle className="text-sm font-bold flex items-center gap-2">
                                <Clock className="h-4 w-4 text-sky-600" />
                                Upcoming Events
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-3 divide-y divide-slate-100 dark:divide-slate-800">
                            {upcomingEvents.length === 0 ? (
                                <p className="text-xs text-slate-500 py-3 text-center">
                                    No upcoming events in the next 30 days.
                                </p>
                            ) : (
                                upcomingEvents.map((evt) => {
                                    const style =
                                        EVENT_TYPE_STYLES[evt.event_type] ||
                                        EVENT_TYPE_STYLES.academic;
                                    return (
                                        <div
                                            key={evt.id}
                                            onClick={() => setDetailEvent(evt)}
                                            className="py-2.5 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40 rounded px-1.5 transition-colors"
                                        >
                                            <div className="flex items-center justify-between text-xs">
                                                <span className="font-semibold text-slate-800 dark:text-slate-200 truncate">
                                                    {evt.title}
                                                </span>
                                                <span
                                                    className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${style.bg} ${style.text}`}
                                                >
                                                    {evt.event_type_display}
                                                </span>
                                            </div>
                                            <div className="text-[11px] text-slate-500 mt-1 flex items-center justify-between">
                                                <span>
                                                    {format(parseISO(evt.start_date), "MMM d, yyyy")}
                                                </span>
                                                {evt.is_holiday && (
                                                    <span className="text-rose-600 dark:text-rose-400 font-semibold text-[10px]">
                                                        Holiday
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })
                            )}
                        </CardContent>
                    </Card>

                    {/* Category Legend */}
                    <Card className="shadow-sm">
                        <CardHeader className="pb-2 border-b border-slate-100 dark:border-slate-800">
                            <CardTitle className="text-xs font-bold uppercase tracking-wider text-slate-500">
                                Categories
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="pt-3 space-y-2 text-xs">
                            {Object.entries(EVENT_TYPE_STYLES).map(([key, style]) => (
                                <div key={key} className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                        <span className={`h-2.5 w-2.5 rounded-full ${style.dot}`} />
                                        <span className="text-slate-700 dark:text-slate-300">
                                            {style.label}
                                        </span>
                                    </div>
                                    <span
                                        className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${style.bg} ${style.text}`}
                                    >
                                        {key}
                                    </span>
                                </div>
                            ))}
                        </CardContent>
                    </Card>
                </div>
            </div>

            {/* Modals */}
            <EventFormModal
                open={isCreateOpen}
                onOpenChange={setIsCreateOpen}
                initialEvent={editingEvent}
                defaultDate={createDefaultDate}
                academicYearId={selectedYear?.id}
            />

            <EventDetailModal
                open={Boolean(detailEvent)}
                onOpenChange={(open) => !open && setDetailEvent(null)}
                event={detailEvent}
                onEdit={handleEditFromDetail}
            />
        </div>
    );
}

