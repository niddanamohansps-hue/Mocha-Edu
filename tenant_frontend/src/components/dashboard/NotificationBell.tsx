"use client";

import { Bell, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import {
    useMarkAllNotificationsRead,
    useMarkNotificationRead,
    useNotifications,
    useUnreadCount,
} from "@/hooks/useNotifications";
import { Notification } from "@/types/Notifications";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function formatUnreadBadge(count: number) {
    return count > 99 ? "99+" : String(count);
}

export function NotificationBell() {
    const router = useRouter();
    const { data: unreadData } = useUnreadCount();
    const { data: listData, isLoading, isError } = useNotifications(1);
    const { mutate: markRead } = useMarkNotificationRead();
    const { mutate: markAllRead, isPending: markingAll } = useMarkAllNotificationsRead();

    const unreadCount = unreadData?.unread_count ?? 0;
    const recent = listData?.results.slice(0, 8) ?? [];

    const handleClick = (notification: Notification) => {
        if (!notification.is_read) {
            markRead(notification.id);
        }
        if (notification.link) {
            router.push(notification.link);
        }
    };

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="relative h-10 w-10 rounded-xl">
                    <Bell className="h-5 w-5 text-slate-600 dark:text-slate-400" />
                    {unreadCount > 0 && (
                        <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 flex items-center justify-center rounded-full bg-red-500 text-white text-[10px] font-bold">
                            {formatUnreadBadge(unreadCount)}
                        </span>
                    )}
                </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-80 mt-2 rounded-2xl p-2 shadow-2xl border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                <div className="flex items-center justify-between px-3 py-2">
                    <p className="text-sm font-bold">Notifications</p>
                    {unreadCount > 0 && (
                        <button
                            onClick={() => markAllRead()}
                            disabled={markingAll}
                            className="text-xs font-semibold text-sky-600 hover:text-sky-700 disabled:opacity-50"
                        >
                            Mark all read
                        </button>
                    )}
                </div>

                <div className="max-h-96 overflow-y-auto">
                    {isLoading ? (
                        <div className="flex items-center justify-center py-8">
                            <LoaderCircle className="h-5 w-5 animate-spin text-indigo-600" />
                        </div>
                    ) : isError ? (
                        <p className="text-xs text-red-500 text-center py-6">Failed to load notifications.</p>
                    ) : recent.length === 0 ? (
                        <p className="text-xs text-slate-500 text-center py-6">No notifications yet.</p>
                    ) : (
                        recent.map((n) => (
                            <button
                                key={n.id}
                                onClick={() => handleClick(n)}
                                className={`w-full text-left px-3 py-3 rounded-xl transition-colors hover:bg-slate-50 dark:hover:bg-slate-800 ${
                                    !n.is_read ? "bg-sky-50/60 dark:bg-sky-500/5" : ""
                                }`}
                            >
                                <div className="flex items-start gap-2">
                                    {!n.is_read && <span className="mt-1.5 h-2 w-2 rounded-full bg-sky-500 flex-shrink-0" />}
                                    <div className="min-w-0 flex-1">
                                        <p className="text-sm font-semibold text-slate-800 dark:text-slate-200 truncate">
                                            {n.title}
                                        </p>
                                        {n.body && (
                                            <p className="text-xs text-slate-500 line-clamp-2 mt-0.5">{n.body}</p>
                                        )}
                                        <p className="text-[10px] text-slate-400 mt-1">
                                            {new Date(n.created_at).toLocaleString()}
                                        </p>
                                    </div>
                                </div>
                            </button>
                        ))
                    )}
                </div>

                <div className="pt-1 mt-1 border-t border-slate-100 dark:border-slate-800">
                    <button
                        onClick={() => router.push("/dashboard/notifications")}
                        className="w-full text-center text-xs font-semibold text-sky-600 hover:text-sky-700 py-2"
                    >
                        View all
                    </button>
                </div>
            </DropdownMenuContent>
        </DropdownMenu>
    );
}
