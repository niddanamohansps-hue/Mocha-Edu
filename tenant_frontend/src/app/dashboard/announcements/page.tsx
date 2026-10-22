"use client";

import { useState } from "react";
import Link from "next/link";
import { useMyAnnouncements } from "@/hooks/useAnnouncements";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function MyAnnouncementsPage() {
    const [page, setPage] = useState(1);
    const { data, isLoading, isError, refetch } = useMyAnnouncements(page);
    const results = data?.results ?? [];

    return (
        <div className="space-y-6 max-w-3xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">My Announcements</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Announcements sent to you, newest first.
                </p>
            </div>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load announcements. Please try again." onRetry={refetch} />
            ) : results.length === 0 ? (
                <EmptyState title="No announcements yet." className="py-16 text-slate-500 text-sm" />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {results.map((item) => (
                        <Link
                            key={item.id}
                            href={`/dashboard/announcements/${item.id}`}
                            className="block p-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50"
                        >
                            <p className="font-semibold text-slate-800 dark:text-slate-200">{item.title}</p>
                            <p className="text-sm text-slate-500 mt-1 line-clamp-2 whitespace-pre-line">{item.body}</p>
                            <p className="text-xs text-slate-400 mt-2">
                                {new Date(item.published_at).toLocaleString()}
                            </p>
                        </Link>
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
