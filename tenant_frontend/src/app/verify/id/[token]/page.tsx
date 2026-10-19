"use client";

import { useParams } from "next/navigation";
import { usePublicIdCardVerification } from "@/hooks/useCertificates";
import { LoadingState } from "@/components/feedback/LoadingState";

export default function VerifyIdCardPage() {
    const params = useParams<{ token: string }>();
    const token = Array.isArray(params.token) ? params.token[0] : params.token;
    const { data, isLoading, isError } = usePublicIdCardVerification(token);

    return (
        <main className="mx-auto max-w-lg px-4 py-12 space-y-6">
            <h1 className="text-2xl font-bold text-slate-900">ID card verification</h1>
            {isLoading ? (
                <LoadingState className="py-16" />
            ) : isError || !data ? (
                <div role="alert" className="rounded-2xl border border-red-300 bg-red-50 p-6 text-red-800">
                    Verification is unavailable right now. Please try again later.
                </div>
            ) : data.status === "invalid" ? (
                <div role="alert" className="rounded-2xl border border-red-300 bg-red-50 p-6 text-red-800">
                    This code is not a valid ID card of this school.
                </div>
            ) : (
                <>
                    <div
                        role="status"
                        className={`rounded-2xl border p-5 font-semibold ${
                            data.valid ? "bg-emerald-50 border-emerald-300 text-emerald-800" : "bg-amber-50 border-amber-300 text-amber-800"
                        }`}
                    >
                        {data.valid ? "This ID card is valid" : "This ID card is no longer active"}
                    </div>
                    <dl className="rounded-2xl border border-slate-200 divide-y divide-slate-100 px-5 text-sm">
                        <div className="flex justify-between gap-4 py-3">
                            <dt className="text-slate-500">School</dt>
                            <dd className="font-medium text-slate-900 text-right">{data.school_name}</dd>
                        </div>
                        <div className="flex justify-between gap-4 py-3">
                            <dt className="text-slate-500">Card holder</dt>
                            <dd className="font-medium text-slate-900 text-right">{data.holder}</dd>
                        </div>
                        <div className="flex justify-between gap-4 py-3">
                            <dt className="text-slate-500">Type</dt>
                            <dd className="font-medium text-slate-900 text-right capitalize">{data.kind}</dd>
                        </div>
                    </dl>
                    <p className="text-xs text-slate-500">Only basic details are shown. Compare the name with the person presenting the card.</p>
                </>
            )}
        </main>
    );
}
