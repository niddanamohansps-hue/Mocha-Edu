"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import { useAnnouncement, useAnnouncementRecipients } from "@/hooks/useAnnouncements";
import { usePermissions } from "@/providers/PermissionProvider";
import { AUDIENCE_LABELS } from "@/types/Announcements";
import { AnnouncementActions } from "@/components/dashboard/announcements/AnnouncementActions";
import { AnnouncementStatusBadge } from "@/components/dashboard/announcements/AnnouncementStatusBadge";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function ManageAnnouncementDetailPage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const router = useRouter();
    const { can } = usePermissions();
    const [recipientPage, setRecipientPage] = useState(1);
    const { data, isLoading, isError, refetch } = useAnnouncement(id);
    const hasRecipients = data?.status === "published" || data?.status === "archived";
    const recipients = useAnnouncementRecipients(id, recipientPage, hasRecipients && can("manage_announcements"));

    if (!can("view_announcements")) {
        return <ErrorState message="You do not have permission to view announcements." />;
    }

    return (
        <div className="space-y-6 max-w-3xl">
            <Link
                href="/dashboard/announcements/manage"
                className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
                <ArrowLeft className="h-4 w-4" /> All announcements
            </Link>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError || !data ? (
                <ErrorState message="Failed to load the announcement." onRetry={refetch} />
            ) : (
                <>
                    <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-3">
                            <h1 className="text-2xl font-bold text-slate-900 dark:text-white break-words">{data.title}</h1>
                            <AnnouncementStatusBadge status={data.status} />
                        </div>
                        <p className="text-xs text-slate-500">
                            To {AUDIENCE_LABELS[data.audience_type].toLowerCase()}
                            {data.send_email ? " - also by email" : ""}
                            {data.scheduled_at && data.status === "scheduled"
                                ? ` - sends ${new Date(data.scheduled_at).toLocaleString()}`
                                : ""}
                            {data.published_at ? ` - published ${new Date(data.published_at).toLocaleString()}` : ""}
                        </p>
                        <AnnouncementActions announcement={data} onDeleted={() => router.push("/dashboard/announcements/manage")} />
                    </div>

                    <article className="rounded-2xl border border-slate-200 dark:border-slate-800 p-6">
                        <p className="text-slate-700 dark:text-slate-300 whitespace-pre-line break-words">{data.body}</p>
                    </article>

                    {hasRecipients && can("manage_announcements") && (
                        <section className="space-y-3">
                            <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                                Recipients ({data.recipient_count})
                            </h2>
                            {recipients.isLoading ? (
                                <LoadingState className="py-10" />
                            ) : recipients.isError ? (
                                <ErrorState message="Failed to load recipients." onRetry={recipients.refetch} />
                            ) : (recipients.data?.results.length ?? 0) === 0 ? (
                                <EmptyState title="No recipients." className="py-8 text-slate-500 text-sm" />
                            ) : (
                                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                                    {recipients.data?.results.map((r) => (
                                        <div key={r.user_id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                                            <span className="font-mono text-xs text-slate-500 break-all">{r.user_id}</span>
                                            <span className="text-xs text-slate-400 flex-shrink-0">
                                                {r.email_sent ? "Emailed" : "In-app only"}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                            {recipients.data && (recipients.data.next || recipients.data.previous) && (
                                <div className="flex items-center justify-between">
                                    <Button variant="outline" size="sm" disabled={!recipients.data.previous} onClick={() => setRecipientPage((p) => Math.max(1, p - 1))}>
                                        Previous
                                    </Button>
                                    <Button variant="outline" size="sm" disabled={!recipients.data.next} onClick={() => setRecipientPage((p) => p + 1)}>
                                        Next
                                    </Button>
                                </div>
                            )}
                        </section>
                    )}
                </>
            )}
        </div>
    );
}
