"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
    useMarkAllNotificationsRead,
    useMarkNotificationRead,
    useNotifications,
} from "@/hooks/useNotifications";
import { Notification } from "@/types/Notifications";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

type ReadFilter = "all" | "unread";

export default function NotificationsPage() {
    const router = useRouter();
    const [page, setPage] = useState(1);
    const [filter, setFilter] = useState<ReadFilter>("all");

    const { data, isLoading, isError, refetch } = useNotifications(page);
    const { mutate: markRead } = useMarkNotificationRead();
    const { mutate: markAllRead, isPending: markingAll } = useMarkAllNotificationsRead();

    const results = (data?.results ?? []).filter((n) => (filter === "unread" ? !n.is_read : true));
    const unreadOnPage = (data?.results ?? []).filter((n) => !n.is_read).length;

    const handleClick = (notification: Notification) => {
        if (!notification.is_read) {
            markRead(notification.id);
        }
        if (notification.link) {
            router.push(notification.link);
        }
    };

    return (
        <div className="space-y-6 max-w-3xl">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Notifications</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Everything sent to you, newest first.
                    </p>
                </div>
                <div className="flex items-center gap-3">
                    <div className="flex rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                        <button
                            onClick={() => setFilter("all")}
                            className={`px-3 py-1.5 text-xs font-semibold ${
                                filter === "all" ? "bg-sky-600 text-white" : "text-slate-500"
                            }`}
                        >
                            All
                        </button>
                        <button
                            onClick={() => setFilter("unread")}
                            className={`px-3 py-1.5 text-xs font-semibold ${
                                filter === "unread" ? "bg-sky-600 text-white" : "text-slate-500"
                            }`}
                        >
                            Unread
                        </button>
                    </div>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => markAllRead()}
                        disabled={markingAll || unreadOnPage === 0}
                    >
                        Mark all read
                    </Button>
                </div>
            </div>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load notifications. Please try again." onRetry={refetch} />
            ) : results.length === 0 ? (
                <EmptyState
                    title={filter === "unread" ? "No unread notifications." : "No notifications yet."}
                    className="py-16 text-slate-500 text-sm"
                />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {results.map((n) => (
                        <button
                            key={n.id}
                            onClick={() => handleClick(n)}
                            className={`w-full text-left p-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50 ${
                                !n.is_read ? "bg-sky-50/40 dark:bg-sky-500/5" : ""
                            }`}
                        >
                            <div className="flex items-start gap-3">
                                {!n.is_read && <span className="mt-1.5 h-2 w-2 rounded-full bg-sky-500 flex-shrink-0" />}
                                <div className="min-w-0 flex-1">
                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                        <p className="font-semibold text-slate-800 dark:text-slate-200">{n.title}</p>
                                        {n.category && (
                                            <span className="text-[10px] font-bold uppercase tracking-wide text-slate-400 flex-shrink-0">
                                                {n.category}
                                            </span>
                                        )}
                                    </div>
                                    {n.body && <p className="text-sm text-slate-500 mt-1">{n.body}</p>}
                                    <p className="text-xs text-slate-400 mt-2">
                                        {new Date(n.created_at).toLocaleString()}
                                    </p>
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}

            {data && (data.next || data.previous) && (
                <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
                    <Button variant="outline" size="sm" disabled={!data.previous} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                        Previous
                    </Button>
                    <Button variant="outline" size="sm" disabled={!data.next} onClick={() => setPage((p) => p + 1)}>
                        Next
                    </Button>
                </div>
            )}
        </div>
    );
}
