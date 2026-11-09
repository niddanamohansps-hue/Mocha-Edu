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
import { useInstitutionProfile } from "@/hooks/useProfile";
import {
    Printer,
    Briefcase,
    Building,
    Phone,
    Mail,
    Shield,
    Calendar,
    Award,
    RotateCw,
} from "lucide-react";

interface StaffIDCardModalProps {
    isOpen: boolean;
    onClose: () => void;
    staff: {
        id: string;
        employee_id: string;
        designation: string;
        department?: string;
        joining_date?: string;
        qualification?: string;
        experience_years?: number;
        profile_details: {
            first_name: string;
            middle_name?: string;
            last_name: string;
            gender?: string;
            date_of_birth?: string;
            phone?: string;
            email?: string;
            address?: string;
            blood_group?: string;
        };
    } | null;
}

const AVATAR_PALETTES = [
    { bg: "bg-indigo-100", text: "text-indigo-700", border: "border-indigo-300" },
    { bg: "bg-sky-100", text: "text-sky-700", border: "border-sky-300" },
    { bg: "bg-emerald-100", text: "text-emerald-700", border: "border-emerald-300" },
    { bg: "bg-purple-100", text: "text-purple-700", border: "border-purple-300" },
    { bg: "bg-amber-100", text: "text-amber-700", border: "border-amber-300" },
    { bg: "bg-slate-100", text: "text-slate-700", border: "border-slate-300" },
];

