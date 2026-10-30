"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
    Bell,
    CheckCheck,
    CreditCard,
    GraduationCap,
    Megaphone,
    Package,
    UserX,
    Clock,
    ArrowUpRight,
    CheckCircle2,
    Filter,
    Inbox,
    MailCheck,
    Sparkles,
} from "lucide-react";
import { toast } from "sonner";
import {
    useMarkAllNotificationsRead,
    useMarkNotificationRead,
    useNotifications,
} from "@/hooks/useNotifications";
import { Notification } from "@/types/Notifications";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

type ReadFilter = "all" | "unread";

function getCategoryIcon(category: string) {
    const cat = (category || "").toLowerCase();
    if (cat.includes("fee") || cat.includes("payment")) return CreditCard;
    if (cat.includes("absent") || cat.includes("attendance")) return UserX;
    if (cat.includes("exam") || cat.includes("grade") || cat.includes("academic")) return GraduationCap;
    if (cat.includes("announce")) return Megaphone;
    if (cat.includes("stock") || cat.includes("inventory")) return Package;
    return Bell;
}

function getCategoryStyle(category: string) {
    const cat = (category || "").toLowerCase();
    if (cat.includes("fee") || cat.includes("payment")) {
        return "bg-emerald-50 text-emerald-700 border-emerald-300 dark:bg-emerald-950/60 dark:text-emerald-300";
    }
    if (cat.includes("absent") || cat.includes("attendance")) {
        return "bg-rose-50 text-rose-700 border-rose-300 dark:bg-rose-950/60 dark:text-rose-300";
    }
    if (cat.includes("exam") || cat.includes("grade")) {
        return "bg-indigo-50 text-indigo-700 border-indigo-300 dark:bg-indigo-950/60 dark:text-indigo-300";
    }
    if (cat.includes("announce")) {
        return "bg-amber-50 text-amber-700 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300";
    }
    return "bg-sky-50 text-sky-700 border-sky-300 dark:bg-sky-950/60 dark:text-sky-300";
}

