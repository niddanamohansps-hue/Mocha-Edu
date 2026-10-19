"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAcademicLevels, useSections } from "@/hooks/useAcademics";
import { useCreateAnnouncement, useUpdateAnnouncement } from "@/hooks/useAnnouncements";
import { usePermissions } from "@/providers/PermissionProvider";
import { Announcement, AnnouncementInput, AUDIENCE_LABELS, AudienceType } from "@/types/Announcements";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

const SELECT_CLASS =
    "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm disabled:opacity-60 disabled:cursor-not-allowed";

export function AnnouncementForm({ existing }: { existing?: Announcement }) {
    const router = useRouter();
    const { can } = usePermissions();
    const { data: levels } = useAcademicLevels();
    const { data: sections } = useSections();
    const create = useCreateAnnouncement();
    const update = useUpdateAnnouncement();

    const isScheduled = existing?.status === "scheduled";

    const [title, setTitle] = useState(existing?.title ?? "");
    const [body, setBody] = useState(existing?.body ?? "");
    const [audience, setAudience] = useState<AudienceType>(existing?.audience_type ?? "all_students");
    const [sectionId, setSectionId] = useState(existing?.audience_section ?? "");
    const [levelId, setLevelId] = useState(existing?.audience_level ?? "");
    const [sendEmail, setSendEmail] = useState(existing?.send_email ?? false);
    const [errors, setErrors] = useState<Record<string, string>>({});

    // "Everyone" is offered only to holders of broadcast_announcements; the API
    // enforces this again at publish time.
    const audiences = (Object.keys(AUDIENCE_LABELS) as AudienceType[]).filter(
        (key) => key !== "all" || can("broadcast_announcements") || existing?.audience_type === "all"
    );
    const pending = create.isPending || update.isPending;

    const submit = (event: React.FormEvent) => {
        event.preventDefault();
        const next: Record<string, string> = {};
        if (!title.trim()) next.title = "Enter a title.";
        if (!body.trim()) next.body = "Enter the announcement text.";
        if (audience === "section" && !sectionId) next.audience_section = "Choose a section.";
        if (audience === "level" && !levelId) next.audience_level = "Choose a level.";
        setErrors(next);
        if (Object.keys(next).length) return;

        const input: AnnouncementInput = {
            title: title.trim(),
            body: body.trim(),
            audience_type: audience,
            audience_section: audience === "section" ? sectionId : null,
            audience_level: audience === "level" ? levelId : null,
            send_email: sendEmail,
        };
        const done = (saved: Announcement) => router.push(`/dashboard/announcements/manage/${saved.id}`);
        if (existing) {
            update.mutate({ id: existing.id, input }, { onSuccess: done });
        } else {
            create.mutate(input, { onSuccess: done });
        }
    };

    return (
        <form onSubmit={submit} className="space-y-5 max-w-2xl" noValidate>
            <div className="space-y-2">
                <Label htmlFor="title">Title</Label>
                <Input id="title" value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)} />
                {errors.title && <p className="text-xs text-red-600">{errors.title}</p>}
            </div>

            <div className="space-y-2">
                <Label htmlFor="body">Message</Label>
                <Textarea id="body" rows={7} value={body} onChange={(e) => setBody(e.target.value)} />
                {errors.body && <p className="text-xs text-red-600">{errors.body}</p>}
            </div>

            {isScheduled && (
                <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3 text-xs text-amber-800 dark:text-amber-300">
                    <p className="font-semibold mb-0.5">Audience settings locked</p>
                    <p>
                        The audience of a scheduled announcement cannot be modified directly. To change the recipient audience, cancel the schedule first from the announcement actions.
                    </p>
                </div>
            )}

            <div className="space-y-2">
                <Label htmlFor="audience">Send to</Label>
                <select
                    id="audience"
                    className={SELECT_CLASS}
                    value={audience}
                    disabled={isScheduled}
                    onChange={(e) => setAudience(e.target.value as AudienceType)}
                >
                    {audiences.map((key) => (
                        <option key={key} value={key}>
                            {AUDIENCE_LABELS[key]}
                        </option>
                    ))}
                </select>
            </div>

            {audience === "section" && (
                <div className="space-y-2">
                    <Label htmlFor="section">Section</Label>
                    <select
                        id="section"
                        className={SELECT_CLASS}
                        value={sectionId}
                        disabled={isScheduled}
                        onChange={(e) => setSectionId(e.target.value)}
                    >
                        <option value="">Select a section</option>
                        {(sections ?? []).map((s) => (
                            <option key={s.id} value={s.id}>
                                {s.level_name} - {s.name}
                            </option>
                        ))}
                    </select>
                    {errors.audience_section && <p className="text-xs text-red-600">{errors.audience_section}</p>}
                </div>
            )}

            {audience === "level" && (
                <div className="space-y-2">
                    <Label htmlFor="level">Level</Label>
                    <select
                        id="level"
                        className={SELECT_CLASS}
                        value={levelId}
                        disabled={isScheduled}
                        onChange={(e) => setLevelId(e.target.value)}
                    >
                        <option value="">Select a level</option>
                        {(levels ?? []).map((l) => (
                            <option key={l.id} value={l.id}>
                                {l.program_name} - {l.name}
                            </option>
                        ))}
                    </select>
                    {errors.audience_level && <p className="text-xs text-red-600">{errors.audience_level}</p>}
                </div>
            )}

            <label className="flex items-center gap-2 text-sm text-slate-700 dark:text-slate-300">
                <input type="checkbox" checked={sendEmail} onChange={(e) => setSendEmail(e.target.checked)} />
                Also send by email (recipients without an email address get the in-app notification only)
            </label>

            <div className="flex gap-3">
                <Button type="submit" disabled={pending}>
                    {pending ? "Saving..." : existing ? "Save changes" : "Save draft"}
                </Button>
                <Button type="button" variant="outline" disabled={pending} onClick={() => router.back()}>
                    Cancel
                </Button>
            </div>
        </form>
    );
}
