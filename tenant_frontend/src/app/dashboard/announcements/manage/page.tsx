"use client";

import { useState, useEffect } from "react";
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
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Pagination } from "@/components/ui/pagination";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import {
    Megaphone,
    Plus,
    Search,
    X,
    Calendar,
    Users,
    GraduationCap,
    Briefcase,
    Layers,
    Mail,
    Send,
    Eye,
    Clock,
    FileText,
} from "lucide-react";

const PAGE_SIZE = 15;

function getAudienceIcon(audience: AudienceType) {
    switch (audience) {
        case "all":
            return <Megaphone className="h-3.5 w-3.5 text-purple-600 dark:text-purple-400" />;
        case "all_students":
            return <GraduationCap className="h-3.5 w-3.5 text-sky-600 dark:text-sky-400" />;
        case "all_parents":
            return <Users className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />;
        case "all_staff":
            return <Briefcase className="h-3.5 w-3.5 text-amber-600 dark:text-amber-400" />;
        default:
            return <Layers className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />;
    }
}

function formatAnnouncementDate(iso: string | null) {
    if (!iso) return "—";
    try {
        const d = new Date(iso);
        return d.toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return iso;
    }
}

export default function ManageAnnouncementsPage() {
    const { can } = usePermissions();
    const [filters, setFilters] = useState<AnnouncementFilters>({
        page: 1,
        status: "",
        audience_type: "",
        search: "",
    });

    const [searchInput, setSearchInput] = useState("");
    const [debouncedSearch, setDebouncedSearch] = useState("");

    // Debounce search query by 300ms
    useEffect(() => {
        const handler = setTimeout(() => {
            setDebouncedSearch(searchInput.trim());
        }, 300);
        return () => clearTimeout(handler);
    }, [searchInput]);

    // Sync debounced search with query filters
    useEffect(() => {
        setFilters((prev) => ({ ...prev, page: 1, search: debouncedSearch }));
    }, [debouncedSearch]);

    const { data, isLoading, isError, refetch } = useAnnouncements(filters);

    if (!can("view_announcements")) {
        return <ErrorState message="You do not have permission to manage announcements." />;
    }

    const changeStatus = (status: string) => {
        setFilters((f) => ({
            ...f,
            page: 1,
            status: status === "all" ? "" : (status as AnnouncementStatus),
        }));
    };

    const changeAudience = (audience: string) => {
        setFilters((f) => ({
            ...f,
            page: 1,
            audience_type: audience === "all" ? "" : (audience as AudienceType),
        }));
    };

    const handlePageChange = (nextPage: number) => {
        setFilters((f) => ({ ...f, page: nextPage }));
    };

    const results = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    return (
        <div className="space-y-6 max-w-7xl mx-auto pb-16 animate-in fade-in duration-500">
            {/* 1. Senior Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Megaphone className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        <span>Institutional Notices &amp; Announcements</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Draft, schedule, publish, and broadcast multi-channel notices to staff, students, and parent communities
                    </p>
                </div>

                {can("manage_announcements") && (
                    <Button
                        asChild
                        size="sm"
                        className="gap-1.5 shrink-0"
                    >
                        <Link href="/dashboard/announcements/manage/new">
                            <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>New Announcement</span>
                        </Link>
                    </Button>
                )}
            </div>

            {/* 2. Control Bar: Search & Segmentation Filters */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-4 shadow-2xs space-y-3">
                <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
                    {/* Search Input with Clear Button */}
                    <div className="relative flex-1 max-w-md">
                        <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                        <Input
                            placeholder="Search notices by title or content keywords..."
                            value={searchInput}
                            onChange={(e) => setSearchInput(e.target.value)}
                            className="h-9 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                        />
                        {searchInput && (
                            <button
                                type="button"
                                onClick={() => setSearchInput("")}
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5 cursor-pointer"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        )}
                    </div>

                    {/* Audience Filter Select */}
                    <div className="w-full md:w-56 shrink-0">
                        <Select
                            value={filters.audience_type || "all"}
                            onValueChange={changeAudience}
                        >
                            <SelectTrigger className="h-9 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium">
                                <SelectValue placeholder="All Audiences" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">
                                    All Audiences
                                </SelectItem>
                                {(Object.keys(AUDIENCE_LABELS) as AudienceType[]).map((a) => (
                                    <SelectItem key={a} value={a} className="text-xs cursor-pointer">
                                        <div className="flex items-center gap-2">
                                            {getAudienceIcon(a)}
                                            <span>{AUDIENCE_LABELS[a]}</span>
                                        </div>
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                </div>

                {/* Status Segment Filter Pills */}
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs border-t border-slate-100 dark:border-slate-800/60 pt-2.5">
                    {[
                        { id: "all", label: "All Statuses" },
                        { id: "draft", label: "Drafts" },
                        { id: "scheduled", label: "Scheduled" },
                        { id: "published", label: "Published" },
                        { id: "archived", label: "Archived" },
                    ].map((tab) => {
                        const active = (filters.status || "all") === tab.id;
                        return (
                            <button
                                key={tab.id}
                                type="button"
                                onClick={() => changeStatus(tab.id)}
                                className={`px-3 py-1 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                                    active
                                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                        : "bg-slate-100/70 dark:bg-slate-800/60 text-slate-600 dark:text-slate-400 hover:bg-slate-200/60"
                                }`}
                            >
                                {tab.label}
                            </button>
                        );
                    })}
                </div>
            </div>

            {/* 3. Announcements List Desk */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load announcements. Please try again." onRetry={refetch} />
            ) : results.length === 0 ? (
                <EmptyState
                    title={
                        filters.search || filters.status || filters.audience_type
                            ? "No announcements matched your search filters"
                            : "No announcements created yet"
                    }
                    description="Create your first institutional notice to broadcast important updates, schedules, and alerts."
                    className="py-16 text-slate-500"
                />
            ) : (
                <div className="space-y-3">
                    <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800/80 overflow-hidden shadow-2xs">
                        {results.map((a) => {
                            const isScheduled = a.status === "scheduled";
                            const isPublished = a.status === "published";
                            const dateLabel = isScheduled
                                ? `Sends on ${formatAnnouncementDate(a.scheduled_at)}`
                                : isPublished
                                ? `Published on ${formatAnnouncementDate(a.published_at)}`
                                : `Created on ${formatAnnouncementDate(a.created_at)}`;

                            return (
                                <div
                                    key={a.id}
                                    className="p-5 hover:bg-slate-50/50 dark:hover:bg-slate-800/30 transition flex flex-col md:flex-row md:items-center justify-between gap-4"
                                >
                                    <div className="space-y-2 flex-1 min-w-0">
                                        {/* Status & Audience Chips */}
                                        <div className="flex items-center gap-2 flex-wrap">
                                            <AnnouncementStatusBadge status={a.status} />
                                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200/60 dark:border-slate-700/60">
                                                {getAudienceIcon(a.audience_type)}
                                                <span>{AUDIENCE_LABELS[a.audience_type]}</span>
                                            </span>
                                            {a.send_email && (
                                                <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
                                                    <Mail className="w-3 h-3" /> Email Dispatched
                                                </span>
                                            )}
                                        </div>

                                        {/* Title & Preview Link */}
                                        <Link
                                            href={`/dashboard/announcements/manage/${a.id}`}
                                            className="text-base font-bold text-slate-900 dark:text-white hover:text-sky-600 dark:hover:text-sky-400 transition-colors block truncate"
                                        >
                                            {a.title}
                                        </Link>

                                        {/* Meta Information Strip */}
                                        <div className="flex items-center gap-3 text-xs text-slate-400 font-medium flex-wrap">
                                            <span className="flex items-center gap-1">
                                                <Clock className="w-3.5 h-3.5" />
                                                <span>{dateLabel}</span>
                                            </span>
                                            {(isPublished || a.status === "archived") && (
                                                <>
                                                    <span>•</span>
                                                    <span className="flex items-center gap-1">
                                                        <Users className="w-3.5 h-3.5" />
                                                        <span>{a.recipient_count} recipient(s)</span>
                                                    </span>
                                                </>
                                            )}
                                        </div>
                                    </div>

                                    {/* Action Strip */}
                                    <div className="shrink-0 flex items-center gap-2 border-t md:border-t-0 pt-2 md:pt-0 border-slate-100 dark:border-slate-800">
                                        <Button
                                            asChild
                                            variant="ghost"
                                            size="sm"
                                            className="h-8 px-2.5 text-xs text-slate-600 dark:text-slate-400 hover:text-sky-600"
                                        >
                                            <Link href={`/dashboard/announcements/manage/${a.id}`}>
                                                <Eye className="w-3.5 h-3.5 mr-1" />
                                                View
                                            </Link>
                                        </Button>
                                        <AnnouncementActions announcement={a} onDeleted={refetch} />
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    {/* Pagination */}
                    {totalCount > PAGE_SIZE && (
                        <div className="pt-2">
                            <Pagination
                                page={filters.page || 1}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={handlePageChange}
                            />
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
