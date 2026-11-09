"use client";

import React, { useRef } from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useInstitutionProfile } from "@/hooks/useProfile";
import { useCertificateSettings } from "@/hooks/useCertificates";
import { Certificate } from "@/types/Certificates";
import { CertificateStatusBadge } from "./CertificateStatusBadge";
import {
    Printer,
    Award,
    School,
    CheckCircle2,
    Calendar,
    Shield,
    FileText,
} from "lucide-react";

interface PrintableCertificateModalProps {
    isOpen: boolean;
    onClose: () => void;
    certificate: Certificate | null | undefined;
}

function formatDate(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
            const [y, m, d] = dateStr.split("-").map(Number);
            const date = new Date(y, m - 1, d);
            return date.toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
        }
        return new Date(dateStr).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
    } catch {
        return dateStr;
    }
}

export function PrintableCertificateModal({
    isOpen,
    onClose,
    certificate,
}: PrintableCertificateModalProps) {
    const { data: institution } = useInstitutionProfile();
    const { data: certSettings } = useCertificateSettings();
    const printContainerRef = useRef<HTMLDivElement>(null);

    if (!certificate) return null;

    const schoolName = institution?.name || "Sunrise Valley Senior Secondary School";
    const schoolAddress = (institution as any)?.address || institution?.tagline || "Affiliated to Central Board of Secondary Education (CBSE), New Delhi";
    const schoolPhone = institution?.phone || "+91 (011) 2345-6789";
    const schoolEmail = institution?.email || "principal@school.edu";

    const signatoryName = certSettings?.signatory_name || "Authorized Principal";
    const signatoryTitle = certSettings?.signatory_title || "Principal & Head of Institution";

    const handlePrint = () => {
        window.print();
    };

    const typeLabel = certificate.certificate_type_label || "Certificate";

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent
                className="max-w-4xl max-h-[92vh] p-0 flex flex-col overflow-hidden rounded-2xl"
                showCloseButton={false}
            >
                <ModalHeader
                    title="Certificate Document Viewer"
                    subtitle="Official printable A4 institutional certificate"
                    badge={<CertificateStatusBadge status={certificate.status} />}
                    metadata={
                        <span className="font-mono text-indigo-600 font-bold">
                            {certificate.certificate_number}
                        </span>
                    }
                    actions={
                        <Button
                            size="sm"
                            onClick={handlePrint}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg h-9 font-semibold text-xs gap-1.5 print:hidden"
                        >
                            <Printer className="h-3.5 w-3.5" />
                            <span>Print Certificate</span>
                        </Button>
                    }
                    onClose={onClose}
                />

                <DialogBody className="flex-1 overflow-y-auto p-6 [scrollbar-width:thin] space-y-6 bg-slate-100/70 dark:bg-slate-950/70">
                    {/* A4 Printable Certificate Canvas */}
                    <div className="flex justify-center items-center py-2 print:p-0 print:m-0">
                        <div
                            ref={printContainerRef}
                            className="w-full max-w-[780px] bg-white text-slate-900 shadow-xl rounded-xl p-8 sm:p-12 border-[8px] border-double border-indigo-950/80 relative print-avoid-break print:shadow-none print:border-[6px] print:p-8"
                        >
                            {/* Watermark Crest */}
                            <div className="absolute inset-0 flex items-center justify-center pointer-events-none opacity-[0.03] select-none">
                                <Award className="w-[360px] h-[360px] text-slate-900" />
                            </div>

                            {/* Header: School Identity */}
                            <div className="text-center border-b-2 border-slate-300 pb-5 mb-6 relative">
                                <div className="flex justify-center mb-2">
                                    <div className="h-14 w-14 rounded-full bg-indigo-50 border-2 border-indigo-200 flex items-center justify-center text-indigo-700">
                                        <School className="h-8 w-8" />
                                    </div>
                                </div>
                                <h2 className="font-serif font-black text-2xl sm:text-3xl text-slate-900 tracking-tight uppercase">
                                    {schoolName}
                                </h2>
                                <p className="text-xs sm:text-sm text-slate-600 font-medium mt-1">
                                    {schoolAddress}
                                </p>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    Phone: {schoolPhone} • Email: {schoolEmail}
                                </p>
                            </div>

                            {/* Certificate Reference Metadata */}
                            <div className="flex justify-between items-center text-xs text-slate-700 font-medium mb-8 px-2 border-b border-slate-100 pb-2">
                                <div>
                                    <span className="text-slate-400 uppercase text-[10px] tracking-wider block">
                                        Certificate No.
                                    </span>
                                    <span className="font-mono font-bold text-sm text-indigo-900">
                                        {certificate.certificate_number}
                                    </span>
                                </div>
                                <div className="text-center">
                                    <span className="text-slate-400 uppercase text-[10px] tracking-wider block">
                                        Academic Year
                                    </span>
                                    <span className="font-bold text-slate-800">
                                        {certificate.academic_year || "2026-2027"}
                                    </span>
                                </div>
                                <div className="text-right">
                                    <span className="text-slate-400 uppercase text-[10px] tracking-wider block">
                                        Date of Issue
                                    </span>
                                    <span className="font-bold text-slate-800">
                                        {formatDate(certificate.issue_date)}
                                    </span>
                                </div>
                            </div>

                            {/* Certificate Title Badge */}
                            <div className="text-center mb-8">
                                <span className="inline-block px-6 py-2 rounded-full border-2 border-indigo-900 bg-indigo-50/70 text-indigo-950 font-serif font-extrabold text-lg sm:text-xl tracking-wider uppercase shadow-xs">
                                    {typeLabel}
                                </span>
                            </div>

                            {/* Certificate Body Paragraph */}
                            <div className="text-sm sm:text-base leading-relaxed text-slate-800 space-y-4 px-2 font-serif text-justify">
                                {certificate.certificate_type === "transfer" && (
                                    <>
                                        <p>
                                            This is to certify that{" "}
                                            <span className="font-bold underline decoration-slate-400 underline-offset-4 uppercase text-slate-950">
                                                {certificate.holder_name}
                                            </span>
                                            , was a bonafide student of this institution during the academic session{" "}
                                            <span className="font-bold text-slate-950">{certificate.academic_year}</span>.
                                        </p>
                                        <p>
                                            The student has cleared all school dues up to the date of leaving:{" "}
                                            <span className="font-bold text-slate-950">{formatDate(certificate.leaving_date)}</span>.
                                        </p>
                                        <p>
                                            Reason for leaving the school:{" "}
                                            <span className="font-semibold text-slate-950 italic">
                                                {certificate.reason || "On parent's request"}
                                            </span>.
                                        </p>
                                        <p>
                                            General conduct and moral character during the stay at this school has been{" "}
                                            <span className="font-bold text-slate-950 capitalize">{certificate.conduct || "Good"}</span>.
                                        </p>
                                    </>
                                )}

                                {certificate.certificate_type === "bonafide" && (
                                    <>
                                        <p>
                                            This is to certify that{" "}
                                            <span className="font-bold underline decoration-slate-400 underline-offset-4 uppercase text-slate-950">
                                                {certificate.holder_name}
                                            </span>{" "}
                                            is a bonafide student of this school pursuing academic studies in the academic session{" "}
                                            <span className="font-bold text-slate-950">{certificate.academic_year}</span>.
                                        </p>
                                        <p>
                                            This certificate is issued on the student&apos;s request for the purpose of:{" "}
                                            <span className="font-semibold text-slate-950 italic">
                                                {certificate.reason || "Official documentation and verification"}
                                            </span>.
                                        </p>
                                        <p>
                                            To the best of our knowledge, the student bears a{" "}
                                            <span className="font-bold text-slate-950 capitalize">{certificate.conduct || "Good"}</span> moral character.
                                        </p>
                                    </>
                                )}

                                {certificate.certificate_type === "character" && (
                                    <>
                                        <p>
                                            This is to certify that{" "}
                                            <span className="font-bold underline decoration-slate-400 underline-offset-4 uppercase text-slate-950">
                                                {certificate.holder_name}
                                            </span>{" "}
                                            has been a student of this institution during the academic year{" "}
                                            <span className="font-bold text-slate-950">{certificate.academic_year}</span>.
                                        </p>
                                        <p>
                                            During the tenure at this school, the student showed exemplary diligence, discipline, and moral integrity.
                                        </p>
                                        <p>
                                            Character &amp; Conduct Evaluation:{" "}
                                            <span className="font-bold text-slate-950 capitalize">{certificate.conduct || "Exemplary & Good"}</span>.
                                        </p>
                                    </>
                                )}

                                {certificate.certificate_type === "experience" && (
                                    <>
                                        <p>
                                            This is to certify that{" "}
                                            <span className="font-bold underline decoration-slate-400 underline-offset-4 uppercase text-slate-950">
                                                {certificate.holder_name}
                                            </span>{" "}
                                            served as an esteemed member of the faculty / staff at this institution.
                                        </p>
                                        <p>
                                            Period of Service: From{" "}
                                            <span className="font-bold text-slate-950">{formatDate(certificate.period_start)}</span> to{" "}
                                            <span className="font-bold text-slate-950">{formatDate(certificate.period_end)}</span>.
                                        </p>
                                        <p>
                                            Conduct &amp; Performance:{" "}
                                            <span className="font-bold text-slate-950 capitalize">{certificate.conduct || "Outstanding"}</span>.
                                        </p>
                                        <p>
                                            We wish them every success in all future professional and personal endeavors.
                                        </p>
                                    </>
                                )}
                            </div>

                            {/* Signatories & Official Seal */}
                            <div className="pt-16 sm:pt-20 mt-8 border-t border-slate-200 flex items-end justify-between px-2">
                                <div className="text-center">
                                    <div className="w-28 sm:w-36 border-b border-slate-500 mb-1 mx-auto" />
                                    <span className="text-[11px] font-bold uppercase text-slate-600 block">
                                        Prepared &amp; Checked By
                                    </span>
                                    <span className="text-[10px] text-slate-400">Office Superintendent</span>
                                </div>

                                {/* Circular Seal */}
                                <div className="hidden sm:flex flex-col items-center justify-center h-24 w-24 rounded-full border-2 border-dashed border-indigo-900/60 p-2 text-center text-[9px] font-bold text-indigo-900 uppercase opacity-70">
                                    <span>Official Seal</span>
                                    <span>★</span>
                                    <span>Institution</span>
                                </div>

                                <div className="text-center">
                                    <div className="w-32 sm:w-44 border-b border-slate-900 mb-1 mx-auto" />
                                    <span className="text-xs sm:text-sm font-bold text-slate-900 block font-serif">
                                        {signatoryName}
                                    </span>
                                    <span className="text-[10px] text-slate-500 font-medium">
                                        {signatoryTitle}
                                    </span>
                                </div>
                            </div>

                            {/* Verification Footer Note */}
                            <div className="mt-8 pt-4 border-t border-slate-100 flex items-center justify-between text-[10px] text-slate-400">
                                <span>
                                    Official Document • Tampering or alteration invalidates this certificate.
                                </span>
                                {certificate.verification_id && (
                                    <span className="font-mono">
                                        Verify: {certificate.verification_id}
                                    </span>
                                )}
                            </div>
                        </div>
                    </div>
                </DialogBody>

                <DialogFooter className="px-6 py-3.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 shrink-0 print:hidden flex items-center justify-between">
                    <span className="text-xs text-slate-500 font-medium">
                        Standard A4 Institutional Certificate Format (ISO 216)
                    </span>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={onClose} className="rounded-lg h-9">
                            Close
                        </Button>
                        <Button
                            size="sm"
                            onClick={handlePrint}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg h-9 gap-1.5 font-semibold"
                        >
                            <Printer className="h-3.5 w-3.5" />
                            <span>Print Certificate</span>
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
