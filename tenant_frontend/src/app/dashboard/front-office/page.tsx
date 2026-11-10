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
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
    Dialog,
    DialogContent,
    DialogBody,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { FormGrid, FormGrid3, FormFieldWrapper } from "@/components/ui/form-layout";
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
import { Avatar } from "@/components/ui/avatar";

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
                        <Button
                            onClick={() => setIsVisitorModalOpen(true)}
                            size="sm"
                            className="gap-1.5"
                        >
                            <Plus className="h-4 w-4" />
                            <span>Check In Visitor</span>
                        </Button>
                    )}
                    {can("issue_gate_pass") && (
                        <Button
                            onClick={() => setIsGatePassModalOpen(true)}
                            size="sm"
                            className="gap-1.5 bg-amber-600 hover:bg-amber-500 text-white"
                        >
                            <LogOut className="h-4 w-4" />
                            <span>Issue Gate Pass</span>
                        </Button>
                    )}
                    {can("manage_postal_records") && (
                        <Button
                            onClick={() => setIsPostalModalOpen(true)}
                            variant="outline"
                            size="sm"
                            className="gap-1.5"
                        >
                            <Mail className="h-4 w-4" />
                            <span>Log Courier</span>
                        </Button>
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
                                        return (
                                            <TableRow key={v.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                                <TableCell className="font-mono text-xs font-bold text-sky-600 dark:text-sky-400">
                                                    {v.pass_number}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2.5">
                                                        <Avatar name={v.visitor_name} size="sm" shape="square" />
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
                                        return (
                                            <TableRow key={gp.id} className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40">
                                                <TableCell className="font-mono text-xs font-bold text-amber-600 dark:text-amber-400">
                                                    {gp.pass_number}
                                                </TableCell>
                                                <TableCell>
                                                    <div className="flex items-center gap-2.5">
                                                        <Avatar name={gp.student_name || "Student"} size="sm" shape="square" />
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
            <Dialog open={isVisitorModalOpen} onOpenChange={setIsVisitorModalOpen}>
                <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<ShieldCheck className="w-5 h-5 text-sky-600" />}
                        title="Check In Visitor"
                        subtitle="Issue temporary visitor badge and record contact details."
                        onClose={() => setIsVisitorModalOpen(false)}
                    />
                    <form onSubmit={handleCreateVisitor} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormGrid>
                                <FormFieldWrapper label="Visitor Name" htmlFor="vis-name" required>
                                    <Input
                                        id="vis-name"
                                        type="text"
                                        required
                                        placeholder="Full name"
                                        value={visitorForm.visitor_name}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, visitor_name: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Phone Number" htmlFor="vis-phone" required>
                                    <Input
                                        id="vis-phone"
                                        type="tel"
                                        required
                                        placeholder="Mobile no."
                                        value={visitorForm.phone}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, phone: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="ID Proof Type" htmlFor="vis-id-type">
                                    <select
                                        id="vis-id-type"
                                        value={visitorForm.id_proof_type}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, id_proof_type: e.target.value })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="aadhaar">Aadhaar Card</option>
                                        <option value="driving_license">Driving License</option>
                                        <option value="voter_id">Voter ID</option>
                                        <option value="pan">PAN Card</option>
                                        <option value="other">Other</option>
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="ID Proof Number" htmlFor="vis-id-num">
                                    <Input
                                        id="vis-id-num"
                                        type="text"
                                        placeholder="Card / license number"
                                        value={visitorForm.id_proof_number}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, id_proof_number: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Purpose of Visit" htmlFor="vis-purpose" required>
                                    <select
                                        id="vis-purpose"
                                        value={visitorForm.purpose}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, purpose: e.target.value })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
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
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Person to Meet" htmlFor="vis-meet">
                                    <Input
                                        id="vis-meet"
                                        type="text"
                                        placeholder="Staff or student name"
                                        value={visitorForm.person_to_meet_name}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, person_to_meet_name: e.target.value })}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                            <FormGrid3>
                                <FormFieldWrapper label="Badge #" htmlFor="vis-badge">
                                    <Input
                                        id="vis-badge"
                                        type="text"
                                        placeholder="e.g. V-04"
                                        value={visitorForm.badge_number}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, badge_number: e.target.value })}
                                        className="font-mono"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Vehicle #" htmlFor="vis-vehicle">
                                    <Input
                                        id="vis-vehicle"
                                        type="text"
                                        placeholder="e.g. DL-01-AB"
                                        value={visitorForm.vehicle_number}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, vehicle_number: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Persons Count" htmlFor="vis-count">
                                    <Input
                                        id="vis-count"
                                        type="number"
                                        min={1}
                                        value={visitorForm.number_of_visitors}
                                        onChange={(e) => setVisitorForm({ ...visitorForm, number_of_visitors: parseInt(e.target.value) || 1 })}
                                    />
                                </FormFieldWrapper>
                            </FormGrid3>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsVisitorModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button type="submit">
                                Check In Visitor
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* MODAL 2: CHECK OUT VISITOR */}
            <Dialog open={!!visitorToCheckOut} onOpenChange={(open) => !open && setVisitorToCheckOut(null)}>
                <DialogContent className="max-w-md max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<LogOut className="w-5 h-5 text-sky-600" />}
                        title={`Check Out: ${visitorToCheckOut?.visitor_name || ""}`}
                        subtitle={`Confirm that badge #${visitorToCheckOut?.badge_number || "N/A"} has been returned.`}
                        onClose={() => setVisitorToCheckOut(null)}
                    />
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                        <FormFieldWrapper label="Exit Remarks / Notes (Optional)" htmlFor="checkout-remarks">
                            <Input
                                id="checkout-remarks"
                                type="text"
                                placeholder="e.g. Left campus via Gate 1"
                                value={checkOutRemarks}
                                onChange={(e) => setCheckOutRemarks(e.target.value)}
                            />
                        </FormFieldWrapper>
                    </DialogBody>
                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setVisitorToCheckOut(null)}
                        >
                            Back
                        </Button>
                        <Button
                            type="button"
                            onClick={handleCheckOut}
                        >
                            Confirm Check Out
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* MODAL 3: ISSUE GATE PASS */}
            <Dialog open={isGatePassModalOpen} onOpenChange={setIsGatePassModalOpen}>
                <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<LogOut className="w-5 h-5 text-amber-600" />}
                        title="Issue Early Departure Gate Pass"
                        subtitle="Authorize student departure with guardian or relative."
                        onClose={() => setIsGatePassModalOpen(false)}
                    />
                    <form onSubmit={handleCreateGatePass} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormFieldWrapper label="Student" htmlFor="gp-student" required helpText="Search by name or enrollment number">
                                <StudentPicker
                                    id="gp-student"
                                    required
                                    value={gatePassStudent}
                                    onChange={(student) => {
                                        setGatePassStudent(student);
                                        setGatePassForm({ ...gatePassForm, student: student?.id ?? "" });
                                    }}
                                />
                            </FormFieldWrapper>
                            <FormGrid>
                                <FormFieldWrapper label="Reason Category" htmlFor="gp-reason" required>
                                    <select
                                        id="gp-reason"
                                        value={gatePassForm.reason_category}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, reason_category: e.target.value })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="illness">Medical / Sickness / Fever</option>
                                        <option value="family_emergency">Family Emergency</option>
                                        <option value="doctor_appointment">Doctor Appointment</option>
                                        <option value="event_tournament">Sports / Tournament</option>
                                        <option value="authorized_early_leave">Early Departure</option>
                                        <option value="other">Other</option>
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Relationship" htmlFor="gp-rel" required>
                                    <select
                                        id="gp-rel"
                                        value={gatePassForm.relationship}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, relationship: e.target.value })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="father">Father</option>
                                        <option value="mother">Mother</option>
                                        <option value="guardian">Guardian</option>
                                        <option value="sibling">Brother / Sister</option>
                                        <option value="authorized_relative">Authorized Relative / Driver</option>
                                        <option value="self">Self (Parent Consent Provided)</option>
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Picked Up By (Name)" htmlFor="gp-name" required>
                                    <Input
                                        id="gp-name"
                                        type="text"
                                        required
                                        placeholder="Full name of person"
                                        value={gatePassForm.picked_up_by_name}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, picked_up_by_name: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Phone Number" htmlFor="gp-phone" required>
                                    <Input
                                        id="gp-phone"
                                        type="tel"
                                        required
                                        placeholder="Mobile no."
                                        value={gatePassForm.picked_up_by_phone}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, picked_up_by_phone: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Reason Details" htmlFor="gp-details" colSpan={2}>
                                    <Textarea
                                        id="gp-details"
                                        rows={2}
                                        placeholder="Explain symptoms, doctor note, or parent phone confirmation..."
                                        value={gatePassForm.reason_details}
                                        onChange={(e) => setGatePassForm({ ...gatePassForm, reason_details: e.target.value })}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsGatePassModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button type="submit">
                                Issue Pass
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>

            {/* MODAL 4: CONFIRM GATE EXIT */}
            <Dialog open={!!gatePassToExit} onOpenChange={(open) => !open && setGatePassToExit(null)}>
                <DialogContent className="max-w-md max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<CheckCircle2 className="w-5 h-5 text-emerald-600" />}
                        title="Confirm Student Gate Exit"
                        subtitle="Verify security release of departing student."
                        onClose={() => setGatePassToExit(null)}
                    />
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                        <p className="text-xs text-slate-500">
                            Confirm that student <strong>{gatePassToExit?.student_name}</strong> is physically departing with{" "}
                            <strong>{gatePassToExit?.picked_up_by_name}</strong> ({gatePassToExit?.relationship_display}).
                        </p>
                        <FormFieldWrapper label="Gate Security Note (Optional)" htmlFor="gate-note">
                            <Input
                                id="gate-note"
                                type="text"
                                placeholder="e.g. ID verified, exited through Main Gate"
                                value={gateSecurityNote}
                                onChange={(e) => setGateSecurityNote(e.target.value)}
                            />
                        </FormFieldWrapper>
                    </DialogBody>
                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => setGatePassToExit(null)}
                        >
                            Back
                        </Button>
                        <Button
                            type="button"
                            onClick={handleConfirmExit}
                        >
                            Confirm Departure
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>

            {/* MODAL 5: LOG COURIER */}
            <Dialog open={isPostalModalOpen} onOpenChange={setIsPostalModalOpen}>
                <DialogContent className="max-w-xl max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                    <ModalHeader
                        icon={<Mail className="w-5 h-5 text-sky-600" />}
                        title="Log Postal / Courier Dispatch"
                        subtitle="Inward parcel receipt or outward dispatch tracking."
                        onClose={() => setIsPostalModalOpen(false)}
                    />
                    <form onSubmit={handleCreatePostal} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <FormGrid>
                                <FormFieldWrapper label="Type" htmlFor="post-type" required>
                                    <select
                                        id="post-type"
                                        value={postalForm.record_type}
                                        onChange={(e) => setPostalForm({ ...postalForm, record_type: e.target.value as any })}
                                        className="flex h-9 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 px-3 py-1.5 text-xs sm:text-sm shadow-2xs transition-colors duration-150 focus-visible:border-sky-500 focus-visible:ring-2 focus-visible:ring-sky-500/20 dark:focus-visible:ring-sky-400/25 outline-none hover:border-slate-300 dark:hover:border-slate-700"
                                    >
                                        <option value="inward">Inward (Received)</option>
                                        <option value="outward">Outward (Dispatched)</option>
                                    </select>
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Tracking / Consignment #" htmlFor="post-tracking">
                                    <Input
                                        id="post-tracking"
                                        type="text"
                                        placeholder="Speed post or courier barcode"
                                        value={postalForm.tracking_number}
                                        onChange={(e) => setPostalForm({ ...postalForm, tracking_number: e.target.value })}
                                        className="font-mono"
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Subject / Parcel Title" htmlFor="post-title" required colSpan={2}>
                                    <Input
                                        id="post-title"
                                        type="text"
                                        required
                                        placeholder="e.g. CBSE Affiliation Certificate, Transfer Certificate envelope"
                                        value={postalForm.title}
                                        onChange={(e) => setPostalForm({ ...postalForm, title: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="From (Sender)" htmlFor="post-from" required>
                                    <Input
                                        id="post-from"
                                        type="text"
                                        required
                                        placeholder="Sender name or organization"
                                        value={postalForm.from_title}
                                        onChange={(e) => setPostalForm({ ...postalForm, from_title: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="To (Recipient)" htmlFor="post-to" required>
                                    <Input
                                        id="post-to"
                                        type="text"
                                        required
                                        placeholder="Recipient name or dept"
                                        value={postalForm.to_title}
                                        onChange={(e) => setPostalForm({ ...postalForm, to_title: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Courier Service" htmlFor="post-courier">
                                    <Input
                                        id="post-courier"
                                        type="text"
                                        placeholder="e.g. India Post, BlueDart, DTDC"
                                        value={postalForm.courier_company}
                                        onChange={(e) => setPostalForm({ ...postalForm, courier_company: e.target.value })}
                                    />
                                </FormFieldWrapper>
                                <FormFieldWrapper label="Date" htmlFor="post-date">
                                    <Input
                                        id="post-date"
                                        type="date"
                                        value={postalForm.dispatch_date}
                                        onChange={(e) => setPostalForm({ ...postalForm, dispatch_date: e.target.value })}
                                    />
                                </FormFieldWrapper>
                            </FormGrid>
                        </DialogBody>
                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={() => setIsPostalModalOpen(false)}
                            >
                                Cancel
                            </Button>
                            <Button type="submit">
                                Save Postal Entry
                            </Button>
                        </DialogFooter>
                    </form>
                </DialogContent>
            </Dialog>
        </div>
    );
}

