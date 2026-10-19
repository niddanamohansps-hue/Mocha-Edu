"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft } from "lucide-react";
import {
    downloadPdf,
    useCancelCertificate,
    useCertificate,
    useReissueCertificate,
} from "@/hooks/useCertificates";
import { usePermissions } from "@/providers/PermissionProvider";
import { CertificateStatusBadge } from "@/components/dashboard/certificates/CertificateStatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

type Mode = "cancel" | "reissue" | null;

function Row({ label, value }: { label: string; value: string | null | undefined }) {
    if (!value) return null;
    return (
        <div className="flex flex-col sm:flex-row sm:gap-4 py-2">
            <dt className="sm:w-48 text-xs font-semibold uppercase tracking-wide text-slate-400">{label}</dt>
            <dd className="text-sm text-slate-800 dark:text-slate-200 break-words">{value}</dd>
        </div>
    );
}

export default function CertificateDetailPage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const { can } = usePermissions();
    const { data, isLoading, isError, refetch } = useCertificate(id);
    const cancel = useCancelCertificate();
    const reissue = useReissueCertificate();
    const [mode, setMode] = useState<Mode>(null);
    const [reason, setReason] = useState("");
    const [error, setError] = useState("");
    const [busyPdf, setBusyPdf] = useState(false);

    if (!can("view_certificates")) {
        return <ErrorState message="You do not have permission to view certificates." />;
    }

    const close = () => {
        setMode(null);
        setReason("");
        setError("");
    };

    const submit = () => {
        if (!reason.trim()) {
            setError("Enter a reason.");
            return;
        }
        if (mode === "cancel") {
            cancel.mutate({ id, reason: reason.trim() }, { onSuccess: close });
        } else if (mode === "reissue") {
            reissue.mutate({ id, input: { reason: reason.trim() } }, { onSuccess: close });
        }
    };

    const canCancel = can("cancel_certificates");
    const pending = cancel.isPending || reissue.isPending;

    return (
        <div className="space-y-6 max-w-3xl">
            <Link
                href="/dashboard/certificates"
                className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
            >
                <ArrowLeft className="h-4 w-4" /> All certificates
            </Link>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError || !data ? (
                <ErrorState message="Failed to load the certificate." onRetry={refetch} />
            ) : (
                <>
                    <div className="space-y-3">
                        <div className="flex flex-wrap items-center gap-3">
                            <h1 className="text-2xl font-bold text-slate-900 dark:text-white break-words">{data.holder_name}</h1>
                            <CertificateStatusBadge status={data.status} />
                        </div>
                        <p className="text-sm text-slate-500">
                            {data.certificate_type_label} - {data.certificate_number}
                        </p>
                        <div className="flex flex-wrap gap-2">
                            <Button
                                size="sm"
                                disabled={busyPdf}
                                onClick={async () => {
                                    setBusyPdf(true);
                                    await downloadPdf(`/certificates/${id}/pdf/`, `${data.certificate_number}.pdf`);
                                    setBusyPdf(false);
                                }}
                            >
                                {busyPdf ? "Preparing..." : "Download PDF"}
                            </Button>
                            {canCancel && data.status === "issued" && (
                                <Button variant="outline" size="sm" onClick={() => setMode("cancel")}>
                                    Cancel certificate
                                </Button>
                            )}
                            {canCancel && data.status !== "superseded" && !data.superseded_by_number && (
                                <Button variant="outline" size="sm" onClick={() => setMode("reissue")}>
                                    Reissue
                                </Button>
                            )}
                        </div>
                        {data.status !== "issued" && (
                            <p role="status" className="text-sm text-amber-700 dark:text-amber-400">
                                {data.status === "cancelled"
                                    ? `Cancelled: ${data.cancellation_reason}`
                                    : `Replaced by ${data.superseded_by_number}.`}
                                {data.status === "cancelled" && data.superseded_by_number ? ` Replaced by ${data.superseded_by_number}.` : ""}
                            </p>
                        )}
                    </div>

                    <dl className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 px-5">
                        <Row label="Issue date" value={new Date(data.issue_date).toLocaleDateString()} />
                        <Row label="Academic year" value={data.academic_year} />
                        <Row label="Leaving date" value={data.leaving_date ? new Date(data.leaving_date).toLocaleDateString() : null} />
                        <Row label="Employed from" value={data.period_start ? new Date(data.period_start).toLocaleDateString() : null} />
                        <Row label="Employed until" value={data.period_end ? new Date(data.period_end).toLocaleDateString() : null} />
                        <Row label="Reason" value={data.reason} />
                        <Row label="Conduct" value={data.conduct} />
                        <Row label="Replaces" value={data.supersedes_number} />
                        <Row label="Reissue reason" value={data.reissue_reason} />
                        <Row label="Internal notes" value={data.internal_notes} />
                    </dl>
                </>
            )}

            <Dialog open={mode !== null} onOpenChange={(open) => !open && close()}>
                <DialogContent>
                    <DialogHeader>
                        <DialogTitle>{mode === "cancel" ? "Cancel certificate" : "Reissue certificate"}</DialogTitle>
                        <DialogDescription>
                            {mode === "cancel"
                                ? "The certificate stays on record, is marked cancelled, and public verification will show it as no longer valid."
                                : "A new certificate with a new number replaces this one. The old one stays on record and links to the new one."}
                        </DialogDescription>
                    </DialogHeader>
                    <div className="space-y-2">
                        <Label htmlFor="reason">Reason</Label>
                        <Input id="reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
                        {error && <p className="text-xs text-red-600">{error}</p>}
                    </div>
                    <DialogFooter>
                        <Button variant="outline" onClick={close} disabled={pending}>
                            Close
                        </Button>
                        <Button onClick={submit} disabled={pending}>
                            {pending ? "Saving..." : mode === "cancel" ? "Cancel certificate" : "Reissue"}
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </div>
    );
}
