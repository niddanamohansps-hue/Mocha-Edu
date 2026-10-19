import { CertificateStatus } from "@/types/Certificates";

const STYLES: Record<CertificateStatus, string> = {
    issued: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    cancelled: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
    superseded: "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

const LABELS: Record<CertificateStatus, string> = {
    issued: "Issued",
    cancelled: "Cancelled",
    superseded: "Superseded",
};

export function CertificateStatusBadge({ status }: { status: CertificateStatus }) {
    return (
        <span className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-bold ${STYLES[status]}`}>
            {LABELS[status]}
        </span>
    );
}
