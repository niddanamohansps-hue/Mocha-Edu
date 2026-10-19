"use client";

import { useParams } from "next/navigation";
import { useAnnouncement } from "@/hooks/useAnnouncements";
import { usePermissions } from "@/providers/PermissionProvider";
import { AnnouncementForm } from "@/components/dashboard/announcements/AnnouncementForm";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function EditAnnouncementPage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const { can } = usePermissions();
    const { data, isLoading, isError, refetch } = useAnnouncement(id);

    if (!can("manage_announcements")) {
        return <ErrorState message="You do not have permission to edit announcements." />;
    }

    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Edit announcement</h1>
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError || !data ? (
                <ErrorState message="Failed to load the announcement." onRetry={refetch} />
            ) : data.status !== "draft" && data.status !== "scheduled" ? (
                <ErrorState message="Only a draft or scheduled announcement can be edited." />
            ) : (
                <AnnouncementForm existing={data} />
            )}
        </div>
    );
}
