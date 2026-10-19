"use client";

import React, { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    CalendarEventItem,
    CalendarEventInput,
    CalendarEventType,
    CalendarAudience,
    CalendarEventStatus,
} from "@/types/Calendar";
import { useCreateCalendarEvent, useUpdateCalendarEvent } from "@/hooks/useCalendarEvents";
import { Loader2 } from "lucide-react";

interface EventFormModalProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    initialEvent?: CalendarEventItem | null;
    defaultDate?: string;
    academicYearId?: string | null;
}

export function EventFormModal({
    open,
    onOpenChange,
    initialEvent,
    defaultDate,
    academicYearId,
}: EventFormModalProps) {
    const createMutation = useCreateCalendarEvent();
    const updateMutation = useUpdateCalendarEvent();

    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [eventType, setEventType] = useState<CalendarEventType>("academic");
    const [isHoliday, setIsHoliday] = useState(false);
    const [startDate, setStartDate] = useState("");
    const [endDate, setEndDate] = useState("");
    const [isAllDay, setIsAllDay] = useState(true);
    const [startTime, setStartTime] = useState("");
    const [endTime, setEndTime] = useState("");
    const [location, setLocation] = useState("");
    const [audience, setAudience] = useState<CalendarAudience>("all");
    const [status, setStatus] = useState<CalendarEventStatus>("published");
    const [errors, setErrors] = useState<Record<string, string>>({});

    useEffect(() => {
        if (open) {
            if (initialEvent) {
                setTitle(initialEvent.title || "");
                setDescription(initialEvent.description || "");
                setEventType(initialEvent.event_type || "academic");
                setIsHoliday(Boolean(initialEvent.is_holiday));
                setStartDate(initialEvent.start_date || "");
                setEndDate(initialEvent.end_date || "");
                setIsAllDay(Boolean(initialEvent.is_all_day));
                setStartTime(initialEvent.start_time ? initialEvent.start_time.slice(0, 5) : "");
                setEndTime(initialEvent.end_time ? initialEvent.end_time.slice(0, 5) : "");
                setLocation(initialEvent.location || "");
                setAudience(initialEvent.audience || "all");
                setStatus(initialEvent.status || "published");
            } else {
                const today = defaultDate || new Date().toISOString().split("T")[0];
                setTitle("");
                setDescription("");
                setEventType("academic");
                setIsHoliday(false);
                setStartDate(today);
                setEndDate(today);
                setIsAllDay(true);
                setStartTime("");
                setEndTime("");
                setLocation("");
                setAudience("all");
                setStatus("published");
            }
            setErrors({});
        }
    }, [open, initialEvent, defaultDate]);

    const handleEventTypeChange = (type: CalendarEventType) => {
        setEventType(type);
        if (type === "holiday" || type === "closure") {
            setIsHoliday(true);
        } else {
            setIsHoliday(false);
        }
    };

    const handleStartDateChange = (val: string) => {
        setStartDate(val);
        if (!endDate || endDate < val) {
            setEndDate(val);
        }
    };

    const validate = () => {
        const next: Record<string, string> = {};
        if (!title.trim()) next.title = "Title is required.";
        if (!startDate) next.start_date = "Start date is required.";
        if (!endDate) next.end_date = "End date is required.";
        if (startDate && endDate && endDate < startDate) {
            next.end_date = "End date cannot be earlier than start date.";
        }
        if (!isAllDay) {
            if (startDate === endDate && startTime && endTime && endTime <= startTime) {
                next.end_time = "End time must be after start time on the same day.";
            }
        }
        setErrors(next);
        return Object.keys(next).length === 0;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!validate()) return;

        const payload: CalendarEventInput = {
            title: title.trim(),
            description: description.trim(),
            event_type: eventType,
            is_holiday: isHoliday,
            start_date: startDate,
            end_date: endDate,
            is_all_day: isAllDay,
            start_time: !isAllDay && startTime ? (startTime.length === 5 ? `${startTime}:00` : startTime) : null,
            end_time: !isAllDay && endTime ? (endTime.length === 5 ? `${endTime}:00` : endTime) : null,
            location: location.trim(),
            audience,
            status,
            academic_year: academicYearId || null,
        };

        if (initialEvent) {
            await updateMutation.mutateAsync({ id: initialEvent.id, data: payload });
        } else {
            await createMutation.mutateAsync(payload);
        }
        onOpenChange(false);
    };

    const isSubmitting = createMutation.isPending || updateMutation.isPending;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle>{initialEvent ? "Edit Calendar Event" : "Create Calendar Event"}</DialogTitle>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                    <div className="space-y-1">
                        <Label htmlFor="event-title">Title *</Label>
                        <Input
                            id="event-title"
                            placeholder="e.g. Dashain Vacation / Midterm Exams"
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            disabled={isSubmitting}
                        />
                        {errors.title && <p className="text-xs text-red-500">{errors.title}</p>}
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <Label htmlFor="event-type">Category *</Label>
                            <select
                                id="event-type"
                                value={eventType}
                                onChange={(e) => handleEventTypeChange(e.target.value as CalendarEventType)}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                disabled={isSubmitting}
                            >
                                <option value="academic">Academic Event</option>
                                <option value="holiday">Holiday</option>
                                <option value="closure">School Closure</option>
                                <option value="exam">Examination</option>
                                <option value="meeting">Meeting / Conference</option>
                                <option value="activity">Extracurricular Activity</option>
                            </select>
                        </div>

                        <div className="space-y-1">
                            <Label htmlFor="event-audience">Target Audience</Label>
                            <select
                                id="event-audience"
                                value={audience}
                                onChange={(e) => setAudience(e.target.value as CalendarAudience)}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                disabled={isSubmitting}
                            >
                                <option value="all">All School (Students, Parents, Staff)</option>
                                <option value="staff">Staff Only</option>
                                <option value="students_parents">Students & Parents</option>
                            </select>
                        </div>
                    </div>

                    <div className="flex items-center gap-6 py-1">
                        <label className="flex items-center gap-2 cursor-pointer text-sm font-medium">
                            <input
                                type="checkbox"
                                checked={isHoliday}
                                onChange={(e) => setIsHoliday(e.target.checked)}
                                className="rounded border-gray-300 text-primary focus:ring-primary h-4 w-4"
                                disabled={isSubmitting}
                            />
                            Official Holiday / Day Off
                        </label>

                        <label className="flex items-center gap-2 cursor-pointer text-sm font-medium">
                            <input
                                type="checkbox"
                                checked={isAllDay}
                                onChange={(e) => setIsAllDay(e.target.checked)}
                                className="rounded border-gray-300 text-primary focus:ring-primary h-4 w-4"
                                disabled={isSubmitting}
                            />
                            All Day Event
                        </label>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <Label htmlFor="start-date">Start Date *</Label>
                            <Input
                                id="start-date"
                                type="date"
                                value={startDate}
                                onChange={(e) => handleStartDateChange(e.target.value)}
                                disabled={isSubmitting}
                            />
                            {errors.start_date && <p className="text-xs text-red-500">{errors.start_date}</p>}
                        </div>

                        <div className="space-y-1">
                            <Label htmlFor="end-date">End Date *</Label>
                            <Input
                                id="end-date"
                                type="date"
                                value={endDate}
                                min={startDate}
                                onChange={(e) => setEndDate(e.target.value)}
                                disabled={isSubmitting}
                            />
                            {errors.end_date && <p className="text-xs text-red-500">{errors.end_date}</p>}
                        </div>
                    </div>

                    {!isAllDay && (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div className="space-y-1">
                                <Label htmlFor="start-time">Start Time</Label>
                                <Input
                                    id="start-time"
                                    type="time"
                                    value={startTime}
                                    onChange={(e) => setStartTime(e.target.value)}
                                    disabled={isSubmitting}
                                />
                            </div>

                            <div className="space-y-1">
                                <Label htmlFor="end-time">End Time</Label>
                                <Input
                                    id="end-time"
                                    type="time"
                                    value={endTime}
                                    onChange={(e) => setEndTime(e.target.value)}
                                    disabled={isSubmitting}
                                />
                                {errors.end_time && <p className="text-xs text-red-500">{errors.end_time}</p>}
                            </div>
                        </div>
                    )}

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-1">
                            <Label htmlFor="location">Location / Venue</Label>
                            <Input
                                id="location"
                                placeholder="e.g. Main Auditorium / Sports Ground"
                                value={location}
                                onChange={(e) => setLocation(e.target.value)}
                                disabled={isSubmitting}
                            />
                        </div>

                        <div className="space-y-1">
                            <Label htmlFor="status">Publication Status</Label>
                            <select
                                id="status"
                                value={status}
                                onChange={(e) => setStatus(e.target.value as CalendarEventStatus)}
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                disabled={isSubmitting}
                            >
                                <option value="published">Published</option>
                                <option value="draft">Draft</option>
                                <option value="cancelled">Cancelled</option>
                            </select>
                        </div>
                    </div>

                    <div className="space-y-1">
                        <Label htmlFor="description">Description / Notes</Label>
                        <Textarea
                            id="description"
                            rows={3}
                            placeholder="Provide details about the schedule, instructions or requirements..."
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            disabled={isSubmitting}
                        />
                    </div>

                    <DialogFooter className="pt-2">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={isSubmitting}
                        >
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSubmitting}>
                            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {initialEvent ? "Save Changes" : "Create Event"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