function formatRelativeTime(iso: string) {
    try {
        const diffSeconds = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
        if (diffSeconds < 60) return "Just now";
        if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
        if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`;
        if (diffSeconds < 86400 * 7) return `${Math.floor(diffSeconds / 86400)}d ago`;
        return new Date(iso).toLocaleDateString("en-IN", {
            day: "numeric",
            month: "short",
            year: "numeric",
        });
    } catch {
        return iso;
    }
}

export default function NotificationsPage() {
    const router = useRouter();
    const [page, setPage] = useState(1);
    const [filter, setFilter] = useState<ReadFilter>("all");

    const { data, isLoading, isError, refetch } = useNotifications(page);
    const { mutate: markRead } = useMarkNotificationRead();
    const { mutate: markAllRead, isPending: markingAll } = useMarkAllNotificationsRead();

    const allResults = data?.results ?? [];
    const results = allResults.filter((n) => (filter === "unread" ? !n.is_read : true));
    const unreadCount = allResults.filter((n) => !n.is_read).length;

    const handleClick = (notification: Notification) => {
        if (!notification.is_read) {
            markRead(notification.id);
        }
        if (notification.link) {
            router.push(notification.link);
        }
    };

    const handleMarkAll = () => {
        markAllRead(undefined, {
            onSuccess: () => {
                toast.success("All notifications marked as read.");
            },
        });
    };

    return (
        <div className="space-y-6 max-w-4xl mx-auto">
            {/* Page Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-200/80 dark:border-slate-800 pb-5">
                <div>
                    <div className="flex items-center gap-2">
                        <div className="p-2 rounded-xl bg-sky-600 text-white shadow-sm">
                            <Inbox className="h-5 w-5" />
                        </div>
                        <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                            Activity Inbox
                        </h1>
                        {unreadCount > 0 ? (
                            <Badge className="bg-sky-600 text-white hover:bg-sky-600 text-xs px-2 py-0.5">
                                {unreadCount} New
                            </Badge>
                        ) : (
                            <Badge variant="outline" className="text-slate-500 text-xs">
                                Caught Up
                            </Badge>
                        )}
                    </div>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        System dispatches, attendance triggers, payment confirmations, and institutional alerts.
                    </p>
                </div>

                <div className="flex items-center gap-2.5">
                    {/* Filter Segmented Control */}
                    <div className="flex rounded-xl bg-slate-100 dark:bg-slate-800 p-1 border border-slate-200/80 dark:border-slate-700">
                        <button
                            type="button"
                            onClick={() => setFilter("all")}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                                filter === "all"
                                    ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs"
                                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                            }`}
                        >
                            All ({allResults.length})
                        </button>
                        <button
                            type="button"
                            onClick={() => setFilter("unread")}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                                filter === "unread"
                                    ? "bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-2xs"
                                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                            }`}
                        >
                            Unread ({unreadCount})
                        </button>
                    </div>

                    <Button
                        variant="outline"
                        size="sm"
                        onClick={handleMarkAll}
                        disabled={markingAll || unreadCount === 0}
                        className="h-9 text-xs font-medium bg-white dark:bg-slate-800 shadow-sm"
                    >
                        <CheckCheck className="h-3.5 w-3.5 mr-1.5 text-slate-500" />
                        Mark All Read
                    </Button>
                </div>
            </div>

            {/* Content Feed */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Could not load your activity notifications." onRetry={refetch} />
            ) : results.length === 0 ? (
                <div className="p-12 rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 text-center space-y-3">
                    <div className="w-12 h-12 rounded-2xl bg-sky-50 dark:bg-sky-950/50 text-sky-600 flex items-center justify-center mx-auto">
                        <MailCheck className="h-6 w-6" />
                    </div>
                    <div>
                        <h3 className="text-base font-bold text-slate-900 dark:text-white">
                            {filter === "unread" ? "You're all caught up!" : "No notifications on record"}
                        </h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 max-w-sm mx-auto">
                            {filter === "unread"
                                ? "There are no unread notifications waiting for your review."
                                : "System dispatches and activity alerts for your profile will arrive here."}
                        </p>
                    </div>
                    {filter === "unread" && (
                        <div className="pt-2">
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => setFilter("all")}
                                className="text-xs"
                            >
                                View All Notifications
                            </Button>
                        </div>
                    )}
                </div>
            ) : (
                <div className="rounded-2xl border border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 divide-y divide-slate-100 dark:divide-slate-800 shadow-sm overflow-hidden">
                    {results.map((n) => {
                        const Icon = getCategoryIcon(n.category);
                        const categoryStyle = getCategoryStyle(n.category);

                        return (
                            <div
                                key={n.id}
                                onClick={() => handleClick(n)}
                                className={`group p-4 sm:p-5 flex items-start gap-4 transition cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800/40 ${
                                    !n.is_read
                                        ? "bg-sky-50/40 dark:bg-sky-950/20"
                                        : "bg-white dark:bg-slate-900"
                                }`}
                            >
                                {/* Category Icon with unread beacon */}
                                <div className="relative shrink-0 mt-0.5">
                                    <div className="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800 border border-slate-200/60 dark:border-slate-700 text-slate-600 dark:text-slate-300 group-hover:scale-105 transition-transform">
                                        <Icon className="h-4 w-4" />
                                    </div>
                                    {!n.is_read && (
                                        <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                                            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-sky-400 opacity-75" />
                                            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-sky-500" />
                                        </span>
                                    )}
                                </div>

                                {/* Body Information */}
                                <div className="min-w-0 flex-1 space-y-1">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <div className="flex items-center gap-2 min-w-0">
                                            <h3 className={`text-sm font-semibold truncate ${
                                                !n.is_read
                                                    ? "text-slate-900 dark:text-white"
                                                    : "text-slate-700 dark:text-slate-300"
                                            }`}>
                                                {n.title}
                                            </h3>
                                            {n.category && (
                                                <Badge
                                                    variant="outline"
                                                    className={`text-[10px] uppercase font-bold tracking-wider px-1.5 py-0 ${categoryStyle}`}
                                                >
                                                    {n.category}
                                                </Badge>
                                            )}
                                        </div>

                                        <span className="text-[11px] text-slate-400 font-mono flex items-center gap-1 shrink-0">
                                            <Clock className="h-3 w-3" />
                                            {formatRelativeTime(n.created_at)}
                                        </span>
                                    </div>

                                    {n.body && (
                                        <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                                            {n.body}
                                        </p>
                                    )}

                                    {n.link && (
                                        <div className="pt-1 flex items-center gap-1 text-[11px] font-medium text-sky-600 dark:text-sky-400 group-hover:underline">
                                            <span>View details</span>
                                            <ArrowUpRight className="h-3 w-3" />
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Pagination Controls */}
            {data && (data.next || data.previous) && (
                <div className="flex items-center justify-between pt-2">
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={!data.previous}
                        onClick={() => setPage((p) => Math.max(1, p - 1))}
                        className="text-xs h-8 bg-white dark:bg-slate-800"
                    >
                        Previous Page
                    </Button>
                    <span className="text-xs text-slate-500 font-medium">Page {page}</span>
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={!data.next}
                        onClick={() => setPage((p) => p + 1)}
                        className="text-xs h-8 bg-white dark:bg-slate-800"
                    >
                        Next Page
                    </Button>
                </div>
            )}
        </div>
    );
}
