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
import { Checkbox } from "@/components/ui/checkbox";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Megaphone,
    Users,
    GraduationCap,
    Briefcase,
    Layers,
    Save,
    LoaderCircle,
    Mail,
    AlertCircle,
} from "lucide-react";

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
        <form onSubmit={submit} className="space-y-6 max-w-3xl" noValidate>
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-6 shadow-2xs space-y-5">
                {/* Title */}
                <div className="space-y-2">
                    <Label htmlFor="title" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Notice Title <span className="text-rose-500">*</span>
                    </Label>
                    <Input
                        id="title"
                        value={title}
                        maxLength={200}
                        onChange={(e) => setTitle(e.target.value)}
                        placeholder="e.g. Annual Sports Meet 2026 Schedule & Guidelines"
                        className="h-10 text-xs border-slate-200 dark:border-slate-800 font-medium"
                    />
                    {errors.title && <p className="text-xs text-rose-600 font-medium">{errors.title}</p>}
                </div>

                {/* Message Body */}
                <div className="space-y-2">
                    <Label htmlFor="body" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Notice Content &amp; Instructions <span className="text-rose-500">*</span>
                    </Label>
                    <Textarea
                        id="body"
                        rows={7}
                        value={body}
                        onChange={(e) => setBody(e.target.value)}
                        placeholder="Type the full announcement message here. You can include dates, venues, guidelines, and point of contacts..."
                        className="text-xs border-slate-200 dark:border-slate-800 font-normal leading-relaxed"
                    />
                    {errors.body && <p className="text-xs text-rose-600 font-medium">{errors.body}</p>}
                </div>

                {/* Audience Warning if Scheduled */}
                {isScheduled && (
                    <div className="rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-800 p-3.5 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
                        <AlertCircle className="w-4 h-4 shrink-0 text-amber-600 mt-0.5" />
                        <div>
                            <p className="font-bold">Audience settings locked</p>
                            <p className="text-[11px] text-amber-700 dark:text-amber-400 mt-0.5">
                                The recipient audience of a scheduled announcement cannot be modified directly. To alter the target audience, cancel the schedule first.
                            </p>
                        </div>
                    </div>
                )}

                {/* Audience Selection */}
                <div className="space-y-2">
                    <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Target Audience <span className="text-rose-500">*</span>
                    </Label>
                    <Select
                        value={audience}
                        disabled={isScheduled}
                        onValueChange={(val) => setAudience(val as AudienceType)}
                    >
                        <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 font-medium">
                            <SelectValue placeholder="Select target audience" />
                        </SelectTrigger>
                        <SelectContent>
                            {audiences.map((key) => (
                                <SelectItem key={key} value={key} className="text-xs cursor-pointer">
                                    {AUDIENCE_LABELS[key]}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Specific Section Selector */}
                {audience === "section" && (
                    <div className="space-y-2 animate-in fade-in duration-200">
                        <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            Academic Section <span className="text-rose-500">*</span>
                        </Label>
                        <Select
                            value={sectionId}
                            disabled={isScheduled}
                            onValueChange={setSectionId}
                        >
                            <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 font-medium">
                                <SelectValue placeholder="Select a section..." />
                            </SelectTrigger>
                            <SelectContent>
                                {(sections ?? []).map((s) => (
                                    <SelectItem key={s.id} value={s.id} className="text-xs">
                                        {s.level_name} - {s.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {errors.audience_section && (
                            <p className="text-xs text-rose-600 font-medium">{errors.audience_section}</p>
                        )}
                    </div>
                )}

                {/* Specific Level Selector */}
                {audience === "level" && (
                    <div className="space-y-2 animate-in fade-in duration-200">
                        <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                            Grade Level <span className="text-rose-500">*</span>
                        </Label>
                        <Select
                            value={levelId}
                            disabled={isScheduled}
                            onValueChange={setLevelId}
                        >
                            <SelectTrigger className="h-10 text-xs border-slate-200 dark:border-slate-800 font-medium">
                                <SelectValue placeholder="Select a grade level..." />
                            </SelectTrigger>
                            <SelectContent>
                                {(levels ?? []).map((l) => (
                                    <SelectItem key={l.id} value={l.id} className="text-xs">
                                        {l.program_name} - {l.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                        {errors.audience_level && (
                            <p className="text-xs text-rose-600 font-medium">{errors.audience_level}</p>
                        )}
                    </div>
                )}

                {/* Email Dispatch Checkbox */}
                <div className="pt-2 border-t border-slate-100 dark:border-slate-800">
                    <label className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-300 cursor-pointer select-none">
                        <Checkbox
                            checked={sendEmail}
                            onCheckedChange={(val) => setSendEmail(Boolean(val))}
                            className="mt-0.5"
                        />
                        <div>
                            <span className="font-semibold text-slate-900 dark:text-white">
                                Also broadcast by email
                            </span>
                            <p className="text-[11px] text-slate-400 mt-0.5">
                                Dispatches an email notification to recipients with verified email addresses. Others receive in-app portal notifications.
                            </p>
                        </div>
                    </label>
                </div>
            </div>

            {/* Actions Bar */}
            <div className="flex items-center gap-3">
                <Button
                    type="submit"
                    disabled={pending}
                    className="gap-2"
                >
                    {pending ? (
                        <LoaderCircle className="h-4 w-4 animate-spin" />
                    ) : (
                        <Save className="h-4 w-4" />
                    )}
                    <span>{existing ? "Save Changes" : "Save Notice Draft"}</span>
                </Button>
                <Button
                    type="button"
                    variant="outline"
                    disabled={pending}
                    onClick={() => router.back()}
                >
                    Cancel
                </Button>
            </div>
        </form>
    );
}
