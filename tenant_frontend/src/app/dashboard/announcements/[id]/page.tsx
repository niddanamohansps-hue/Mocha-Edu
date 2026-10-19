"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useMyAnnouncement } from "@/hooks/useAnnouncements";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

// Target of the notification link (/dashboard/announcements/<id>). Uses the
// recipient-scoped endpoint, so it works for students, parents and staff alike
// and only ever shows an announcement the signed-in user actually received.
export default function AnnouncementDetailPage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const { data, isLoading, isError, error, refetch } = useMyAnnouncement(id);
    const notFound = (error as { response?: { status?: number } } | null)?.response?.status === 404;

    return (
        <div className="space-y-6 max-w-3xl">
            <Link
                href="/dashboard/announcements"
                className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
                <ArrowLeft className="h-4 w-4" /> All announcements
            </Link>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                notFound ? (
                    <ErrorState message="This announcement could not be found, or it was not sent to you." />
                ) : (
                    <ErrorState message="Failed to load the announcement. Please try again." onRetry={refetch} />
                )
            ) : data ? (
                <article className="rounded-2xl border border-slate-200 dark:border-slate-800 p-6 space-y-3">
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">{data.title}</h1>
                    <p className="text-xs text-slate-400">{new Date(data.published_at).toLocaleString()}</p>
                    <p className="text-slate-700 dark:text-slate-300 whitespace-pre-line break-words">{data.body}</p>
                </article>
            ) : null}
        </div>
    );
}
