import { AnnouncementStatus, STATUS_LABELS } from "@/types/Announcements";
import { StatusBadge } from "@/components/ui/StatusBadge";

export function AnnouncementStatusBadge({ status }: { status: AnnouncementStatus }) {
    return (
        <StatusBadge
            status={status}
            label={STATUS_LABELS[status]}
        />
    );
}
