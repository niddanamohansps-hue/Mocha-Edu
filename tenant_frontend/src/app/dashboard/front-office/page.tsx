"use client";

import React, { useState } from "react";
import {
    ShieldCheck,
    Users,
    LogOut,
    Plus,
    Search,
    Calendar,
    Phone,
    Car,
    FileText,
    Mail,
    Printer,
    CheckCircle2,
    XCircle,
    Clock,
    AlertTriangle,
} from "lucide-react";
import {
    useFrontOfficeOverview,
    useVisitors,
    useGatePasses,
    usePostalRecords,
    useCreateVisitor,
    useCheckOutVisitor,
    useCreateGatePass,
    useConfirmGatePassExit,
    useCancelGatePass,
    useCreatePostalRecord,
    VisitorLog,
    StudentGatePass,
} from "@/hooks/useFrontOffice";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { StudentPicker } from "@/components/common/StudentPicker";
import type { Student } from "@/hooks/useStudents";

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
];

function getAvatarStyle(name?: string | null) {
    if (!name || typeof name !== "string") return AVATAR_PALETTES[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) hash = name.charCodeAt(i) + ((hash << 5) - hash);
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

export default function FrontOfficePage() {
    const { can } = usePermissions();

    const [activeTab, setActiveTab] = useState<"visitors" | "gatepasses" | "postal">("visitors");

    // Filters
    const [visitorStatus, setVisitorStatus] = useState<string>("active");
    const [visitorSearch, setVisitorSearch] = useState<string>("");

    const [gatePassStatus, setGatePassStatus] = useState<string>("");
    const [gatePassSearch, setGatePassSearch] = useState<string>("");

    const [postalType, setPostalType] = useState<string>("");
    const [postalSearch, setPostalSearch] = useState<string>("");

    // Modals
    const [isVisitorModalOpen, setIsVisitorModalOpen] = useState(false);
    const [isGatePassModalOpen, setIsGatePassModalOpen] = useState(false);
    const [isPostalModalOpen, setIsPostalModalOpen] = useState(false);

    const [visitorToCheckOut, setVisitorToCheckOut] = useState<VisitorLog | null>(null);
    const [checkOutRemarks, setCheckOutRemarks] = useState("");

    const [gatePassToExit, setGatePassToExit] = useState<StudentGatePass | null>(null);
    const [gateSecurityNote, setGateSecurityNote] = useState("");

    // Queries
    const { data: overview } = useFrontOfficeOverview();
    const { data: visitors = [], isLoading: isLoadingVisitors } = useVisitors({
        status: visitorStatus || undefined,
        search: visitorSearch || undefined,
    });
    const { data: gatePasses = [], isLoading: isLoadingGatePasses } = useGatePasses({
        status: gatePassStatus || undefined,
        search: gatePassSearch || undefined,
    });
    const { data: postalRecords = [], isLoading: isLoadingPostal } = usePostalRecords({
        record_type: postalType || undefined,
        search: postalSearch || undefined,
    });

    // Mutations
    const createVisitor = useCreateVisitor();
    const checkOutVisitor = useCheckOutVisitor();
    const createGatePass = useCreateGatePass();
    const confirmExit = useConfirmGatePassExit();
    const cancelGatePass = useCancelGatePass();
    const createPostal = useCreatePostalRecord();

    // Form states
    const [visitorForm, setVisitorForm] = useState({
        visitor_name: "",
        phone: "",
        id_proof_type: "aadhaar",
        id_proof_number: "",
        organization: "",
        purpose: "parent_meeting",
        purpose_details: "",
        person_to_meet_name: "",
        badge_number: "",
        vehicle_number: "",
        number_of_visitors: 1,
        remarks: "",
    });

    const [gatePassStudent, setGatePassStudent] = useState<Student | null>(null);
    const [gatePassForm, setGatePassForm] = useState({
        student: "",
        reason_category: "illness",
        reason_details: "",
        picked_up_by_name: "",
        relationship: "father",
        picked_up_by_phone: "",
    });

    const [postalForm, setPostalForm] = useState({
        record_type: "inward" as "inward" | "outward",
        tracking_number: "",
        title: "",
        from_title: "",
        to_title: "",
        courier_company: "India Post Speed Post",
        dispatch_date: new Date().toISOString().split("T")[0],
        reference_number: "",
        notes: "",
    });

    const handleCreateVisitor = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!visitorForm.visitor_name || !visitorForm.phone) return;
        await createVisitor.mutateAsync(visitorForm);
        setIsVisitorModalOpen(false);
        setVisitorForm({
            visitor_name: "",
            phone: "",
            id_proof_type: "aadhaar",
            id_proof_number: "",
            organization: "",
            purpose: "parent_meeting",
            purpose_details: "",
            person_to_meet_name: "",
            badge_number: "",
            vehicle_number: "",
            number_of_visitors: 1,
            remarks: "",
        });
    };

    const handleCheckOut = async () => {
        if (!visitorToCheckOut) return;
        await checkOutVisitor.mutateAsync({ id: visitorToCheckOut.id, remarks: checkOutRemarks });
        setVisitorToCheckOut(null);
        setCheckOutRemarks("");
    };

    const handleCreateGatePass = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!gatePassForm.student || !gatePassForm.picked_up_by_name || !gatePassForm.picked_up_by_phone) return;
        await createGatePass.mutateAsync(gatePassForm);
        setIsGatePassModalOpen(false);
        setGatePassStudent(null);
        setGatePassForm({
            student: "",
            reason_category: "illness",
            reason_details: "",
            picked_up_by_name: "",
            relationship: "father",
            picked_up_by_phone: "",
        });
    };

    const handleConfirmExit = async () => {
        if (!gatePassToExit) return;
        await confirmExit.mutateAsync({ id: gatePassToExit.id, note: gateSecurityNote });
        setGatePassToExit(null);
        setGateSecurityNote("");
    };

    const handleCreatePostal = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!postalForm.title || !postalForm.from_title || !postalForm.to_title) return;
        await createPostal.mutateAsync(postalForm);
        setIsPostalModalOpen(false);
        setPostalForm({
            record_type: "inward",
            tracking_number: "",
            title: "",
            from_title: "",
            to_title: "",
            courier_company: "India Post Speed Post",
            dispatch_date: new Date().toISOString().split("T")[0],
            reference_number: "",
            notes: "",
        });
    };

    const printSlip = (title: string, passNo: string, details: Array<[string, string]>) => {
        const win = window.open("", "_blank");
        if (!win) return;
        const html = `
            <!DOCTYPE html>
            <html>
            <head>
                <title>${title} - ${passNo}</title>
                <style>
                    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 24px; color: #1e293b; }
                    .pass-card { max-width: 480px; margin: 0 auto; border: 2px solid #0f172a; border-radius: 8px; padding: 20px; }
                    .header { text-align: center; border-bottom: 2px dashed #94a3b8; padding-bottom: 12px; margin-bottom: 16px; }
                    .header h2 { margin: 0; font-size: 18px; text-transform: uppercase; letter-spacing: 1px; }
                    .header .pass-no { font-family: monospace; font-size: 16px; font-weight: bold; margin-top: 4px; color: #2563eb; }
                    .row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; }
                    .row .label { font-weight: 600; color: #64748b; }
                    .row .value { font-weight: 600; text-align: right; }
                    .footer { border-top: 1px solid #cbd5e1; margin-top: 20px; padding-top: 16px; display: flex; justify-content: space-between; font-size: 11px; }
                    .sig-line { width: 120px; border-top: 1px solid #475569; text-align: center; padding-top: 4px; margin-top: 36px; }
                    @media print { body { padding: 0; } }
                </style>
            </head>
            <body>
                <div class="pass-card">
                    <div class="header">
                        <h2>${title}</h2>
                        <div class="pass-no">${passNo}</div>
                    </div>
                    ${details.map(([l, v]) => `<div class="row"><span class="label">${l}</span><span class="value">${v}</span></div>`).join("")}
                    <div class="footer">
                        <div class="sig-line">Security / Gate</div>
                        <div class="sig-line">Authorized Signatory</div>
                    </div>
                </div>
                <script>window.onload = function() { window.print(); };</script>
            </body>
            </html>
        `;
        win.document.write(html);
        win.document.close();
    };

    return (
        <div className="p-6 max-w-7xl mx-auto space-y-6">
            {/* Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 flex items-center gap-2.5">
                        <ShieldCheck className="h-7 w-7 text-sky-600 dark:text-sky-400" />
                        Front Office & Visitor Management
                    </h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Campus entrance gate log, visitor badges, student early exit passes, and courier tracking.
                    </p>
                </div>
                <div className="flex flex-wrap items-center gap-2.5">
                    {can("manage_visitors") && (
                        <button
                            onClick={() => setIsVisitorModalOpen(true)}
                            className="inline-flex items-center gap-1.5 px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors cursor-pointer"
                        >
                            <Plus className="h-4 w-4" />
                            Check In Visitor
                        </button>
                    )}
                    {can("issue_gate_pass") && (
                        <button
                            onClick={() => setIsGatePassModalOpen(true)}
                            className="inline-flex items-center gap-1.5 px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg shadow-sm transition-colors cursor-pointer"
                        >
                            <LogOut className="h-4 w-4" />
                            Issue Gate Pass
                        </button>
                    )}
                    {can("manage_postal_records") && (
                        <button
                            onClick={() => setIsPostalModalOpen(true)}
                            className="inline-flex items-center gap-1.5 px-3 py-2 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 text-slate-700 dark:text-slate-200 text-sm font-medium rounded-lg shadow-sm hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors cursor-pointer"
                        >
                            <Mail className="h-4 w-4" />
                            Log Courier
                        </button>
                    )}
                </div>
            </div>

            {/* KPI Stats */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-sky-100 dark:border-sky-950/40 shadow-sm">
                    <div className="text-xs font-medium text-sky-600 dark:text-sky-400 flex items-center gap-1.5">
                        <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                        Active Visitors Inside
                    </div>
                    <div className="text-3xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                        {overview?.active_visitors_inside || 0}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">Currently on school campus</div>
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Total Visitors Today</div>
                    <div className="text-3xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                        {overview?.visitors_today || 0}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">Checked in today</div>
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-amber-100 dark:border-amber-950/40 shadow-sm">
                    <div className="text-xs font-medium text-amber-600 dark:text-amber-400 flex items-center gap-1">
                        <LogOut className="h-3.5 w-3.5" /> Student Gate Passes Today
                    </div>
                    <div className="text-3xl font-bold text-amber-600 dark:text-amber-400 mt-1">
                        {overview?.gate_passes_today || 0}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">
                        {overview?.active_gate_passes || 0} pending gate exit
                    </div>
                </div>
                <div className="p-4 bg-white dark:bg-slate-800 rounded-xl border border-slate-200 dark:border-slate-700 shadow-sm">
                    <div className="text-xs font-medium text-slate-500 dark:text-slate-400">Postal / Parcels (Month)</div>
                    <div className="text-3xl font-bold text-slate-900 dark:text-slate-100 mt-1">
                        {overview?.postal_inward_this_month || 0}
                    </div>
                    <div className="text-xs text-slate-400 mt-1">Inward courier received</div>
                </div>
            </div>

            {/* Navigation Tabs */}
            <div className="flex border-b border-slate-200 dark:border-slate-800 space-x-8">
                <button
                    onClick={() => setActiveTab("visitors")}
                    className={`pb-3 text-sm font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
                        activeTab === "visitors"
                            ? "border-sky-600 text-sky-600 dark:text-sky-400 dark:border-sky-400"
                            : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
                    }`}
                >
                    <Users className="h-4 w-4" />
                    Visitor Log
                </button>
                <button
                    onClick={() => setActiveTab("gatepasses")}
                    className={`pb-3 text-sm font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
                        activeTab === "gatepasses"
                            ? "border-sky-600 text-sky-600 dark:text-sky-400 dark:border-sky-400"
                            : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
                    }`}
                >
                    <LogOut className="h-4 w-4" />
                    Student Gate Passes
                </button>
                <button
                    onClick={() => setActiveTab("postal")}
                    className={`pb-3 text-sm font-medium border-b-2 transition-colors cursor-pointer flex items-center gap-2 ${
                        activeTab === "postal"
                            ? "border-sky-600 text-sky-600 dark:text-sky-400 dark:border-sky-400"
                            : "border-transparent text-slate-500 hover:text-slate-700 dark:text-slate-400"
                    }`}
                >
                    <Mail className="h-4 w-4" />
                    Postal & Courier Log
                </button>
            </div>

            {/* TAB 1: VISITOR LOG */}
            {activeTab === "visitors" && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="relative">
                                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                <Input
                                    type="text"
                                    placeholder="Search visitor, phone, pass #..."
                                    value={visitorSearch}
                                    onChange={(e) => setVisitorSearch(e.target.value)}
                                    className="pl-9 h-9 text-xs w-64 rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                                />
                            </div>
                            <select
                                value={visitorStatus}
                                onChange={(e) => setVisitorStatus(e.target.value)}
                                className="h-9 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300"
                            >
                                <option value="">All Statuses</option>
                                <option value="active">Active (Inside Campus)</option>
                                <option value="checked_out">Checked Out</option>
                            </select>
                        </div>
                        <div className="text-xs text-slate-500 font-semibold">
                            {visitors.length} visitors logged
                        </div>
                    </div>

                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-slate-50/75 dark:bg-slate-900/60">
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Pass #</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Visitor</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Phone & ID</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Purpose</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Person to Meet</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Badge & Vehicle</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Check-In</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Status</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {isLoadingVisitors ? (
                                    <TableRow>
                                        <TableCell colSpan={9} className="py-12 text-center text-xs text-slate-400">
                                            Loading visitor logs...
                                        </TableCell>
                                    </TableRow>
                                ) : visitors.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={9} className="py-12 text-center text-xs text-slate-400">
                                            No visitor entries found matching the filter.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    visitors.map((v) => {
                                        const avatar = getAvatarStyle(v.visitor_name);
                                        return (
                                            <TableRow key={v.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                                <TableCell className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                                                    {v.pass_number}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2.5">
                                                        <div className={`w-8 h-8 rounded-lg ${avatar.bg} ${avatar.text} ${avatar.border} border flex items-center justify-center font-bold text-xs shrink-0`}>
                                                            {v.visitor_name.slice(0, 2).toUpperCase()}
                                                        </div>
                                                        <div>
                                                            <div className="font-bold text-xs text-slate-900 dark:text-white">{v.visitor_name}</div>
                                                            {v.organization && (
                                                                <div className="text-[11px] text-slate-400">{v.organization}</div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-600 dark:text-slate-300">
                                                    <div className="font-mono">{v.phone}</div>
                                                    {v.id_proof_number && (
                                                        <div className="text-[10px] text-slate-400 uppercase">
                                                            {v.id_proof_type}: {v.id_proof_number}
                                                        </div>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-700 dark:text-slate-300">
                                                    <Badge variant="outline" className="text-[11px] font-semibold bg-slate-50 text-slate-700 border-slate-200">
                                                        {v.purpose_display || v.purpose}
                                                    </Badge>
                                                    {v.purpose_details && (
                                                        <div className="text-[11px] text-slate-400 truncate max-w-xs mt-0.5">{v.purpose_details}</div>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-700 dark:text-slate-300">
                                                    {v.person_to_meet_staff_name || v.person_to_meet_name || "—"}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-600 dark:text-slate-300">
                                                    {v.badge_number && (
                                                        <span className="px-2 py-0.5 bg-slate-100 dark:bg-slate-800 rounded font-mono text-[11px]">
                                                            {v.badge_number}
                                                        </span>
                                                    )}
                                                    {v.vehicle_number && (
                                                        <div className="text-[10px] text-slate-400 mt-0.5">{v.vehicle_number}</div>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                                                    {new Date(v.check_in_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge
                                                        className={
                                                            v.status === "active"
                                                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300/80 text-[10px]"
                                                                : "bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400 border border-slate-200 text-[10px]"
                                                        }
                                                    >
                                                        {v.status === "active" ? (
                                                            <span className="flex items-center gap-1.5">
                                                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
                                                                Inside Campus
                                                            </span>
                                                        ) : (
                                                            "Checked Out"
                                                        )}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right space-x-1.5">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() =>
                                                            printSlip("Visitor Pass Slip", v.pass_number, [
                                                                ["Visitor Name", v.visitor_name],
                                                                ["Phone", v.phone],
                                                                ["Purpose", v.purpose_display || v.purpose],
                                                                ["Person to Meet", v.person_to_meet_staff_name || v.person_to_meet_name || "General"],
                                                                ["Badge #", v.badge_number || "None"],
                                                                ["Vehicle #", v.vehicle_number || "None"],
                                                                ["Check-In Time", new Date(v.check_in_time).toLocaleString()],
                                                            ])
                                                        }
                                                        className="h-8 px-2 text-xs text-slate-600 hover:text-slate-900 cursor-pointer"
                                                        title="Print Visitor Pass"
                                                    >
                                                        <Printer className="h-3.5 w-3.5 mr-1" />
                                                        Slip
                                                    </Button>
                                                    {v.status === "active" && can("manage_visitors") && (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => setVisitorToCheckOut(v)}
                                                            className="h-8 px-2.5 text-xs text-rose-600 hover:text-rose-700 border-rose-200 hover:bg-rose-50 cursor-pointer font-semibold"
                                                        >
                                                            Check Out
                                                        </Button>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })
                                )}
                            </TableBody>
                        </Table>
                    </TableShell>
                </div>
            )}

            {/* TAB 2: STUDENT GATE PASSES */}
            {activeTab === "gatepasses" && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="relative">
                                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                <Input
                                    type="text"
                                    placeholder="Search student, pickup person, pass #..."
                                    value={gatePassSearch}
                                    onChange={(e) => setGatePassSearch(e.target.value)}
                                    className="pl-9 h-9 text-xs w-64 rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                                />
                            </div>
                            <select
                                value={gatePassStatus}
                                onChange={(e) => setGatePassStatus(e.target.value)}
                                className="h-9 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300"
                            >
                                <option value="">All Statuses</option>
                                <option value="issued">Issued (Pending Departure)</option>
                                <option value="departed">Departed</option>
                                <option value="cancelled">Cancelled</option>
                            </select>
                        </div>
                        <div className="text-xs text-slate-500 font-semibold">
                            {gatePasses.length} gate passes issued
                        </div>
                    </div>

                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-slate-50/75 dark:bg-slate-900/60">
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Gate Pass #</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Student & Cohort</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Reason</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Picked Up By</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Authorized By</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Departure</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Status</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 text-right">Actions</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {isLoadingGatePasses ? (
                                    <TableRow>
                                        <TableCell colSpan={8} className="py-12 text-center text-xs text-slate-400">
                                            Loading student gate passes...
                                        </TableCell>
                                    </TableRow>
                                ) : gatePasses.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={8} className="py-12 text-center text-xs text-slate-400">
                                            No gate passes recorded matching the criteria.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    gatePasses.map((gp) => {
                                        const avatar = getAvatarStyle(gp.student_name || "Student");
                                        return (
                                            <TableRow key={gp.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                                <TableCell className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400">
                                                    {gp.pass_number}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2.5">
                                                        <div className={`w-8 h-8 rounded-lg ${avatar.bg} ${avatar.text} ${avatar.border} border flex items-center justify-center font-bold text-xs shrink-0`}>
                                                            {(gp.student_name || "ST").slice(0, 2).toUpperCase()}
                                                        </div>
                                                        <div>
                                                            <div className="font-bold text-xs text-slate-900 dark:text-white">{gp.student_name}</div>
                                                            <div className="text-[11px] text-slate-400">
                                                                {gp.student_enrollment_id} • {gp.student_class_section || "Class Section"}
                                                            </div>
                                                        </div>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-700 dark:text-slate-300">
                                                    <Badge variant="outline" className="text-[11px] font-semibold bg-rose-50 text-rose-700 border-rose-200">
                                                        {gp.reason_category_display}
                                                    </Badge>
                                                    {gp.reason_details && (
                                                        <div className="text-[11px] text-slate-400 truncate max-w-xs mt-0.5">{gp.reason_details}</div>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-700 dark:text-slate-300">
                                                    <div className="font-semibold">{gp.picked_up_by_name} <span className="text-slate-400 font-normal">({gp.relationship_display})</span></div>
                                                    <div className="text-slate-400 font-mono text-[11px]">{gp.picked_up_by_phone}</div>
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-600 dark:text-slate-300">
                                                    {gp.authorized_by_staff_name || "School Principal"}
                                                </TableCell>
                                                <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                                                    {new Date(gp.departure_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                                                </TableCell>
                                                <TableCell>
                                                    <Badge
                                                        className={
                                                            gp.status === "issued"
                                                                ? "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300 border border-amber-300/80 text-[10px]"
                                                                : gp.status === "departed"
                                                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300/80 text-[10px]"
                                                                : "bg-slate-100 text-slate-500 border border-slate-200 text-[10px] line-through"
                                                        }
                                                    >
                                                        {gp.status === "issued" ? (
                                                            <span className="flex items-center gap-1.5">
                                                                <span className="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse" />
                                                                Pending Exit
                                                            </span>
                                                        ) : gp.status === "departed" ? (
                                                            "Departed"
                                                        ) : (
                                                            "Cancelled"
                                                        )}
                                                    </Badge>
                                                </TableCell>
                                                <TableCell className="text-right space-x-1.5">
                                                    <Button
                                                        variant="ghost"
                                                        size="sm"
                                                        onClick={() =>
                                                            printSlip("Student Early Departure Gate Pass", gp.pass_number, [
                                                                ["Student Name", gp.student_name || ""],
                                                                ["Admission No", gp.student_enrollment_id || ""],
                                                                ["Class & Section", gp.student_class_section || ""],
                                                                ["Reason for Exit", gp.reason_category_display || ""],
                                                                ["Reason Details", gp.reason_details || "N/A"],
                                                                ["Picked Up By", `${gp.picked_up_by_name} (${gp.relationship_display})`],
                                                                ["Phone", gp.picked_up_by_phone],
                                                                ["Authorized By", gp.authorized_by_staff_name || "Administration"],
                                                                ["Departure Date/Time", new Date(gp.departure_time).toLocaleString()],
                                                            ])
                                                        }
                                                        className="h-8 px-2 text-xs text-slate-600 hover:text-slate-900 cursor-pointer"
                                                        title="Print Gate Pass Slip"
                                                    >
                                                        <Printer className="h-3.5 w-3.5 mr-1" />
                                                        Slip
                                                    </Button>
                                                    {gp.status === "issued" && can("issue_gate_pass") && (
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            onClick={() => setGatePassToExit(gp)}
                                                            className="h-8 px-2.5 text-xs text-emerald-600 hover:text-emerald-700 border-emerald-200 hover:bg-emerald-50 cursor-pointer font-semibold"
                                                        >
                                                            Gate Exit
                                                        </Button>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })
                                )}
                            </TableBody>
                        </Table>
                    </TableShell>
                </div>
            )}

            {/* TAB 3: POSTAL & COURIER LOG */}
            {activeTab === "postal" && (
                <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                        <div className="flex flex-wrap items-center gap-3">
                            <div className="relative">
                                <Search className="h-4 w-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                <Input
                                    type="text"
                                    placeholder="Search tracking #, sender, recipient..."
                                    value={postalSearch}
                                    onChange={(e) => setPostalSearch(e.target.value)}
                                    className="pl-9 h-9 text-xs w-64 rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                                />
                            </div>
                            <select
                                value={postalType}
                                onChange={(e) => setPostalType(e.target.value)}
                                className="h-9 px-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300"
                            >
                                <option value="">All Types (Inward & Outward)</option>
                                <option value="inward">Inward (Received)</option>
                                <option value="outward">Outward (Dispatched)</option>
                            </select>
                        </div>
                        <div className="text-xs text-slate-500 font-semibold">
                            {postalRecords.length} postal dispatches logged
                        </div>
                    </div>

                    <TableShell>
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-slate-50/75 dark:bg-slate-900/60">
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Type</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Tracking #</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Subject / Title</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">From (Sender)</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">To (Recipient)</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Courier Company</TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300">Date</TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {isLoadingPostal ? (
                                    <TableRow>
                                        <TableCell colSpan={7} className="py-12 text-center text-xs text-slate-400">
                                            Loading postal records...
                                        </TableCell>
                                    </TableRow>
                                ) : postalRecords.length === 0 ? (
                                    <TableRow>
                                        <TableCell colSpan={7} className="py-12 text-center text-xs text-slate-400">
                                            No courier or postal records logged.
                                        </TableCell>
                                    </TableRow>
                                ) : (
                                    postalRecords.map((p) => (
                                        <TableRow key={p.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                            <TableCell>
                                                <Badge
                                                    className={
                                                        p.record_type === "inward"
                                                            ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-300/80 text-[10px] uppercase font-bold"
                                                            : "bg-sky-50 text-sky-700 dark:bg-sky-950 dark:text-sky-300 border border-sky-300/80 text-[10px] uppercase font-bold"
                                                    }
                                                >
                                                    {p.record_type}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="font-mono text-xs font-semibold text-slate-700 dark:text-slate-300">
                                                {p.tracking_number || "—"}
                                            </TableCell>
                                            <TableCell>
                                                <div className="font-bold text-xs text-slate-900 dark:text-white">{p.title}</div>
                                                {p.notes && <div className="text-[11px] text-slate-400 mt-0.5">{p.notes}</div>}
                                            </TableCell>
                                            <TableCell className="text-xs text-slate-700 dark:text-slate-300 font-medium">
                                                {p.from_title}
                                            </TableCell>
                                            <TableCell className="text-xs text-slate-700 dark:text-slate-300 font-medium">
                                                {p.to_title}
                                            </TableCell>
                                            <TableCell className="text-xs text-slate-500">
                                                {p.courier_company || "—"}
                                            </TableCell>
                                            <TableCell className="text-xs text-slate-500 whitespace-nowrap">
                                                {p.dispatch_date}
                                            </TableCell>
                                        </TableRow>
                                    ))
                                )}
                            </TableBody>
                        </Table>
                    </TableShell>
                </div>
            )}

            {/* MODAL 1: CHECK IN VISITOR */}
            {isVisitorModalOpen && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                            Check In Visitor (Issue Badge)
                        </h2>
                        <form onSubmit={handleCreateVisitor} className="space-y-3.5">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Visitor Name *
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="Full name"
                                        value={visitorForm.visitor_name}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, visitor_name: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Phone Number *
                                    </label>
                                    <input
                                        type="tel"
                                        required
                                        placeholder="Mobile no."
                                        value={visitorForm.phone}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, phone: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        ID Proof Type
                                    </label>
                                    <select
                                        value={visitorForm.id_proof_type}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, id_proof_type: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="aadhaar">Aadhaar Card</option>
                                        <option value="driving_license">Driving License</option>
                                        <option value="voter_id">Voter ID</option>
                                        <option value="pan">PAN Card</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        ID Proof Number
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="Card / license number"
                                        value={visitorForm.id_proof_number}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, id_proof_number: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Purpose of Visit *
                                    </label>
                                    <select
                                        value={visitorForm.purpose}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, purpose: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="parent_meeting">Meet Teacher / Staff</option>
                                        <option value="principal_meeting">Meet Principal / Management</option>
                                        <option value="admission_inquiry">Admission Inquiry</option>
                                        <option value="fee_payment">Fee Payment / Accounts</option>
                                        <option value="vendor_delivery">Vendor / Delivery</option>
                                        <option value="document_submission">Document Submission</option>
                                        <option value="official_inspection">Education Dept / Board</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Person to Meet
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="Staff or student name"
                                        value={visitorForm.person_to_meet_name}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, person_to_meet_name: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-3 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Badge #
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="e.g. V-04"
                                        value={visitorForm.badge_number}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, badge_number: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm font-mono"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Vehicle #
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="e.g. DL-01-AB"
                                        value={visitorForm.vehicle_number}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, vehicle_number: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Persons Count
                                    </label>
                                    <input
                                        type="number"
                                        min={1}
                                        value={visitorForm.number_of_visitors}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, number_of_visitors: parseInt(e.target.value) || 1 })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                                <button
                                    type="button"
                                    onClick={() => setIsVisitorModalOpen(false)}
                                    className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium"
                                >
                                    Check In Visitor
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* MODAL 2: CHECK OUT VISITOR */}
            {visitorToCheckOut && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                            <LogOut className="h-5 w-5 text-sky-600" />
                            Check Out: {visitorToCheckOut.visitor_name}
                        </h2>
                        <p className="text-sm text-slate-500">
                            Confirm that badge #{visitorToCheckOut.badge_number || "N/A"} has been returned at the security gate.
                        </p>
                        <div>
                            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                Exit Remarks / Notes (Optional)
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. Left campus via Gate 1"
                                value={checkOutRemarks}
                                onChange={(e) => setCheckOutRemarks(e.target.value)}
                                className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                            />
                        </div>
                        <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                            <button
                                type="button"
                                onClick={() => setVisitorToCheckOut(null)}
                                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                            >
                                Back
                            </button>
                            <button
                                type="button"
                                onClick={handleCheckOut}
                                className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium"
                            >
                                Confirm Check Out
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL 3: ISSUE GATE PASS */}
            {isGatePassModalOpen && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                            <LogOut className="h-5 w-5 text-amber-600" />
                            Issue Student Early Departure Gate Pass
                        </h2>
                        <form onSubmit={handleCreateGatePass} className="space-y-3.5">
                            <div>
                                <label htmlFor="gp-student" className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                    Student *
                                </label>
                                <div className="mt-1">
                                    <StudentPicker
                                        id="gp-student"
                                        required
                                        value={gatePassStudent}
                                        onChange={(student) => {
                                            setGatePassStudent(student);
                                            setGatePassForm({ ...gatePassForm, student: student?.id ?? "" });
                                        }}
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Reason Category *
                                    </label>
                                    <select
                                        value={gatePassForm.reason_category}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, reason_category: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="illness">Medical / Sickness / Fever</option>
                                        <option value="family_emergency">Family Emergency</option>
                                        <option value="doctor_appointment">Doctor Appointment</option>
                                        <option value="event_tournament">Sports / Tournament</option>
                                        <option value="authorized_early_leave">Early Departure</option>
                                        <option value="other">Other</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Relationship *
                                    </label>
                                    <select
                                        value={gatePassForm.relationship}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, relationship: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="father">Father</option>
                                        <option value="mother">Mother</option>
                                        <option value="guardian">Guardian</option>
                                        <option value="sibling">Brother / Sister</option>
                                        <option value="authorized_relative">Authorized Relative / Driver</option>
                                        <option value="self">Self (Parent Consent Provided)</option>
                                    </select>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Picked Up By (Name) *
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="Full name of person"
                                        value={gatePassForm.picked_up_by_name}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, picked_up_by_name: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Phone Number *
                                    </label>
                                    <input
                                        type="tel"
                                        required
                                        placeholder="Mobile no."
                                        value={gatePassForm.picked_up_by_phone}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, picked_up_by_phone: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                    Reason Details
                                </label>
                                <textarea
                                    rows={2}
                                    placeholder="Explain symptoms, doctor note, or parent phone confirmation..."
                                    value={gatePassForm.reason_details}
                                    onChange={(e) => setGatePassForm({ ...gatePassForm, reason_details: e.target.value })}
                                    className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                />
                            </div>
                            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                                <button
                                    type="button"
                                    onClick={() => setIsGatePassModalOpen(false)}
                                    className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white rounded-lg text-sm font-medium"
                                >
                                    Issue Pass
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

            {/* MODAL 4: CONFIRM GATE EXIT */}
            {gatePassToExit && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-md w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                            <CheckCircle2 className="h-5 w-5 text-emerald-600" />
                            Confirm Student Gate Exit
                        </h2>
                        <p className="text-sm text-slate-500">
                            Confirm that student <strong>{gatePassToExit.student_name}</strong> is physically departing with{" "}
                            <strong>{gatePassToExit.picked_up_by_name}</strong> ({gatePassToExit.relationship_display}).
                        </p>
                        <div>
                            <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                Gate Security Note (Optional)
                            </label>
                            <input
                                type="text"
                                placeholder="e.g. ID verified, exited through Main Gate"
                                value={gateSecurityNote}
                                onChange={(e) => setGateSecurityNote(e.target.value)}
                                className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                            />
                        </div>
                        <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                            <button
                                type="button"
                                onClick={() => setGatePassToExit(null)}
                                className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                            >
                                Back
                            </button>
                            <button
                                type="button"
                                onClick={handleConfirmExit}
                                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium"
                            >
                                Confirm Departure
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* MODAL 5: LOG COURIER */}
            {isPostalModalOpen && (
                <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
                    <div className="bg-white dark:bg-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-xl border border-slate-200 dark:border-slate-700 space-y-4">
                        <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">
                            Log Postal / Courier Dispatch
                        </h2>
                        <form onSubmit={handleCreatePostal} className="space-y-3.5">
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Type *
                                    </label>
                                    <select
                                        value={postalForm.record_type}
                                        onChange={(e) => setPostalForm({ ...postalForm, record_type: e.target.value as any })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    >
                                        <option value="inward">Inward (Received)</option>
                                        <option value="outward">Outward (Dispatched)</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Tracking / Consignment #
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="Speed post or courier barcode"
                                        value={postalForm.tracking_number}
                                        onChange={(e) => setPostalForm({ ...postalForm, tracking_number: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm font-mono"
                                    />
                                </div>
                            </div>
                            <div>
                                <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                    Subject / Parcel Title *
                                </label>
                                <input
                                    type="text"
                                    required
                                    placeholder="e.g. CBSE Affiliation Certificate, Transfer Certificate envelope"
                                    value={postalForm.title}
                                    onChange={(e) => setPostalForm({ ...postalForm, title: e.target.value })}
                                    className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                />
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        From (Sender) *
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="Sender name or organization"
                                        value={postalForm.from_title}
                                        onChange={(e) => setPostalForm({ ...postalForm, from_title: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        To (Recipient) *
                                    </label>
                                    <input
                                        type="text"
                                        required
                                        placeholder="Recipient name or dept"
                                        value={postalForm.to_title}
                                        onChange={(e) => setPostalForm({ ...postalForm, to_title: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-3">
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Courier Service
                                    </label>
                                    <input
                                        type="text"
                                        placeholder="e.g. India Post, BlueDart, DTDC"
                                        value={postalForm.courier_company}
                                        onChange={(e) => setPostalForm({ ...postalForm, courier_company: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                                <div>
                                    <label className="text-xs font-semibold text-slate-600 dark:text-slate-400">
                                        Date
                                    </label>
                                    <input
                                        type="date"
                                        value={postalForm.dispatch_date}
                                        onChange={(e) => setPostalForm({ ...postalForm, dispatch_date: e.target.value })}
                                        className="w-full mt-1 px-3 py-2 bg-slate-50 dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg text-sm"
                                    />
                                </div>
                            </div>
                            <div className="flex justify-end gap-2.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                                <button
                                    type="button"
                                    onClick={() => setIsPostalModalOpen(false)}
                                    className="px-4 py-2 text-sm text-slate-600 hover:text-slate-800 dark:text-slate-400"
                                >
                                    Cancel
                                </button>
                                <button
                                    type="submit"
                                    className="px-4 py-2 bg-sky-600 hover:bg-sky-700 text-white rounded-lg text-sm font-medium"
                                >
                                    Save Postal Entry
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
}

