"use client";

import React from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CalendarEventItem } from "@/types/Calendar";
import {
    usePublishCalendarEvent,
    useCancelCalendarEvent,
    useDeleteCalendarEvent,
} from "@/hooks/useCalendarEvents";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    Calendar as CalendarIcon,
    Clock,
    MapPin,
    Users,
    CheckCircle2,
    XCircle,
    Trash2,
    Edit3,
    Sparkles,
    Loader2,
} from "lucide-react";
import { format, parseISO } from "date-fns";

interface EventDetailModalProps {
    event: CalendarEventItem | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onEdit?: (event: CalendarEventItem) => void;
}

export function EventDetailModal({
    event,
    open,
    onOpenChange,
    onEdit,
}: EventDetailModalProps) {
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("manage_calendar_events");

    const publishMutation = usePublishCalendarEvent();
    const cancelMutation = useCancelCalendarEvent();
    const deleteMutation = useDeleteCalendarEvent();

    if (!event) return null;

    const formatDateDisplay = (startStr: string, endStr: string) => {
        try {
            const start = parseISO(startStr);
            const end = parseISO(endStr);
            if (startStr === endStr) {
                return format(start, "EEEE, MMMM d, yyyy");
            }
            return `${format(start, "MMM d, yyyy")} – ${format(end, "MMM d, yyyy")}`;
        } catch {
            return startStr === endStr ? startStr : `${startStr} to ${endStr}`;
        }
    };

    const formatTimeDisplay = () => {
        if (event.is_all_day) return "All Day";
        if (event.start_time && event.end_time) {
            return `${event.start_time.slice(0, 5)} - ${event.end_time.slice(0, 5)}`;
        }
        if (event.start_time) {
            return `From ${event.start_time.slice(0, 5)}`;
        }
        return "All Day";
    };

    const handlePublish = async () => {
        await publishMutation.mutateAsync(event.id);
        onOpenChange(false);
    };

    const handleCancel = async () => {
        if (confirm("Are you sure you want to mark this event as cancelled?")) {
            await cancelMutation.mutateAsync(event.id);
            onOpenChange(false);
        }
    };

    const handleDelete = async () => {
        if (confirm("Are you sure you want to permanently delete this event? This action cannot be undone.")) {
            await deleteMutation.mutateAsync(event.id);
            onOpenChange(false);
        }
    };

    const isActionLoading =
        publishMutation.isPending || cancelMutation.isPending || deleteMutation.isPending;

    const getCategoryBadgeClass = (type: string) => {
        switch (type) {
            case "holiday":
                return "bg-rose-100 text-rose-800 dark:bg-rose-950 dark:text-rose-300 border-rose-200 dark:border-rose-900";
            case "closure":
                return "bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300 border-amber-200 dark:border-amber-900";
            case "exam":
                return "bg-purple-100 text-purple-800 dark:bg-purple-950 dark:text-purple-300 border-purple-200 dark:border-purple-900";
            case "meeting":
                return "bg-indigo-100 text-indigo-800 dark:bg-indigo-950 dark:text-indigo-300 border-indigo-200 dark:border-indigo-900";
            case "activity":
                return "bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 border-emerald-200 dark:border-emerald-900";
            default:
                return "bg-sky-100 text-sky-800 dark:bg-sky-950 dark:text-sky-300 border-sky-200 dark:border-sky-900";
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    title={event.title}
                    badge={
                        <div className="flex items-center gap-1.5 flex-wrap">
                            <Badge variant="outline" className={getCategoryBadgeClass(event.event_type)}>
                                {event.event_type_display || event.event_type}
                            </Badge>
                            {event.is_holiday && (
                                <Badge className="bg-red-500 hover:bg-red-600 text-white flex items-center gap-1">
                                    <Sparkles className="h-3 w-3" /> Holiday
                                </Badge>
                            )}
                            <Badge
                                variant={
                                    event.status === "published"
                                        ? "default"
                                        : event.status === "cancelled"
                                        ? "destructive"
                                        : "secondary"
                                }
                            >
                                {event.status_display || event.status}
                            </Badge>
                        </div>
                    }
                    subtitle={formatDateDisplay(event.start_date, event.end_date)}
                    metadata={<span>{formatTimeDisplay()}</span>}
                    onClose={() => onOpenChange(false)}
                />

                <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                    <div className="space-y-4 text-sm text-slate-700 dark:text-slate-300">
                    <div className="flex items-start gap-3">
                        <CalendarIcon className="h-4 w-4 text-slate-500 mt-0.5 shrink-0" />
                        <div>
                            <span className="font-medium text-slate-900 dark:text-slate-100">Date:</span>{" "}
                            {formatDateDisplay(event.start_date, event.end_date)}
                        </div>
                    </div>

                    <div className="flex items-center gap-3">
                        <Clock className="h-4 w-4 text-slate-500 shrink-0" />
                        <div>
                            <span className="font-medium text-slate-900 dark:text-slate-100">Time:</span>{" "}
                            {formatTimeDisplay()}
                        </div>
                    </div>

                    {event.location && (
                        <div className="flex items-center gap-3">
                            <MapPin className="h-4 w-4 text-slate-500 shrink-0" />
                            <div>
                                <span className="font-medium text-slate-900 dark:text-slate-100">Location:</span>{" "}
                                {event.location}
                            </div>
                        </div>
                    )}

                    <div className="flex items-center gap-3">
                        <Users className="h-4 w-4 text-slate-500 shrink-0" />
                        <div>
                            <span className="font-medium text-slate-900 dark:text-slate-100">Audience:</span>{" "}
                            {event.audience_display || event.audience}
                        </div>
                    </div>

                    {event.academic_year_name && (
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                            Academic Year: <span className="font-medium">{event.academic_year_name}</span>
                        </div>
                    )}

                    {event.description && (
                        <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                            <h4 className="font-semibold text-slate-900 dark:text-slate-100 mb-1">Description</h4>
                            <p className="whitespace-pre-wrap text-slate-600 dark:text-slate-300 text-sm leading-relaxed">
                                {event.description}
                            </p>
                        </div>
                    )}

                    <div className="pt-2 text-xs text-slate-400 dark:text-slate-500">
                        Created by {event.created_by_username || "System"} on{" "}
                        {event.created_at ? format(parseISO(event.created_at), "PPp") : "—"}
                    </div>
                </div>
                </DialogBody>

                <DialogFooter className="px-6 py-3.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 shrink-0 flex flex-col sm:flex-row justify-between gap-2">
                    <div className="flex items-center gap-2">
                        {canManage && (
                            <>
                                {event.status === "draft" && (
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="text-emerald-600 hover:text-emerald-700"
                                        onClick={handlePublish}
                                        disabled={isActionLoading}
                                    >
                                        <CheckCircle2 className="h-4 w-4 mr-1" /> Publish
                                    </Button>
                                )}
                                {event.status === "published" && (
                                    <Button
                                        size="sm"
                                        variant="outline"
                                        className="text-amber-600 hover:text-amber-700"
                                        onClick={handleCancel}
                                        disabled={isActionLoading}
                                    >
                                        <XCircle className="h-4 w-4 mr-1" /> Cancel Event
                                    </Button>
                                )}
                                <Button
                                    size="sm"
                                    variant="outline"
                                    className="text-rose-600 hover:text-rose-700"
                                    onClick={handleDelete}
                                    disabled={isActionLoading}
                                >
                                    <Trash2 className="h-4 w-4 mr-1" /> Delete
                                </Button>
                            </>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        {canManage && onEdit && (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => {
                                    onOpenChange(false);
                                    onEdit(event);
                                }}
                                disabled={isActionLoading}
                            >
                                <Edit3 className="h-4 w-4 mr-1" /> Edit
                            </Button>
                        )}
                        <Button
                            size="sm"
                            onClick={() => onOpenChange(false)}
                            disabled={isActionLoading}
                        >
                            {isActionLoading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Close
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}

