"use client";

import { useState } from "react";
import Link from "next/link";
import { useAnnouncements } from "@/hooks/useAnnouncements";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    Announcement,
    AnnouncementFilters,
    AnnouncementStatus,
    AudienceType,
    AUDIENCE_LABELS,
    STATUS_LABELS,
} from "@/types/Announcements";
import { AnnouncementActions } from "@/components/dashboard/announcements/AnnouncementActions";
import { AnnouncementStatusBadge } from "@/components/dashboard/announcements/AnnouncementStatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

const SELECT_CLASS =
    "rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm";

function whenLabel(a: Announcement) {
    if (a.status === "scheduled" && a.scheduled_at) return `Sends ${new Date(a.scheduled_at).toLocaleString()}`;
    if (a.published_at) return `Published ${new Date(a.published_at).toLocaleString()}`;
    return `Created ${new Date(a.created_at).toLocaleString()}`;
}

export default function ManageAnnouncementsPage() {
    const { can } = usePermissions();
    const [filters, setFilters] = useState<AnnouncementFilters>({ page: 1, status: "", audience_type: "", search: "" });
    const [searchText, setSearchText] = useState("");
    const { data, isLoading, isError, refetch } = useAnnouncements(filters);

    if (!can("view_announcements")) {
        return <ErrorState message="You do not have permission to manage announcements." />;
    }

    const change = (patch: Partial<AnnouncementFilters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));
    const results = data?.results ?? [];

    return (
        <div className="space-y-6">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Manage Announcements</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Draft, schedule and publish announcements to staff, students and parents.
                    </p>
                </div>
                {can("manage_announcements") && (
                    <Button asChild>
                        <Link href="/dashboard/announcements/manage/new">New announcement</Link>
                    </Button>
                )}
            </div>

            <form
                className="flex flex-wrap gap-3"
                onSubmit={(e) => {
                    e.preventDefault();
                    change({ search: searchText.trim() });
                }}
            >
                <Input
                    className="w-full sm:w-64"
                    placeholder="Search title or text"
                    value={searchText}
                    onChange={(e) => setSearchText(e.target.value)}
                />
                <select
                    aria-label="Status"
                    className={SELECT_CLASS}
                    value={filters.status}
                    onChange={(e) => change({ status: e.target.value as AnnouncementStatus | "" })}
                >
                    <option value="">All statuses</option>
                    {(Object.keys(STATUS_LABELS) as AnnouncementStatus[]).map((s) => (
                        <option key={s} value={s}>
                            {STATUS_LABELS[s]}
                        </option>
                    ))}
                </select>
                <select
                    aria-label="Audience"
                    className={SELECT_CLASS}
                    value={filters.audience_type}
                    onChange={(e) => change({ audience_type: e.target.value as AudienceType | "" })}
                >
                    <option value="">All audiences</option>
                    {(Object.keys(AUDIENCE_LABELS) as AudienceType[]).map((a) => (
                        <option key={a} value={a}>
                            {AUDIENCE_LABELS[a]}
                        </option>
                    ))}
                </select>
                <Button type="submit" variant="outline">
                    Search
                </Button>
            </form>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load announcements. Please try again." onRetry={refetch} />
            ) : results.length === 0 ? (
                <EmptyState
                    title={filters.search || filters.status || filters.audience_type ? "No announcements match." : "No announcements yet."}
                    className="py-16 text-slate-500 text-sm"
                />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {results.map((a) => (
                        <div key={a.id} className="p-4 space-y-3">
                            <div className="flex flex-wrap items-center gap-2">
                                <Link
                                    href={`/dashboard/announcements/manage/${a.id}`}
                                    className="font-semibold text-slate-800 dark:text-slate-200 hover:underline break-words"
                                >
                                    {a.title}
                                </Link>
                                <AnnouncementStatusBadge status={a.status} />
                            </div>
                            <p className="text-xs text-slate-500">
                                To {AUDIENCE_LABELS[a.audience_type].toLowerCase()}
                                {a.status === "published" || a.status === "archived" ? ` - ${a.recipient_count} recipient(s)` : ""}
                                {" - "}
                                {whenLabel(a)}
                            </p>
                            <AnnouncementActions announcement={a} />
                        </div>
                    ))}
                </div>
            )}

            {data && (data.next || data.previous) && (
                <div className="flex items-center justify-between pt-2">
                    <Button variant="outline" size="sm" disabled={!data.previous} onClick={() => setFilters((f) => ({ ...f, page: Math.max(1, f.page - 1) }))}>
                        Previous
                    </Button>
                    <Button variant="outline" size="sm" disabled={!data.next} onClick={() => setFilters((f) => ({ ...f, page: f.page + 1 }))}>
                        Next
                    </Button>
                </div>
            )}
        </div>
    );
}
