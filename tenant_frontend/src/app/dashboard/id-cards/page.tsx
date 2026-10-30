"use client";

import { useState } from "react";
import Link from "next/link";
import {
    CreditCard,
    Printer,
    Download,
    RotateCcw,
    ShieldAlert,
    User,
    GraduationCap,
    Briefcase,
    QrCode,
    Sparkles,
    CheckCircle2,
    ArrowLeft,
    LoaderCircle,
} from "lucide-react";
import {
    downloadPdf,
    certificateErrorMessage,
    useIdCard,
    useRotateIdCard,
} from "@/hooks/useCertificates";
import { usePermissions } from "@/providers/PermissionProvider";
import { PersonPicker } from "@/components/dashboard/certificates/PersonPicker";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
        <div className="space-y-7 max-w-4xl mx-auto pb-24 animate-in fade-in duration-500">
            <style>{PRINT_CSS}</style>

            {/* 1. Senior Executive Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800 print:hidden">
                <div>
                    <div className="flex items-center gap-2 mb-1">
                        <Link
                            href="/dashboard/certificates"
                            className="text-xs text-sky-600 dark:text-sky-400 hover:underline flex items-center gap-1 font-semibold"
                        >
                            <ArrowLeft className="w-3.5 h-3.5" /> Back to Certificates Registry
                        </Link>
                    </div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <CreditCard className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        <span>Institutional ID Card Studio</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Generate, preview, and print ISO/IEC 7810 CR80 identity cards with verification QR codes
                    </p>
                </div>
            </div>

            {/* 2. Mode Selector Pill & Person Picker Card */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-6 shadow-2xs space-y-5 print:hidden">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-100 dark:border-slate-800 pb-4">
                    <div>
                        <span className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider block">
                            Target Identity Type
                        </span>
                        <span className="text-xs text-slate-400">
                            Choose between student cohort passes and faculty staff badges
                        </span>
                    </div>

                    <div className="flex items-center p-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl border border-slate-200/60 dark:border-slate-700">
                        <button
                            type="button"
                            onClick={() => {
                                setKind("student");
                                setPersonId("");
                            }}
                            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
                                kind === "student"
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "text-slate-600 dark:text-slate-400"
                            }`}
                        >
                            <GraduationCap className="w-3.5 h-3.5" />
                            <span>Student Identity Card</span>
                        </button>
                        <button
                            type="button"
                            onClick={() => {
                                setKind("staff");
                                setPersonId("");
                            }}
                            className={`px-3.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer flex items-center gap-1.5 ${
                                kind === "staff"
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "text-slate-600 dark:text-slate-400"
                            }`}
                        >
                            <Briefcase className="w-3.5 h-3.5" />
                            <span>Staff Member Badge</span>
                        </button>
                    </div>
                </div>

                {/* Person Search & Picker */}
                <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                        <User className="h-3.5 w-3.5 text-slate-500" />
                        Select {kind === "student" ? "Active Enrolled Student" : "Active Staff Member"}
                    </label>
                    <PersonPicker
                        key={kind}
                        kind={kind}
                        value={personId}
                        onChange={setPersonId}
                        studentStatus={kind === "student" ? "active" : ""}
                        staffActive={kind === "staff" ? true : undefined}
                    />
                </div>
            </div>

            {/* Empty, Loading, and Error States */}
            {!personId && (
                <EmptyState
                    title={`Select a ${kind === "student" ? "student" : "staff member"} above to render their ID card`}
                    description="Preview live student details, photo, barcode, and anti-tamper verification QR codes."
                    className="py-16 text-slate-500 text-sm print:hidden"
                />
            )}

            {personId && isLoading && <LoadingState className="py-20 print:hidden" />}

            {personId && (isError || !data) && !isLoading && (
                <ErrorState
                    message={certificateErrorMessage(error, "Could not generate ID card data.")}
                    className="print:hidden"
                />
            )}

            {/* 3. Live Card Preview & Studio Actions */}
            {personId && data && !isLoading && (
                <div className="space-y-5 animate-in fade-in duration-300">
                    <div className="flex items-center justify-between print:hidden">
                        <div>
                            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <Sparkles className="w-4 h-4 text-sky-600" />
                                <span>CR80 Card Live Preview</span>
                            </h2>
                            <span className="text-[11px] text-slate-400">
                                85.6mm × 54.0mm Standard PVC Specification (300 DPI)
                            </span>
                        </div>
                    </div>

                    {/* Visual ID Card (CR80 Dimension: 85.6mm x 54mm) */}
                    <div className="flex justify-center p-6 bg-slate-100/70 dark:bg-slate-950/60 rounded-2xl border border-slate-200/80 dark:border-slate-800 print:bg-transparent print:border-none print:p-0">
                        <div
                            className="id-card-print relative w-[85.6mm] h-[54mm] overflow-hidden rounded-xl border border-slate-300/80 bg-white text-slate-900 shadow-xl"
                            style={{ printColorAdjust: "exact", WebkitPrintColorAdjust: "exact" }}
                        >
                            {/* Card Header Strip */}
                            <div
                                className="flex items-center gap-2 bg-gradient-to-r from-sky-800 to-sky-700 px-3 text-white"
                                style={{ height: "13mm" }}
                            >
                                {data.logo && (
                                    // eslint-disable-next-line @next/next/no-img-element
                                    <img src={data.logo} alt="" className="h-[9.5mm] w-[9.5mm] object-contain rounded" />
                                )}
                                <div className="min-w-0 flex-1">
                                    <span className="text-[9px] font-extrabold tracking-wide uppercase line-clamp-1 block">
                                        {data.school_name}
                                    </span>
                                    <span className="text-[7px] text-sky-200 tracking-wider uppercase block">
                                        Institutional Identity Card
                                    </span>
                                </div>
                            </div>

                            {/* Card Body */}
                            <div className="flex gap-2.5 p-2.5">
                                {/* Photo Box */}
                                <div className="flex h-[24mm] w-[20mm] items-center justify-center rounded border border-slate-300 bg-slate-50 text-[7px] text-slate-400 overflow-hidden shrink-0 shadow-2xs">
                                    {data.photo ? (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img src={data.photo} alt="" className="h-full w-full object-cover" />
                                    ) : (
                                        <User className="h-6 w-6 text-slate-300" />
                                    )}
                                </div>

                                {/* Text Details */}
                                <div className="min-w-0 flex-1 space-y-0.5">
                                    <p className="text-[11px] font-extrabold leading-tight text-slate-900 truncate">
                                        {data.holder_name}
                                    </p>
                                    <p className="text-[8px] font-mono font-bold text-sky-700">
                                        ID: {data.id_number}
                                    </p>
                                    {data.details.map((d) => (
                                        <p key={d.label} className="text-[7.5px] text-slate-600 truncate leading-tight">
                                            <span className="font-semibold text-slate-800">{d.label}:</span> {d.value}
                                        </p>
                                    ))}
                                </div>
                            </div>

                            {/* Bottom Identity Role Badge & QR Code */}
                            <div className="absolute bottom-2 left-3">
                                <span className="text-[7.5px] font-extrabold px-1.5 py-0.5 rounded bg-slate-100 text-slate-800 border border-slate-300 uppercase tracking-wider">
                                    {data.kind_label}
                                </span>
                            </div>

                            {/* eslint-disable-next-line @next/next/no-img-element */}
                            <img
                                src={data.qr_svg}
                                alt="Verification QR code"
                                className="absolute bottom-1 right-2 h-[15mm] w-[15mm]"
                            />
                        </div>
                    </div>

                    {/* Studio Action Buttons Bar */}
                    <div className="flex flex-wrap items-center gap-3 pt-2 print:hidden justify-center sm:justify-start">
                        <Button
                            onClick={() => window.print()}
                            className="h-9 px-4 gap-2 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                        >
                            <Printer className="h-4 w-4" />
                            <span>Print Card Directly</span>
                        </Button>

                        <Button
                            variant="outline"
                            disabled={busyPdf}
                            onClick={async () => {
                                setBusyPdf(true);
                                await downloadPdf(
                                    `/certificates/id-cards/${kind}/${personId}/pdf/`,
                                    `id-card-${data.id_number}.pdf`
                                );
                                setBusyPdf(false);
                            }}
                            className="h-9 px-4 gap-2 text-xs font-semibold border-slate-200 dark:border-slate-800 shadow-2xs"
                        >
                            {busyPdf ? (
                                <LoaderCircle className="h-4 w-4 animate-spin text-sky-600" />
                            ) : (
                                <Download className="h-4 w-4 text-slate-500" />
                            )}
                            <span>{busyPdf ? "Rendering PDF..." : "Export PDF Card"}</span>
                        </Button>

                        <Button
                            variant="outline"
                            disabled={rotate.isPending}
                            onClick={() => setConfirmRotate(true)}
                            className="h-9 px-3 gap-1.5 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200 dark:border-rose-900/60 shadow-2xs"
                        >
                            <ShieldAlert className="h-3.5 w-3.5" />
                            <span>Rotate Security QR</span>
                        </Button>
                    </div>
                </div>
            )}

            {/* QR Rotation Security Confirmation Dialog */}
            {confirmRotate && (
                <ConfirmationDialog
                    open
                    onOpenChange={(open) => !open && setConfirmRotate(false)}
                    title="Replace and Invalidate Security QR Code?"
                    description="Generating a new cryptographic QR code immediately invalidates all previously printed physical cards for this person. Use this immediately if a card is lost or stolen."
                    confirmLabel="Yes, Invalidate and Replace"
                    variant="destructive"
                    isLoading={rotate.isPending}
                    onConfirm={() =>
                        rotate.mutate({ kind, id: personId }, { onSettled: () => setConfirmRotate(false) })
                    }
                />
            )}
        </div>
    );
}