function getAvatarStyle(name?: string | null) {
    if (!name) return AVATAR_PALETTES[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_PALETTES[Math.abs(hash) % AVATAR_PALETTES.length];
}

function getInitials(first: string = "", last: string = "") {
    const f = first.trim()[0] || "";
    const l = last.trim()[0] || "";
    return `${f}${l}`.toUpperCase() || "SF";
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

export function StaffIDCardModal({ isOpen, onClose, staff }: StaffIDCardModalProps) {
    const { data: institution } = useInstitutionProfile();
    const [orientation, setOrientation] = useState<"portrait" | "landscape">("portrait");
    const [side, setSide] = useState<"front" | "back">("front");

    const printContainerRef = useRef<HTMLDivElement>(null);

    if (!staff) return null;

    const profile = staff.profile_details;
    const staffFullName = `${profile.first_name || ""} ${profile.middle_name ? profile.middle_name + " " : ""}${profile.last_name || ""}`.trim() || "Staff Member";
    const initials = getInitials(profile.first_name, profile.last_name);
    const avatarStyle = getAvatarStyle(staffFullName);

    const schoolName = institution?.name || "Sunrise Valley School";
    const schoolAddress = (institution as any)?.address || institution?.tagline || "CBSE Affiliated Senior Secondary School";
    const schoolPhone = institution?.phone || "+91 (011) 2345-6789";
    const schoolEmail = institution?.email || "info@school.edu";

    const handlePrint = () => {
        window.print();
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    title="Staff & Faculty Identity Card"
                    subtitle="Official printable CR80 employee credential badge"
                    metadata={<span className="font-mono text-indigo-600 font-bold">{staff.employee_id}</span>}
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
                                <RotateCw className="h-3.5 w-3.5 text-indigo-600" />
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
                                        {/* Card Top Brand Header */}
                                        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white p-4 text-center relative">
                                            <div className="flex items-center justify-center gap-2 mb-1">
                                                <Building className="h-4 w-4 text-indigo-300" />
                                                <h3 className="font-black text-xs uppercase tracking-wide truncate max-w-[240px]">
                                                    {schoolName}
                                                </h3>
                                            </div>
                                            <span className="inline-block text-[9px] font-bold uppercase tracking-widest text-indigo-200 bg-indigo-900/60 px-2 py-0.5 rounded border border-indigo-700/50">
                                                Staff &amp; Faculty Credential
                                            </span>
                                        </div>

                                        {/* Card Photo & Core Info */}
                                        <div className="p-5 flex flex-col items-center flex-1 text-center space-y-3">
                                            {/* Photo / Deterministic Avatar */}
                                            <div
                                                className={`h-24 w-24 rounded-2xl flex items-center justify-center font-bold text-3xl border-2 ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border} shadow-sm shrink-0`}
                                            >
                                                {initials}
                                            </div>

                                            {/* Employee Name & Designation */}
                                            <div className="space-y-1">
                                                <h4 className="font-black text-base text-slate-900 leading-tight">
                                                    {staffFullName}
                                                </h4>
                                                <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                                                    <Briefcase className="h-3 w-3" />
                                                    <span>{staff.designation || "Staff Member"}</span>
                                                </div>
                                                {staff.department && (
                                                    <p className="text-[11px] text-slate-500 font-medium">
                                                        Dept: {staff.department}
                                                    </p>
                                                )}
                                            </div>

                                            {/* Employee Attribute Grid */}
                                            <div className="w-full pt-1 space-y-1.5 text-xs text-left">
                                                <div className="flex justify-between border-b border-slate-200/60 pb-1">
                                                    <span className="text-slate-500 font-medium">Employee ID:</span>
                                                    <span className="font-bold font-mono text-indigo-700">
                                                        {staff.employee_id}
                                                    </span>
                                                </div>
                                                {staff.qualification && (
                                                    <div className="flex justify-between border-b border-slate-200/60 pb-1">
                                                        <span className="text-slate-500 font-medium">Qualification:</span>
                                                        <span className="font-semibold text-slate-900 truncate max-w-[150px]">
                                                            {staff.qualification}
                                                        </span>
                                                    </div>
                                                )}
                                                {staff.joining_date && (
                                                    <div className="flex justify-between border-b border-slate-200/60 pb-1">
                                                        <span className="text-slate-500 font-medium">Joining Date:</span>
                                                        <span className="font-semibold text-slate-900">
                                                            {formatDate(staff.joining_date)}
                                                        </span>
                                                    </div>
                                                )}
                                                <div className="flex justify-between border-b border-slate-200/60 pb-1">
                                                    <span className="text-slate-500 font-medium">Contact Phone:</span>
                                                    <span className="font-bold font-mono text-slate-800">
                                                        {profile.phone || schoolPhone}
                                                    </span>
                                                </div>
                                                {profile.email && (
                                                    <div className="flex justify-between">
                                                        <span className="text-slate-500 font-medium">Official Email:</span>
                                                        <span className="font-semibold text-slate-700 text-[10px] truncate max-w-[150px]">
                                                            {profile.email}
                                                        </span>
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Barcode & Footer */}
                                        <div className="p-3 bg-slate-50 border-t border-slate-200 text-center space-y-1.5">
                                            {/* Simulated Barcode */}
                                            <div className="h-7 w-48 mx-auto flex items-center justify-center gap-[2px] overflow-hidden opacity-80">
                                                {[2, 3, 1, 4, 2, 5, 1, 6, 4, 3, 5, 2, 6, 7, 3, 4, 2, 5, 8, 3, 2, 6, 1, 4, 3, 2, 5, 4, 2, 7].map((w, idx) => (
                                                    <div key={idx} style={{ width: `${(w % 3) + 1.5}px` }} className="h-full bg-slate-900" />
                                                ))}
                                            </div>
                                            <p className="text-[9px] font-mono tracking-widest text-slate-500 font-semibold">
                                                *{staff.employee_id}*
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
                                                <p className="text-[10px] text-slate-400">Tel: {schoolPhone} • {schoolEmail}</p>
                                            </div>

                                            <div className="space-y-2 text-[11px] text-slate-700 leading-relaxed">
                                                <p className="font-semibold text-slate-900">Campus Authorization Terms:</p>
                                                <ul className="list-disc pl-4 space-y-1 text-slate-600 text-[10px]">
                                                    <li>This card certifies the bearer is an authorized faculty/staff member of this institution.</li>
                                                    <li>Must be visibly displayed within campus premises and security checkpoints.</li>
                                                    <li>Non-transferable; must be surrendered upon resignation or termination of service.</li>
                                                    <li>If found, please return to the School Administration Office immediately.</li>
                                                </ul>
                                            </div>
                                        </div>

                                        {/* Signature & Seal Area */}
                                        <div className="pt-8 border-t border-slate-200 flex items-end justify-between">
                                            <div className="text-center">
                                                <div className="w-20 border-b border-slate-400 mb-1" />
                                                <span className="text-[9px] uppercase font-bold text-slate-500">Employee Sign</span>
                                            </div>
                                            <div className="text-center">
                                                <div className="w-24 border-b border-slate-400 mb-1" />
                                                <span className="text-[9px] uppercase font-bold text-slate-500">Director / Principal</span>
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
                                        <div className="bg-gradient-to-r from-slate-900 via-indigo-950 to-slate-900 text-white px-4 py-2 flex items-center justify-between">
                                            <div className="flex items-center gap-2">
                                                <Building className="h-4 w-4 text-indigo-300" />
                                                <span className="font-black text-xs uppercase tracking-wide truncate max-w-[220px]">
                                                    {schoolName}
                                                </span>
                                            </div>
                                            <span className="text-[9px] font-bold uppercase tracking-wider bg-white/20 px-2 py-0.5 rounded">
                                                EMP: {staff.employee_id}
                                            </span>
                                        </div>

                                        {/* Content Body */}
                                        <div className="p-4 flex items-center gap-4 flex-1">
                                            <div className={`h-24 w-24 rounded-2xl flex items-center justify-center font-bold text-2xl border-2 ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border} shrink-0 shadow-sm`}>
                                                {initials}
                                            </div>

                                            <div className="space-y-1.5 flex-1 min-w-0 text-xs">
                                                <h4 className="font-black text-sm text-slate-900 truncate">
                                                    {staffFullName}
                                                </h4>
                                                <p className="font-bold text-indigo-700 text-xs truncate">
                                                    {staff.designation} {staff.department ? `• ${staff.department}` : ""}
                                                </p>
                                                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] pt-1">
                                                    <div>
                                                        <span className="text-slate-400 block text-[10px]">Joining:</span>
                                                        <span className="font-semibold text-slate-800">
                                                            {formatDate(staff.joining_date)}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <span className="text-slate-400 block text-[10px]">Qualification:</span>
                                                        <span className="font-semibold text-slate-800 truncate block">
                                                            {staff.qualification || "—"}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <span className="text-slate-400 block text-[10px]">Phone:</span>
                                                        <span className="font-bold font-mono text-slate-800">
                                                            {profile.phone || schoolPhone}
                                                        </span>
                                                    </div>
                                                    <div>
                                                        <span className="text-slate-400 block text-[10px]">Email:</span>
                                                        <span className="font-medium text-slate-700 truncate block text-[10px]">
                                                            {profile.email || "—"}
                                                        </span>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Footer Barcode */}
                                        <div className="px-4 py-2 bg-slate-50 border-t border-slate-200 flex items-center justify-between">
                                            <div className="h-5 w-36 flex items-center gap-[2px] opacity-80">
                                                {[2, 3, 1, 4, 2, 5, 1, 6, 4, 3, 5, 2, 6, 7, 3, 4, 2, 5].map((w, idx) => (
                                                    <div key={idx} style={{ width: `${(w % 2.5) + 1.5}px` }} className="h-full bg-slate-900" />
                                                ))}
                                            </div>
                                            <span className="text-[9px] font-semibold text-slate-400 uppercase tracking-wider">Authorized Faculty Badge</span>
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
                                            This card confirms official employment and campus authorization for institutional operations.
                                        </p>

                                        <div className="pt-4 flex items-end justify-between">
                                            <div className="text-center">
                                                <div className="w-20 border-b border-slate-400 mb-0.5" />
                                                <span className="text-[8px] uppercase font-bold text-slate-400">Employee Sign</span>
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
                        <Button variant="outline" size="sm" onClick={onClose} className="rounded-lg h-9">
                            Close
                        </Button>
                        <Button
                            size="sm"
                            onClick={handlePrint}
                            className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg h-9 gap-1.5 font-semibold"
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
