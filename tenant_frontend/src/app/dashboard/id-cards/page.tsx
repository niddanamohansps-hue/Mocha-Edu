"use client";

import { useState } from "react";
import { downloadPdf, certificateErrorMessage, useIdCard, useRotateIdCard } from "@/hooks/useCertificates";
import { usePermissions } from "@/providers/PermissionProvider";
import { PersonPicker } from "@/components/dashboard/certificates/PersonPicker";
import { Button } from "@/components/ui/button";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

type Kind = "student" | "staff";

// Only the card is printed; the rest of the dashboard is hidden by the print rules.
const PRINT_CSS = `
@media print {
  body * { visibility: hidden !important; }
  .id-card-print, .id-card-print * { visibility: visible !important; }
  .id-card-print { position: absolute; left: 0; top: 0; box-shadow: none !important; }
  @page { size: 85.6mm 54mm; margin: 0; }
}`;

export default function IdCardsPage() {
    const { can } = usePermissions();
    const [kind, setKind] = useState<Kind>("student");
    const [personId, setPersonId] = useState("");
    const [busyPdf, setBusyPdf] = useState(false);
    const { data, isLoading, isError, error } = useIdCard(kind, personId || undefined);
    const rotate = useRotateIdCard();
    const [confirmRotate, setConfirmRotate] = useState(false);

    if (!can("generate_id_cards")) {
        return <ErrorState message="You do not have permission to generate ID cards." />;
    }

    return (
        <div className="space-y-6 max-w-2xl">
            <style>{PRINT_CSS}</style>
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">ID cards</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Generate a printable ID card for an active student or staff member.
                </p>
            </div>

            <div className="flex rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden w-fit">
                {(["student", "staff"] as Kind[]).map((k) => (
                    <button
                        key={k}
                        type="button"
                        onClick={() => {
                            setKind(k);
                            setPersonId("");
                        }}
                        className={`px-4 py-1.5 text-xs font-semibold ${kind === k ? "bg-sky-600 text-white" : "text-slate-500"}`}
                    >
                        {k === "student" ? "Student" : "Staff"}
                    </button>
                ))}
            </div>

            <PersonPicker
                key={kind}
                kind={kind}
                value={personId}
                onChange={setPersonId}
                studentStatus={kind === "student" ? "active" : ""}
                staffActive={kind === "staff" ? true : undefined}
            />

            {!personId ? (
                <EmptyState title="Select a person to preview their card." className="py-10 text-slate-500 text-sm" />
            ) : isLoading ? (
                <LoadingState className="py-10" />
            ) : isError || !data ? (
                <ErrorState message={certificateErrorMessage(error, "Could not generate the card.")} />
            ) : (
                <div className="space-y-4">
                    <div
                        className="id-card-print relative w-[85.6mm] h-[54mm] overflow-hidden rounded-lg border border-slate-300 bg-white text-slate-900 shadow-md"
                        style={{ printColorAdjust: "exact", WebkitPrintColorAdjust: "exact" }}
                    >
                        <div className="flex items-center gap-2 bg-sky-700 px-2 text-white" style={{ height: "12mm" }}>
                            {data.logo && (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={data.logo} alt="" className="h-[10mm] w-[10mm] object-contain" />
                            )}
                            <span className="text-[9px] font-bold leading-tight line-clamp-2">{data.school_name}</span>
                        </div>
                        <div className="flex gap-2 p-2">
                            <div className="flex h-[25mm] w-[20mm] items-center justify-center border border-dashed border-slate-400 text-[7px] text-slate-500">
                                {data.photo ? (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={data.photo} alt="" className="h-full w-full object-cover" />
                                ) : (
                                    "No photo"
                                )}
                            </div>
                            <div className="min-w-0 flex-1">
                                <p className="text-[11px] font-bold leading-tight break-words">{data.holder_name}</p>
                                <p className="text-[8px] mt-1">ID: {data.id_number}</p>
                                {data.details.map((d) => (
                                    <p key={d.label} className="text-[8px]">
                                        {d.label}: {d.value}
                                    </p>
                                ))}
                            </div>
                        </div>
                        <span className="absolute bottom-1 left-2 text-[8px] font-bold uppercase">{data.kind_label}</span>
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={data.qr_svg} alt="Verification QR code" className="absolute bottom-1 right-1 h-[16mm] w-[16mm]" />
                    </div>

                    <div className="flex gap-3">
                        <Button onClick={() => window.print()}>Print card</Button>
                        <Button variant="outline" disabled={rotate.isPending} onClick={() => setConfirmRotate(true)}>
                            Replace QR code
                        </Button>
                        <Button
                            variant="outline"
                            disabled={busyPdf}
                            onClick={async () => {
                                setBusyPdf(true);
                                await downloadPdf(`/certificates/id-cards/${kind}/${personId}/pdf/`, `id-card-${data.id_number}.pdf`);
                                setBusyPdf(false);
                            }}
                        >
                            {busyPdf ? "Preparing..." : "Download PDF"}
                        </Button>
                    </div>
                </div>
            )}

            {confirmRotate && (
                <ConfirmationDialog
                    open
                    onOpenChange={(open) => !open && setConfirmRotate(false)}
                    title="Replace this card's QR code?"
                    description="The QR code on every printed copy of this card stops verifying immediately. Use this for a lost card, then print a new one."
                    confirmLabel="Replace QR code"
                    variant="default"
                    isLoading={rotate.isPending}
                    onConfirm={() =>
                        rotate.mutate({ kind, id: personId }, { onSettled: () => setConfirmRotate(false) })
                    }
                />
            )}
        </div>
    );
}
