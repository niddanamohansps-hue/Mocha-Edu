"use client";

import React, { useState, useRef } from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Avatar } from "@/components/ui/avatar";
import { useInstitutionProfile } from "@/hooks/useProfile";
import {
    Printer,
    GraduationCap,
    School,
    Phone,
    Shield,
    Calendar,
    HeartPulse,
    MapPin,
    RotateCw,
} from "lucide-react";

interface StudentIDCardModalProps {
    isOpen: boolean;
    onClose: () => void;
    student: {
        id: string;
        full_name?: string;
        first_name?: string;
        last_name?: string;
        middle_name?: string;
        enrollment_id: string;
        photo?: string | null;
        profile_image?: string | null;
        level?: string;
        section?: string;
        academic_year?: string;
        date_of_birth?: string;
        blood_group?: string;
        guardian_name?: string;
        phone?: string;
        address?: string;
        is_rte?: boolean;
    } | null;
}

function formatDate(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
            const [y, m, d] = dateStr.split("-").map(Number);
            const date = new Date(y, m - 1, d);
            return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        }
        return new Date(dateStr).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
        return dateStr;
    }
}

export function StudentIDCardModal({ isOpen, onClose, student }: StudentIDCardModalProps) {
    const { data: institution } = useInstitutionProfile();
    const [orientation, setOrientation] = useState<"portrait" | "landscape">("portrait");
    const [side, setSide] = useState<"front" | "back">("front");

    const printContainerRef = useRef<HTMLDivElement>(null);

    if (!student) return null;

    const studentFullName = student.full_name || `${student.first_name || ""} ${student.last_name || ""}`.trim() || "Student Name";

    const schoolName = institution?.name || "Sunrise Valley School";
    const schoolAddress = (institution as any)?.address || institution?.tagline || "CBSE Affiliated Senior Secondary School";
    const schoolPhone = institution?.phone || "+91 (011) 2345-6789";

    const handlePrint = () => {
        window.print();
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    title="Student Identity Card"
                    subtitle="Official printable CR80 photo badge"
                    metadata={<span className="font-mono text-sky-600 font-bold">{student.enrollment_id}</span>}
                    actions={
                        <Button
                            size="sm"
                            onClick={handlePrint}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg h-9 font-semibold text-xs gap-1.5 print:hidden"
                        >
                            <Printer className="h-3.5 w-3.5" />
                            <span>Print ID Card</span>
                        </Button>
                    }
                    onClose={onClose}
                />

                <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-6">
                    {/* Controls Toolbar (Hidden when printing) */}
                    <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-200/80 dark:border-slate-800 print:hidden">
                        <div className="flex items-center gap-1.5">
                            <span className="text-xs font-semibold text-slate-500 mr-1">Orientation:</span>
                            <button
                                type="button"
                                onClick={() => setOrientation("portrait")}
                                className={`px-2.5 py-1 text-xs font-semibold rounded-lg border transition ${orientation === "portrait" ? "bg-indigo-600 text-white border-indigo-600" : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700"}`}
                            >
                                Portrait Badge
                            </button>
                            <button
                                type="button"
                                onClick={() => setOrientation("landscape")}
                                className={`px-2.5 py-1 text-xs font-semibold rounded-lg border transition ${orientation === "landscape" ? "bg-indigo-600 text-white border-indigo-600" : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700"}`}
                            >
                                Landscape Card
                            </button>
                        </div>

                        <div className="flex items-center gap-1.5">
                            <button
                                type="button"
                                onClick={() => setSide(side === "front" ? "back" : "front")}
                                className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 hover:bg-slate-50 transition"
                            >
                                <RotateCw className="h-3.5 w-3.5 text-sky-600" />
                                <span>Flip to {side === "front" ? "Back Side" : "Front Side"}</span>
                            </button>
                        </div>
                    </div>

                    {/* Printable Card Container */}
                    <div ref={printContainerRef} className="flex justify-center items-center py-4 print:p-0 print:m-0">
                        {orientation === "portrait" ? (
                            /* PORTRAIT BADGE (Standard Lanyard Format: 320px x 480px) */
                            <div className="w-[320px] min-h-[480px] bg-white text-slate-900 rounded-2xl border-2 border-slate-300 shadow-xl overflow-hidden flex flex-col justify-between relative print-avoid-break print:shadow-none print:border-slate-400">
                                {side === "front" ? (
                                    <>
                                        {/* School Header Banner */}
                                        <div className="bg-gradient-to-r from-indigo-700 via-sky-700 to-indigo-800 text-white p-4 text-center relative">
                                            <div className="w-10 h-10 rounded-full bg-white/10 backdrop-blur-xs border border-white/30 flex items-center justify-center mx-auto mb-1.5 shadow-sm">
                                                <GraduationCap className="h-5 w-5 text-white" />
                                            </div>
                                            <h3 className="font-black text-sm uppercase tracking-wide leading-tight">
                                                {schoolName}
                                            </h3>
                                            <p className="text-[10px] text-sky-200 font-medium tracking-wider uppercase mt-0.5">
                                                Student Identity Card • {student.academic_year || "2026-27"}
                                            </p>
                                        </div>

                                        {/* Student Photo & Demographics */}
                                        <div className="p-4 text-center flex-1 flex flex-col items-center justify-center space-y-3">
                                            <Avatar
                                                name={studentFullName}
                                                src={student.photo}
                                                size="card"
                                                shape="rounded"
                                                className="shadow-md"
                                            />

                                            <div>
                                                <h4 className="font-black text-base text-slate-900 tracking-tight">
                                                    {studentFullName}
                                                </h4>
                                                <div className="inline-flex items-center gap-1.5 mt-1">
                                                    <span className="font-mono text-xs font-bold bg-slate-100 text-slate-800 px-2 py-0.5 rounded border border-slate-200">
                                                        {student.enrollment_id}
                                                    </span>
                                                </div>
                                            </div>

                                            {/* Details Grid */}
                                            <div className="w-full bg-slate-50 border border-slate-200/80 rounded-xl p-2.5 text-left text-[11px] space-y-1.5">
                                                <div className="flex justify-between border-b border-slate-200/60 pb-1">
                                                    <span className="text-slate-500 font-medium">Class &amp; Section:</span>
                                                    <span className="font-bold text-slate-900">
                                                        {student.level || "Grade Not Set"} {student.section ? `• Sec ${student.section}` : ""}
                                                    </span>
                                                </div>
                                                <div className="flex justify-between border-b border-slate-200/60 pb-1">
                                                    <span className="text-slate-500 font-medium">Date of Birth:</span>
                                                    <span className="font-semibold text-slate-900">
                                                        {formatDate(student.date_of_birth)}
                                                    </span>
                                                </div>
                                                <div className="flex justify-between border-b border-slate-200/60 pb-1">
                                                    <span className="text-slate-500 font-medium">Emergency Contact:</span>
                                                    <span className="font-bold font-mono text-sky-700">
                                                        {student.phone || schoolPhone}
                                                    </span>
                                                </div>
                                                {student.guardian_name && (
                                                    <div className="flex justify-between">
                                                        <span className="text-slate-500 font-medium">Guardian:</span>
                                                        <span className="font-semibold text-slate-900 truncate max-w-[140px]">
                                                            {student.guardian_name}
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Barcode & Footer */}
                                        <div className="p-3 bg-slate-50 border-t border-slate-200 text-center space-y-1.5">
                                            {/* Simulated Barcode */}
                                            <div className="h-7 w-48 mx-auto flex items-center justify-center gap-[2px] overflow-hidden opacity-80">
                                                {[3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3, 2, 3, 8, 4, 6, 2, 6, 4, 3, 3, 8, 3, 2, 7].map((w, idx) => (
                                                    <div key={idx} style={{ width: `${(w % 3) + 1.5}px` }} className="h-full bg-slate-900" />
                                                ))}
                                            </div>
                                            <p className="text-[9px] font-mono tracking-widest text-slate-500 font-semibold">
                                                *{student.enrollment_id}*
                                            </p>
                                        </div>
                                    </>
                                ) : (
                                    /* PORTRAIT BACK SIDE */
                                    <div className="p-5 flex-1 flex flex-col justify-between text-xs space-y-4">
                                        <div className="space-y-3">
                                            <div className="text-center border-b border-slate-200 pb-2">
                                                <h4 className="font-black uppercase text-sm text-slate-900">{schoolName}</h4>
                                                <p className="text-[10px] text-slate-500">{schoolAddress}</p>
                                            </div>

                                            <div className="space-y-2 text-[11px] text-slate-700 leading-relaxed">
                                                <p className="font-semibold text-slate-900">Terms &amp; Instructions:</p>
                                                <ul className="list-disc pl-4 space-y-1 text-slate-600 text-[10px]">
                                                    <li>This identity card is the property of the school and must be worn on campus at all times.</li>
                                                    <li>In case of loss, notify the administration office immediately.</li>
                                                    <li>Non-transferable and surrenderable upon leaving institution.</li>
                                                </ul>
                                            </div>
                                        </div>

                                        {/* Signature & Seal Area */}
                                        <div className="pt-8 border-t border-slate-200 flex items-end justify-between">
                                            <div className="text-center">
                                                <div className="w-20 border-b border-slate-400 mb-1" />
                                                <span className="text-[9px] uppercase font-bold text-slate-500">Student Sign</span>
                                            </div>
                                            <div className="text-center">
                                                <div className="w-24 border-b border-slate-400 mb-1" />
                                                <span className="text-[9px] uppercase font-bold text-slate-500">Principal Signature</span>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        ) : (
                            /* LANDSCAPE CARD (Standard Wallet Format: 420px x 260px) */
                            <div className="w-[420px] min-h-[260px] bg-white text-slate-900 rounded-2xl border-2 border-slate-300 shadow-xl overflow-hidden flex flex-col justify-between relative print-avoid-break print:shadow-none print:border-slate-400">
                                {side === "front" ? (
                                    <>
                                        {/* Header */}
                                        <div className="bg-gradient-to-r from-indigo-700 via-sky-700 to-indigo-800 text-white px-4 py-2 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <GraduationCap className="h-4 w-4 text-sky-200" />
                                                <span className="font-black text-xs uppercase tracking-wide">{schoolName}</span>
                                            </div>
                                            <span className="text-[9px] font-bold uppercase tracking-wider bg-white/20 px-1.5 py-0.5 rounded">
                                                ID: {student.enrollment_id}
                                            </span>
                                        </div>

                                        {/* Content Body */}
                                        <div className="p-4 flex items-center gap-4 flex-1">
                                            <Avatar
                                                name={studentFullName}
                                                src={student.photo}
                                                size="card"
                                                shape="rounded"
                                                className="shrink-0 shadow-sm"
                                            />

                                            <div className="space-y-1.5 flex-1 min-w-0 text-xs">
                                                <h4 className="font-black text-sm text-slate-900 truncate">
                                                    {studentFullName}
                                                </h4>
                                                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px]">
                                                    <div>
                                                        <span className="text-slate-400 block">Class:</span>
                                                        <span className="font-bold text-slate-800">
                                                            {student.level || "Grade"} {student.section ? `(${student.section})` : ""}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <span className="text-slate-400 block">Session:</span>
                                                        <span className="font-semibold text-slate-800">{student.academic_year || "2026-27"}</span>
                                                    </div>
                                                    <div>
                                                        <span className="text-slate-400 block">DOB:</span>
                                                        <span className="font-semibold text-slate-800">{formatDate(student.date_of_birth)}</span>
                                                    </div>
                                                    <div>
                                                        <span className="text-slate-400 block">Emergency:</span>
                                                        <span className="font-bold font-mono text-sky-700">{student.phone || schoolPhone}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Footer Barcode */}
                                        <div className="px-4 py-2 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
                                            <div className="h-5 w-36 flex items-center gap-[2px] opacity-80">
                                                {[3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3, 2, 3, 8, 4, 6].map((w, idx) => (
                                                    <div key={idx} style={{ width: `${(w % 2.5) + 1.5}px` }} className="h-full bg-slate-900" />
                                                ))}
                                            </div>
                                            <span className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">Authorized Student Badge</span>
                                        </div>
                                    </>
                                ) : (
                                    /* LANDSCAPE BACK SIDE */
                                    <div className="p-4 flex-1 flex flex-col justify-between text-xs space-y-3">
                                        <div className="border-b border-slate-200 pb-1.5 flex justify-between items-center">
                                            <span className="font-bold text-xs uppercase text-slate-900">{schoolName}</span>
                                            <span className="text-[10px] text-slate-500">{schoolPhone}</span>
                                        </div>

                                        <p className="text-[10px] text-slate-600 leading-relaxed">
                                            If found, please return to: {schoolAddress}. Phone: {schoolPhone}.
                                            This card confirms identity for campus entry, library access, and examinations.
                                        </p>

                                        <div className="pt-4 flex items-end justify-between">
                                            <div className="text-center">
                                                <div className="w-20 border-b border-slate-400 mb-0.5" />
                                                <span className="text-[8px] uppercase font-bold text-slate-400">Student Sign</span>
                                            </div>
                                            <div className="text-center">
                                                <div className="w-24 border-b border-slate-400 mb-0.5" />
                                                <span className="text-[8px] uppercase font-bold text-slate-400">Principal Signature</span>
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </DialogBody>

                <DialogFooter className="px-6 py-3.5 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 shrink-0 print:hidden flex items-center justify-between">
                    <span className="text-xs text-slate-500 font-medium">
                        Standard CR80 Printable Dimensions (ISO/IEC 7810 ID-1)
                    </span>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={onClose}>
                            Close
                        </Button>
                        <Button
                            size="sm"
                            onClick={handlePrint}
                            className="gap-1.5 bg-indigo-600 hover:bg-indigo-500 text-white"
                        >
                            <Printer className="h-3.5 w-3.5" />
                            <span>Print Card</span>
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
