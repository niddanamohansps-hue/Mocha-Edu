"use client";

import { usePermissions } from "@/providers/PermissionProvider";
import { AnnouncementForm } from "@/components/dashboard/announcements/AnnouncementForm";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function NewAnnouncementPage() {
    const { can } = usePermissions();
    if (!can("manage_announcements")) {
        return <ErrorState message="You do not have permission to create announcements." />;
    }
    return (
        <div className="space-y-6">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white">New announcement</h1>
            <AnnouncementForm />
        </div>
    );
}
