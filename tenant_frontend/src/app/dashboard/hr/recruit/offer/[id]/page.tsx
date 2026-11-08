"use client";

import { use } from "react";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import Unauthorized from "@/components/Unauthorized";
import { useOfferLetter } from "@/hooks/useRecruitment";
import { usePermissions } from "@/providers/PermissionProvider";

export default function OfferLetterPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);
    const { can, isOwner } = usePermissions();
    const { data, isLoading, isError } = useOfferLetter(id);

    if (!isOwner && !can("view_recruitment")) return <Unauthorized />;
    if (isLoading) return <LoadingState />;
    if (isError || !data) {
        return <EmptyState title="No letter yet" description="Save the offer terms first, then open the letter again." />;
    }
    return (
        <div className="mx-auto max-w-3xl space-y-4">
            <style>{`@media print { @page { size: A4 portrait; margin: 20mm; } .no-print { display: none !important; } body { background: white !important; } }`}</style>
            <div className="no-print flex justify-end">
                <Button onClick={() => window.print()}><Printer className="mr-2 h-4 w-4" />Print</Button>
            </div>
            <article className="whitespace-pre-wrap rounded-xl border border-slate-200 bg-white p-10 text-sm leading-7 text-slate-900 print:border-0 print:p-0">
                {data.body}
                <div className="mt-12 grid grid-cols-2 gap-10 text-xs">
                    <div><div className="mb-2 h-10 border-b border-slate-400" />Candidate: accepted. Signature and date</div>
                    <div><div className="mb-2 h-10 border-b border-slate-400" />Principal. Signature and seal</div>
                </div>
            </article>
        </div>
    );
}
