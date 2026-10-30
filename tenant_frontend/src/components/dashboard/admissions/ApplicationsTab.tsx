"use client";

import React, { useState } from "react";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Pagination } from "@/components/ui/pagination";
import { useApplications } from "@/hooks/useAdmissions";
import { useAcademicLevels, useAcademicYears } from "@/hooks/useAcademics";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { AdmissionApplication, ApplicationStatus } from "@/types/Admissions";
import { usePermissions } from "@/providers/PermissionProvider";
import ApplicationDetailDrawer from "./ApplicationDetailDrawer";
import NewApplicationDialog from "./NewApplicationDialog";
import {
    Search,
    Plus,
    Calendar,
    Phone,
    User,
    ChevronRight,
    Loader2,
    GraduationCap,
    Clock,
    X,
    MoreHorizontal,
    Eye,
} from "lucide-react";

const STATUS_FILTER_OPTIONS: { label: string; value: string }[] = [
    { label: "All Statuses", value: "all" },
    { label: "Submitted", value: "submitted" },
    { label: "Under Review", value: "under_review" },
    { label: "Docs Pending", value: "documents_pending" },
    { label: "Docs Verified", value: "documents_verified" },
    { label: "Assessment Pending", value: "assessment_pending" },
    { label: "Approved", value: "approved" },
    { label: "Waitlisted", value: "waitlisted" },
    { label: "Rejected", value: "rejected" },
    { label: "Offer Accepted", value: "offer_accepted" },
    { label: "Enrolled", value: "enrolled" },
];

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name?: string | null) {
    if (!name || typeof name !== "string") return AVATAR_PALETTES[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

function getInitials(name: string) {
    if (!name) return "AP";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
}

function formatDate(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
        // Handle date-only strings like YYYY-MM-DD cleanly without timezone shifts
        if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
            const [y, m, d] = dateStr.split("-").map(Number);
            const date = new Date(y, m - 1, d);
            return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
        }
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr.split("T")[0];
        return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
    } catch {
        return dateStr.split("T")[0];
    }
}

