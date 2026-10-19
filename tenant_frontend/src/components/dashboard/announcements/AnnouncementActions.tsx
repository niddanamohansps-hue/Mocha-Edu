"use client";

import { useState } from "react";
import Link from "next/link";
import { useAnnouncementAction, useDeleteAnnouncement } from "@/hooks/useAnnouncements";
import { usePermissions } from "@/providers/PermissionProvider";
import { Announcement, AUDIENCE_LABELS } from "@/types/Announcements";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";

type Pending = "publish" | "cancel" | "archive" | "delete" | null;

// datetime-local values are wall-clock strings without a zone; new Date()
// reads them in the browser's zone and toISOString() sends an unambiguous UTC instant.
function toIso(local: string) {
    return new Date(local).toISOString();
}

function toLocalInput(iso: string | null) {
    if (!iso) return "";
    const date = new Date(iso);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function AnnouncementActions({
    announcement,
    onDeleted,
}: {
    announcement: Announcement;
    onDeleted?: () => void;
}) {
    const { can } = usePermissions();
    const act = useAnnouncementAction();
    const remove = useDeleteAnnouncement();
    const [pending, setPending] = useState<Pending>(null);
    const [scheduleOpen, setScheduleOpen] = useState(false);
    const [when, setWhen] = useState("");
    const [whenError, setWhenError] = useState("");

    if (!can("manage_announcements")) return null;

    const { id, status } = announcement;
    const editable = status === "draft" || status === "scheduled";
    const busy = act.isPending || remove.isPending;

    const requiresBroadcast = announcement.audience_type === "all";
    const canBroadcast = can("broadcast_announcements");
    const broadcastBlocked = requiresBroadcast && !canBroadcast;

    const confirm = () => {
        if (pending === "delete") {
            remove.mutate(id, {
                onSuccess: () => {
                    setPending(null);
                    onDeleted?.();
                },
            });
        } else if (pending) {
            act.mutate({ id, action: pending }, { onSettled: () => setPending(null) });
        }
    };

    const submitSchedule = () => {
        if (!when) {
            setWhenError("Choose a date and time.");
            return;
        }
        if (new Date(when).getTime() <= Date.now()) {
            setWhenError("The time must be in the future.");
            return;
        }
        setWhenError("");
        act.mutate(
            { id, action: "schedule", scheduledAt: toIso(when) },
            { onSuccess: () => setScheduleOpen(false) }
        );
    };

    const copy: Record<Exclude<Pending, null>, { title: string; description: string; label: string; destructive: boolean }> = {
        publish: {
            title: "Publish now?",
            description: `This sends "${announcement.title}" immediately to ${AUDIENCE_LABELS[announcement.audience_type].toLowerCase()}${
                announcement.send_email ? ", including by email" : ""
            }. It cannot be unsent.`,
            label: "Publish",
            destructive: false,
        },
        cancel: {
            title: "Cancel the schedule?",
            description: "The announcement goes back to a draft and will not be sent automatically.",
            label: "Cancel schedule",
            destructive: false,
        },
        archive: {
            title: "Archive this announcement?",
            description: "Recipients will no longer see it in My Announcements. This cannot be undone.",
            label: "Archive",
            destructive: true,
        },
        delete: {
            title: "Delete this draft?",
            description: "The draft is removed permanently.",
            label: "Delete",
            destructive: true,
        },
    };

    return (
        <>
            <div className="flex flex-wrap gap-2">
                {editable && (
                    <Button asChild variant="outline" size="sm">
                        <Link href={`/dashboard/announcements/manage/${id}/edit`}>Edit</Link>
                    </Button>
                )}
                {(status === "draft" || status === "scheduled") && (
                    <Button
                        size="sm"
                        disabled={busy || broadcastBlocked}
                        title={broadcastBlocked ? "Broadcasting to everyone requires the broadcast_announcements permission" : undefined}
                        onClick={() => setPending("publish")}
                    >
                        Publish now
                    </Button>
                )}
                {(status === "draft" || status === "scheduled") && (
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={busy || broadcastBlocked}
                        title={broadcastBlocked ? "Scheduling to everyone requires the broadcast_announcements permission" : undefined}
                        onClick={() => {
                            setWhen(toLocalInput(announcement.scheduled_at));
                            setWhenError("");
                            setScheduleOpen(true);
                        }}
                    >
                        {status === "scheduled" ? "Reschedule" : "Schedule"}
                    </Button>
                )}
                {status === "scheduled" && (
                    <Button variant="outline" size="sm" disabled={busy} onClick={() => setPending("cancel")}>
                        Cancel schedule
                    </Button>
                )}
                {status === "published" && (
                    <Button variant="outline" size="sm" disabled={busy} onClick={() => setPending("archive")}>
                        Archive
                    </Button>
                )}
                {status === "draft" && (
                    <Button variant="outline" size="sm" disabled={busy} onClick={() => setPending("delete")}>
                        Delete
                    </Button>
                )}
            </div>

            {broadcastBlocked && (status === "draft" || status === "scheduled") && (
                <p className="text-xs text-amber-700 dark:text-amber-400 mt-2 font-medium">
                    Note: Broadcasting to Everyone requires the &quot;broadcast_announcements&quot; permission.
                </p>
            )}

            {pending && (
                <ConfirmationDialog
                    open
                    onOpenChange={(open) => !open && setPending(null)}
                    title={copy[pending].title}
                    description={copy[pending].description}
                    confirmLabel={copy[pending].label}
                    variant={copy[pending].destructive ? "destructive" : "default"}
                    isLoading={busy}
                    onConfirm={confirm}
                />
            )}

            <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{status === "scheduled" ? "Reschedule" : "Schedule"} announcement</DialogTitle>
                        <DialogDescription>
                            It is published automatically within about 5 minutes after this time.
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2">
                        <Label htmlFor="scheduled_at">Send at</Label>
                        <Input
                            id="scheduled_at"
                            type="datetime-local"
                            value={when}
                            onChange={(e) => setWhen(e.target.value)}
                        />
                        {whenError && <p className="text-xs text-red-600">{whenError}</p>}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={() => setScheduleOpen(false)} disabled={act.isPending}>
                            Close
                        </Button>
                        <Button onClick={submitSchedule} disabled={act.isPending}>
                            {act.isPending ? "Saving..." : "Save schedule"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
