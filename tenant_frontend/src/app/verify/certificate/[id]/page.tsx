"use client";

import { useParams } from "next/navigation";
import { usePublicCertificateVerification } from "@/hooks/useCertificates";
import { LoadingState } from "@/components/feedback/LoadingState";

const HEADLINE: Record<string, { text: string; style: string }> = {
    issued: { text: "This certificate is valid", style: "bg-emerald-50 border-emerald-300 text-emerald-800" },
    cancelled: { text: "This certificate has been cancelled", style: "bg-red-50 border-red-300 text-red-800" },
    superseded: { text: "This certificate has been replaced", style: "bg-amber-50 border-amber-300 text-amber-800" },
    integrity_failed: { text: "This record could not be verified", style: "bg-red-50 border-red-300 text-red-800" },
};

export default function VerifyCertificatePage() {
    const params = useParams<{ id: string }>();
    const id = Array.isArray(params.id) ? params.id[0] : params.id;
    const { data, isLoading, isError, error } = usePublicCertificateVerification(id);
    const notFound = (error as { response?: { status?: number } } | null)?.response?.status === 404;

    return (
        <main className="mx-auto max-w-lg px-4 py-12 space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">Certificate verification</h1>
            {isLoading ? (
                <LoadingState className="py-16" />
            ) : isError || !data ? (
                <div role="alert" className="rounded-2xl border border-red-300 bg-red-50 p-6 text-red-800">
                    {notFound
                        ? "No certificate matches this code. Check the code printed on the document."
                        : "Verification is unavailable right now. Please try again later."}
                </div>
            ) : (
                <>
                    <div role="status" className={`rounded-2xl border p-5 font-semibold ${(HEADLINE[data.status] ?? HEADLINE.integrity_failed).style}`}>
                        {(HEADLINE[data.status] ?? HEADLINE.integrity_failed).text}
                    </div>
                    <dl className="rounded-2xl border border-slate-200 divide-y divide-slate-100 px-5 text-sm">
                        <Item label="Type" value={data.certificate_type_label} />
                        <Item label="Certificate number" value={data.certificate_number} />
                        <Item label="Issued by" value={data.school_name} />
                        <Item label="Issued to" value={data.holder_name} />
                        <Item label="Date of issue" value={new Date(data.issue_date).toLocaleDateString()} />
                        <Item label="Replaced by" value={data.replaced_by_number} />
                    </dl>
                    <p className="text-xs text-slate-500">
                        Compare these details with the printed certificate. Only basic details are shown here.
                    </p>
                </>
            )}
        </main>
    );
}

function Item({ label, value }: { label: string; value: string | null }) {
    if (!value) return null;
    return (
        <div className="flex flex-wrap justify-between gap-4 py-3">
            <dt className="text-slate-500">{label}</dt>
            <dd className="font-medium text-slate-900 text-right break-words">{value}</dd>
        </div>
    );
}
