import { AnnouncementStatus, STATUS_LABELS } from "@/types/Announcements";

const STYLES: Record<AnnouncementStatus, string> = {
    draft: "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300",
    scheduled: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    published: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    archived: "bg-slate-200 text-slate-500 dark:bg-slate-800 dark:text-slate-500",
};

export function AnnouncementStatusBadge({ status }: { status: AnnouncementStatus }) {
    return (
        <span className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-bold ${STYLES[status]}`}>
            {STATUS_LABELS[status]}
        </span>
    );
}