export default function ApplicationsTab() {
    const { can, isOwner } = usePermissions();
    const canManageApplications = isOwner || can("manage_admission_applications");

    const { selectedYear, currentYear } = useAcademicYear();
    const activeYear = selectedYear || currentYear;
    const { data: levels = [] } = useAcademicLevels();
    const { data: years = [] } = useAcademicYears();

    const [page, setPage] = useState(1);
    const PAGE_SIZE = 20;

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<string>("all");
    const [levelFilter, setLevelFilter] = useState<string>("all");
    const [yearFilter, setYearFilter] = useState<string>("all");

    const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [newAppOpen, setNewAppOpen] = useState(false);

    const {
        data,
        isLoading,
    } = useApplications({
        search: search || undefined,
        status: statusFilter === "all" ? undefined : (statusFilter as ApplicationStatus),
        level: levelFilter === "all" ? undefined : levelFilter,
        academic_year: yearFilter === "all" ? undefined : yearFilter,
        page,
        page_size: PAGE_SIZE,
    });

    const applications = data?.results || [];
    const totalCount = data?.count || 0;

    const handleSearchChange = (val: string) => {
        setSearch(val);
        setPage(1);
    };

    const handleStatusChange = (val: string) => {
        setStatusFilter(val);
        setPage(1);
    };

    const handleLevelChange = (val: string) => {
        setLevelFilter(val);
        setPage(1);
    };

    const handleYearChange = (val: string) => {
        setYearFilter(val);
        setPage(1);
    };

    const handleResetFilters = () => {
        setSearch("");
        setStatusFilter("all");
        setLevelFilter("all");
        setYearFilter("all");
        setPage(1);
    };

    const handleOpenDetail = (id: string) => {
        setSelectedApplicationId(id);
        setDrawerOpen(true);
    };

    const getStatusBadge = (status: ApplicationStatus) => {
        switch (status) {
            case "draft":
                return <Badge variant="outline" className="font-semibold text-xs capitalize">Draft</Badge>;
            case "submitted":
                return <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 font-semibold text-xs">Submitted</Badge>;
            case "under_review":
                return <Badge className="bg-indigo-50 text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300 border border-indigo-300/80 font-semibold text-xs">Under Review</Badge>;
            case "documents_pending":
                return <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-xs">Docs Pending</Badge>;
            case "documents_verified":
                return <Badge className="bg-teal-50 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300 border border-teal-300/80 font-semibold text-xs">Docs Verified</Badge>;
            case "assessment_pending":
                return <Badge className="bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-300/80 font-semibold text-xs">Assessment Pending</Badge>;
            case "approved":
                return <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-xs">Approved</Badge>;
            case "waitlisted":
                return <Badge className="bg-orange-50 text-orange-700 dark:bg-orange-950/60 dark:text-orange-300 border border-orange-300/80 font-semibold text-xs">Waitlisted</Badge>;
            case "rejected":
                return <Badge className="bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300/80 font-semibold text-xs">Rejected</Badge>;
            case "offer_accepted":
                return <Badge className="bg-cyan-50 text-cyan-700 dark:bg-cyan-950/60 dark:text-cyan-300 border border-cyan-300/80 font-semibold text-xs">Offer Accepted</Badge>;
            case "enrolled":
                return <Badge className="bg-emerald-600 text-white border-none font-bold text-xs">Enrolled</Badge>;
            case "withdrawn":
                return <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-none font-semibold text-xs">Withdrawn</Badge>;
            default:
                return <Badge variant="outline" className="text-xs">{status}</Badge>;
        }
    };

    return (
        <div className="space-y-4">
            {/* 1. High-Density Unified Filter Bar (Zero Dead Space) */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col md:flex-row gap-2.5 items-center justify-between">
                {/* Search Input */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        aria-label="Search by name, app #, enq #, phone..."
                        placeholder="Search by student name, application number, phone..."
                        value={search}
                        onChange={(e) => handleSearchChange(e.target.value)}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 bg-slate-50/50 dark:bg-slate-950/50"
                    />
                    {search && (
                        <button
                            onClick={() => handleSearchChange("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                {/* Grade & Year Dropdowns */}
                <div className="flex items-center gap-2 w-full md:w-auto shrink-0 justify-between sm:justify-start">
                    {/* Grade Level Select */}
                    <div className="w-38 sm:w-44">
                        <Select value={levelFilter} onValueChange={handleLevelChange}>
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Grades" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Grades / Levels</SelectItem>
                                {levels.map((lvl) => (
                                    <SelectItem key={lvl.id} value={lvl.id} className="text-xs">
                                        {lvl.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Academic Year Select */}
                    <div className="w-36 sm:w-40">
                        <Select value={yearFilter} onValueChange={handleYearChange}>
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Years" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Years</SelectItem>
                                {years.map((y) => (
                                    <SelectItem key={y.id} value={y.id} className="text-xs">
                                        {y.name} {y.is_current ? "(Current)" : ""}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {(levelFilter !== "all" || yearFilter !== "all" || search) && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={handleResetFilters}
                            className="h-9 px-2 text-xs text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40"
                        >
                            Reset
                        </Button>
                    )}
                </div>
            </div>

            {/* 2. Streamlined Status Funnel Bar (Eliminated Duplicate Status Dropdown) */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs scrollbar-none">
                {STATUS_FILTER_OPTIONS.map((opt) => {
                    const active = statusFilter === opt.value;
                    return (
                        <button
                            key={opt.value}
                            type="button"
                            onClick={() => handleStatusChange(opt.value)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all cursor-pointer ${
                                active
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                            }`}
                        >
                            {opt.label}
                        </button>
                    );
                })}
            </div>

            {/* 3. Applications Table */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-2xs overflow-hidden">
                {isLoading ? (
                    <div className="p-16 flex flex-col items-center justify-center gap-3">
                        <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
                        <span className="text-xs text-slate-500 font-medium">Loading applicant pipeline...</span>
                    </div>
                ) : applications.length === 0 ? (
                    <div className="p-16 text-center space-y-3">
                        <div className="w-12 h-12 mx-auto rounded-xl bg-sky-50 dark:bg-sky-900/30 flex items-center justify-center text-sky-600 dark:text-sky-400">
                            <GraduationCap className="w-6 h-6" />
                        </div>
                        <h3 className="text-sm font-bold text-slate-800 dark:text-white">
                            No applications found
                        </h3>
                        <p className="text-xs text-slate-500 max-w-sm mx-auto">
                            {search || statusFilter !== "all" || levelFilter !== "all"
                                ? "No applications matched the current filters. Try resetting or adjusting your search."
                                : "Get started by submitting a new prospective student application."}
                        </p>
                        {canManageApplications && (
                            <Button
                                onClick={() => setNewAppOpen(true)}
                                size="sm"
                                className="rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold gap-1.5 mt-2"
                            >
                                <Plus className="h-3.5 w-3.5" /> Submit First Application
                            </Button>
                        )}
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="py-3.5 pl-5 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        App Number & Date
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Applicant Name
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Applied Grade & Year
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Guardian Contact
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Stage Status
                                    </TableHead>
                                    <TableHead className="text-right pr-5 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {applications.map((app) => {
                                    const fullName = `${app.first_name} ${app.middle_name ? app.middle_name + " " : ""}${app.last_name}`;
                                    const guardianName = `${app.guardian_first_name} ${app.guardian_last_name}`;
                                    const avatarStyle = getAvatarStyle(fullName);
                                    const initials = getInitials(fullName);

                                    return (
                                        <TableRow
                                            key={app.id}
                                            onClick={() => handleOpenDetail(app.id)}
                                            className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 cursor-pointer transition-colors border-b border-slate-100 dark:border-slate-800/70"
                                        >
                                            {/* App Number & Date */}
                                            <TableCell className="py-3 pl-5">
                                                <code className="text-xs font-mono font-bold text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/60 px-1.5 py-0.5 rounded border border-sky-200 dark:border-sky-800">
                                                    {app.application_number}
                                                </code>
                                                <div className="text-[10px] text-slate-400 flex items-center gap-1 mt-1 font-medium">
                                                    <Calendar className="w-3 h-3" />
                                                    <span>{formatDate(app.submission_date || app.created_at)}</span>
                                                </div>
                                            </TableCell>

                                            {/* Applicant with Colorful Avatar */}
                                            <TableCell className="py-3">
                                                <div className="flex items-center gap-2.5">
                                                    <div
                                                        className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                    >
                                                        {initials}
                                                    </div>
                                                    <div>
                                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {fullName}
                                                        </div>
                                                        <div className="text-[10px] text-slate-400 capitalize">
                                                            {app.gender} • DOB: {formatDate(app.date_of_birth)}
                                                        </div>
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Applied Grade Level */}
                                            <TableCell className="py-3">
                                                <span className="font-medium text-xs text-slate-800 dark:text-slate-200">
                                                    {app.level_name || "Level not set"}
                                                </span>
                                                <div className="text-[10px] text-slate-400">
                                                    AY: {app.academic_year}
                                                </div>
                                            </TableCell>

                                            {/* Guardian Contact */}
                                            <TableCell className="py-3">
                                                <div className="font-medium text-xs text-slate-800 dark:text-slate-200">
                                                    {guardianName}
                                                </div>
                                                <div className="text-[10px] text-slate-400 flex items-center gap-1 capitalize">
                                                    <Phone className="w-3 h-3 text-slate-400" />
                                                    <span>{app.guardian_phone}{app.guardian_relationship ? ` (${app.guardian_relationship})` : ""}</span>
                                                </div>
                                            </TableCell>

                                            {/* Stage Status */}
                                            <TableCell className="py-3">
                                                {getStatusBadge(app.status)}
                                            </TableCell>

                                            {/* Actions */}
                                            <TableCell className="text-right pr-5 py-3" onClick={(e) => e.stopPropagation()}>
                                                <Button
                                                    variant="ghost"
                                                    size="sm"
                                                    onClick={() => handleOpenDetail(app.id)}
                                                    className="h-8 px-2.5 text-xs text-slate-600 hover:text-sky-600 hover:bg-slate-100 dark:hover:bg-slate-800"
                                                >
                                                    <Eye className="w-3.5 h-3.5 mr-1" />
                                                    <span>Review</span>
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </div>
                )}

                {/* Enterprise Pagination Footer */}
                {!isLoading && totalCount > 0 && (
                    <Pagination
                        page={page}
                        pageSize={PAGE_SIZE}
                        count={totalCount}
                        onPageChange={setPage}
                        className="border-t border-slate-200/80 dark:border-slate-800 px-4 py-3 bg-slate-50/40 dark:bg-slate-900/40"
                    />
                )}
            </div>

            {/* Application Detail Drawer */}
            <ApplicationDetailDrawer
                applicationId={selectedApplicationId}
                open={drawerOpen}
                onOpenChange={setDrawerOpen}
            />

            {/* New Application Dialog */}
            <NewApplicationDialog
                open={newAppOpen}
                onOpenChange={setNewAppOpen}
            />
        </div>
    );
}
