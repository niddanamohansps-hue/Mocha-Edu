import { CertificateStatus } from "@/types/Certificates";
import { StatusBadge } from "@/components/ui/StatusBadge";

const LABELS: Record<CertificateStatus, string> = {
    issued: "Issued",
    cancelled: "Cancelled",
    superseded: "Superseded",
};

export function CertificateStatusBadge({ status }: { status: CertificateStatus }) {
    return (
        <StatusBadge
            status={status}
            label={LABELS[status]}
            variant={status === "issued" ? "success" : status === "cancelled" ? "danger" : "neutral"}
        />
    );
}
