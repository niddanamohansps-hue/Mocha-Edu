"use client";

import React, { useState, useEffect } from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    FormGrid,
    FormFieldWrapper,
} from "@/components/ui/form-layout";
import {
    CalendarEventItem,
    CalendarEventInput,
    CalendarEventType,
    CalendarAudience,
    CalendarEventStatus,
} from "@/types/Calendar";
import { useCreateCalendarEvent, useUpdateCalendarEvent } from "@/hooks/useCalendarEvents";
import { Calendar, Loader2 } from "lucide-react";

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
        if (endDate && endDate < val) {
            setEndDate(val);
        }
    };

    const validate = () => {
        const nextErrors: Record<string, string> = {};
        if (!title.trim()) nextErrors.title = "Event title is required";
        if (!startDate) nextErrors.start_date = "Start date is required";
        if (!endDate) nextErrors.end_date = "End date is required";
        if (startDate && endDate && endDate < startDate) {
            nextErrors.end_date = "End date cannot precede start date";
        }
        if (!isAllDay) {
            if (startTime && endTime && endTime <= startTime) {
                nextErrors.end_time = "End time must be after start time";
            }
        }
        setErrors(nextErrors);
        return Object.keys(nextErrors).length === 0;
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
            start_time: isAllDay ? null : (startTime || null),
            end_time: isAllDay ? null : (endTime || null),
            location: location.trim(),
            audience,
            status,
            academic_year: academicYearId || null,
        };

        if (initialEvent) {
            updateMutation.mutate(
                { id: initialEvent.id, data: payload },
                {
                    onSuccess: () => onOpenChange(false),
                }
            );
        } else {
            createMutation.mutate(payload, {
                onSuccess: () => onOpenChange(false),
            });
        }
    };

    const isSubmitting = createMutation.isPending || updateMutation.isPending;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl">
                <DialogHeader className="px-6 py-4.5 border-b border-slate-100 dark:border-slate-800 shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-white">
                        <Calendar className="w-5 h-5 text-sky-600" />
                        {initialEvent ? "Edit Academic Event" : "Create New Calendar Event"}
                    </DialogTitle>
                    <DialogDescription className="text-xs text-slate-500">
                        Schedule school activities, holidays, examinations, or academic milestones.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-5">
                        <FormFieldWrapper label="Event Title" htmlFor="event-title" required error={errors.title} colSpan="full">
                            <Input
                                id="event-title"
                                placeholder="e.g. Dashain Vacation / Midterm Exams"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                disabled={isSubmitting}
                            />
                        </FormFieldWrapper>

                        <FormGrid>
                            <FormFieldWrapper label="Event Category" htmlFor="event-type" required>
                                <Select
                                    value={eventType}
                                    onValueChange={(val) => handleEventTypeChange(val as CalendarEventType)}
                                    disabled={isSubmitting}
                                >
                                    <SelectTrigger id="event-type">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="academic">Academic Event</SelectItem>
                                        <SelectItem value="holiday">Holiday</SelectItem>
                                        <SelectItem value="closure">School Closure</SelectItem>
                                        <SelectItem value="exam">Examination</SelectItem>
                                        <SelectItem value="meeting">Meeting / Conference</SelectItem>
                                        <SelectItem value="activity">Extracurricular Activity</SelectItem>
                                    </SelectContent>
                                </Select>
                            </FormFieldWrapper>

                            <FormFieldWrapper label="Target Audience" htmlFor="event-audience">
                                <Select
                                    value={audience}
                                    onValueChange={(val) => setAudience(val as CalendarAudience)}
                                    disabled={isSubmitting}
                                >
                                    <SelectTrigger id="event-audience">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All School (Students, Parents, Staff)</SelectItem>
                                        <SelectItem value="staff">Staff Only</SelectItem>
                                        <SelectItem value="students_parents">Students & Parents</SelectItem>
                                    </SelectContent>
                                </Select>
                            </FormFieldWrapper>
                        </FormGrid>

                        <div className="flex items-center gap-6 py-2 px-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                            <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-700 dark:text-slate-300">
                                <input
                                    type="checkbox"
                                    checked={isHoliday}
                                    onChange={(e) => setIsHoliday(e.target.checked)}
                                    className="rounded border-slate-300 text-sky-600 focus:ring-sky-500 h-4 w-4"
                                    disabled={isSubmitting}
                                />
                                Official Holiday / Day Off
                            </label>

                            <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-700 dark:text-slate-300">
                                <input
                                    type="checkbox"
                                    checked={isAllDay}
                                    onChange={(e) => setIsAllDay(e.target.checked)}
                                    className="rounded border-slate-300 text-sky-600 focus:ring-sky-500 h-4 w-4"
                                    disabled={isSubmitting}
                                />
                                All Day Event
                            </label>
                        </div>

                        <FormGrid>
                            <FormFieldWrapper label="Start Date" htmlFor="start-date" required error={errors.start_date}>
                                <Input
                                    id="start-date"
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => handleStartDateChange(e.target.value)}
                                    disabled={isSubmitting}
                                />
                            </FormFieldWrapper>

                            <FormFieldWrapper label="End Date" htmlFor="end-date" required error={errors.end_date}>
                                <Input
                                    id="end-date"
                                    type="date"
                                    value={endDate}
                                    min={startDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    disabled={isSubmitting}
                                />
                            </FormFieldWrapper>
                        </FormGrid>

                        {!isAllDay && (
                            <FormGrid>
                                <FormFieldWrapper label="Start Time" htmlFor="start-time">
                                    <Input
                                        id="start-time"
                                        type="time"
                                        value={startTime}
                                        onChange={(e) => setStartTime(e.target.value)}
                                        disabled={isSubmitting}
                                    />
                                </FormFieldWrapper>

                                <FormFieldWrapper label="End Time" htmlFor="end-time" error={errors.end_time}>
                                    <Input
                                        id="end-time"
                                        type="time"
                                        value={endTime}
                                        onChange={(e) => setEndTime(e.target.value)}
                                        disabled={isSubmitting}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        )}

                        <FormGrid>
                            <FormFieldWrapper label="Location / Venue" htmlFor="location">
                                <Input
                                    id="location"
                                    placeholder="e.g. Main Auditorium / Sports Ground"
                                    value={location}
                                    onChange={(e) => setLocation(e.target.value)}
                                    disabled={isSubmitting}
                                />
                            </FormFieldWrapper>

                            <FormFieldWrapper label="Publication Status" htmlFor="status">
                                <Select
                                    value={status}
                                    onValueChange={(val) => setStatus(val as CalendarEventStatus)}
                                    disabled={isSubmitting}
                                >
                                    <SelectTrigger id="status">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="published">Published</SelectItem>
                                        <SelectItem value="draft">Draft</SelectItem>
                                        <SelectItem value="cancelled">Cancelled</SelectItem>
                                    </SelectContent>
                                </Select>
                            </FormFieldWrapper>
                        </FormGrid>

                        <FormFieldWrapper label="Description / Notes" htmlFor="description" colSpan="full">
                            <Textarea
                                id="description"
                                rows={3}
                                placeholder="Provide details about the schedule, instructions or requirements..."
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                disabled={isSubmitting}
                            />
                        </FormFieldWrapper>
                    </DialogBody>

                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={isSubmitting}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={isSubmitting}
                            className="bg-sky-600 hover:bg-sky-700 text-white min-w-[120px]"
                        >
                            {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            {initialEvent ? "Save Changes" : "Create Event"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
