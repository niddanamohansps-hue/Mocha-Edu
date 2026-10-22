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
    Filter,
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

export default function ApplicationsTab() {
    const { can, isOwner } = usePermissions();
    const canManageApplications = isOwner || can("manage_admission_applications");

    const { selectedYear, currentYear } = useAcademicYear();
    const activeYear = selectedYear || currentYear;
    const { data: levels = [] } = useAcademicLevels();
    const { data: years = [] } = useAcademicYears();

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<string>("all");
    const [levelFilter, setLevelFilter] = useState<string>("all");
    const [yearFilter, setYearFilter] = useState<string>("all");

    const [selectedApplicationId, setSelectedApplicationId] = useState<string | null>(null);
    const [drawerOpen, setDrawerOpen] = useState(false);
    const [newAppOpen, setNewAppOpen] = useState(false);

    const {
        data: applications = [],
        isLoading,
    } = useApplications({
        search: search || undefined,
        status: statusFilter === "all" ? undefined : (statusFilter as ApplicationStatus),
        level: levelFilter === "all" ? undefined : levelFilter,
        academic_year: yearFilter === "all" ? undefined : yearFilter,
    });

    const handleOpenDetail = (id: string) => {
        setSelectedApplicationId(id);
        setDrawerOpen(true);
    };

    const getStatusBadge = (status: ApplicationStatus) => {
        switch (status) {
            case "draft":
                return <Badge variant="outline" className="font-semibold capitalize">Draft</Badge>;
            case "submitted":
                return <Badge className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border-none font-semibold">Submitted</Badge>;
            case "under_review":
                return <Badge className="bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-300 border-none font-semibold">Under Review</Badge>;
            case "documents_pending":
                return <Badge className="bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300 border-none font-semibold">Docs Pending</Badge>;
            case "documents_verified":
                return <Badge className="bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-300 border-none font-semibold">Docs Verified</Badge>;
            case "assessment_pending":
                return <Badge className="bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-300 border-none font-semibold">Assessment Pending</Badge>;
            case "approved":
                return <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300 border-none font-semibold">Approved</Badge>;
            case "waitlisted":
                return <Badge className="bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-300 border-none font-semibold">Waitlisted</Badge>;
            case "rejected":
                return <Badge className="bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300 border-none font-semibold">Rejected</Badge>;
            case "offer_accepted":
                return <Badge className="bg-cyan-100 text-cyan-800 dark:bg-cyan-900/40 dark:text-cyan-300 border-none font-semibold">Offer Accepted</Badge>;
            case "enrolled":
                return <Badge className="bg-green-600 text-white border-none font-bold">Enrolled</Badge>;
            case "withdrawn":
                return <Badge className="bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border-none font-semibold">Withdrawn</Badge>;
            default:
                return <Badge variant="outline">{status}</Badge>;
        }
    };

    return (
        <div className="space-y-6">
            {/* Header controls: Search & Filters */}
            <div className="flex flex-col gap-4">
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                    <div className="relative flex-1 max-w-md">
                        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                        <Input aria-label="Search by name, app #, enq #, phone..."
                            placeholder="Search by name, app #, enq #, phone..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            className="pl-10 h-11 bg-white dark:bg-slate-900 rounded-xl border-slate-200 dark:border-slate-800 shadow-sm"
                        />
                    </div>

                    <div className="flex items-center gap-2">
                        {canManageApplications && (
                            <Button
                                onClick={() => setNewAppOpen(true)}
                                className="h-11 px-5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold gap-2 shadow-sm"
                            >
                                <Plus className="h-4 w-4" />
                                New Application
                            </Button>
                        )}
                    </div>
                </div>

                {/* Filter Row */}
                <div className="flex flex-wrap items-center gap-2.5 pt-1">
                    <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-500 uppercase tracking-wider mr-1">
                        <Filter className="w-3.5 h-3.5" /> Filters:
                    </div>

                    {/* Status Select */}
                    <div className="w-44">
                        <Select value={statusFilter} onValueChange={setStatusFilter}>
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Statuses" />
                            </SelectTrigger>
                            <SelectContent>
                                {STATUS_FILTER_OPTIONS.map((opt) => (
                                    <SelectItem key={opt.value} value={opt.value} className="text-xs">
                                        {opt.label}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Grade Level Select */}
                    <div className="w-44">
                        <Select value={levelFilter} onValueChange={setLevelFilter}>
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Grades/Levels" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Grades/Levels</SelectItem>
                                {levels.map((lvl) => (
                                    <SelectItem key={lvl.id} value={lvl.id} className="text-xs">
                                        {lvl.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Academic Year Select */}
                    <div className="w-44">
                        <Select value={yearFilter} onValueChange={setYearFilter}>
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Academic Years" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Academic Years</SelectItem>
                                {years.map((y) => (
                                    <SelectItem key={y.id} value={y.id} className="text-xs">
                                        {y.name} {y.is_current ? "(Current)" : ""}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {(statusFilter !== "all" || levelFilter !== "all" || yearFilter !== "all" || search) && (
                        <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                                setStatusFilter("all");
                                setLevelFilter("all");
                                setYearFilter("all");
                                setSearch("");
                            }}
                            className="h-9 text-xs text-slate-500 hover:text-slate-800"
                        >
                            Reset Filters
                        </Button>
                    )}
                </div>
            </div>

            {/* Quick Status Bar / Tabs */}
            <div className="flex items-center gap-1.5 overflow-x-auto pb-2 scrollbar-none">
                {STATUS_FILTER_OPTIONS.map((opt) => {
                    const active = statusFilter === opt.value;
                    return (
                        <button
                            key={opt.value}
                            type="button"
                            onClick={() => setStatusFilter(opt.value)}
                            className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-all ${
                                active
                                    ? "bg-blue-600 text-white shadow-sm"
                                    : "bg-slate-100 hover:bg-slate-200 text-slate-600 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300"
                            }`}
                        >
                            {opt.label}
                        </button>
                    );
                })}
            </div>

            {/* Applications Table */}
            <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                {isLoading ? (
                    <div className="p-16 flex flex-col items-center justify-center gap-3">
                        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                        <span className="text-sm text-slate-500 font-medium">Loading applications...</span>
                    </div>
                ) : applications.length === 0 ? (
                    <div className="p-16 text-center space-y-3">
                        <div className="w-14 h-14 mx-auto rounded-2xl bg-blue-50 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 dark:text-blue-400">
                            <GraduationCap className="w-7 h-7" />
                        </div>
                        <h3 className="text-base font-bold text-slate-800 dark:text-white">
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
                                className="rounded-xl bg-blue-600 hover:bg-blue-700 text-white text-xs font-semibold gap-1.5 mt-2"
                            >
                                <Plus className="h-3.5 w-3.5" /> Submit First Application
                            </Button>
                        )}
                    </div>
                ) : (
                    <div className="overflow-x-auto">
                        <Table>
                            <TableHeader>
                                <TableRow className="bg-slate-50/75 dark:bg-slate-800/50 hover:bg-transparent">
                                    <TableHead className="font-bold text-xs text-slate-600 dark:text-slate-300 py-3.5">
                                        App Number / Date
                                    </TableHead>
                                    <TableHead className="font-bold text-xs text-slate-600 dark:text-slate-300 py-3.5">
                                        Applicant
                                    </TableHead>
                                    <TableHead className="font-bold text-xs text-slate-600 dark:text-slate-300 py-3.5">
                                        Grade Level / Year
                                    </TableHead>
                                    <TableHead className="font-bold text-xs text-slate-600 dark:text-slate-300 py-3.5">
                                        Guardian
                                    </TableHead>
                                    <TableHead className="font-bold text-xs text-slate-600 dark:text-slate-300 py-3.5">
                                        Reviewer
                                    </TableHead>
                                    <TableHead className="font-bold text-xs text-slate-600 dark:text-slate-300 py-3.5">
                                        Status
                                    </TableHead>
                                    <TableHead className="text-right font-bold text-xs text-slate-600 dark:text-slate-300 py-3.5 pr-6">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {applications.map((app) => {
                                    const fullName = `${app.first_name} ${app.middle_name ? app.middle_name + " " : ""}${app.last_name}`;
                                    const guardianName = `${app.guardian_first_name} ${app.guardian_last_name}`;
                                    return (
                                        <TableRow
                                            key={app.id}
                                            onClick={() => handleOpenDetail(app.id)}
                                            className="hover:bg-slate-50/80 dark:hover:bg-slate-800/40 cursor-pointer transition-colors"
                                        >
                                            <TableCell className="py-3.5">
                                                <div className="font-mono text-xs font-bold text-blue-600 dark:text-blue-400">
                                                    {app.application_number}
                                                </div>
                                                <div className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                                                    <Calendar className="w-3 h-3" />
                                                    {app.submission_date || app.created_at.split("T")[0]}
                                                </div>
                                            </TableCell>

                                            <TableCell className="py-3.5">
                                                <div className="font-bold text-xs text-slate-800 dark:text-slate-100">
                                                    {fullName}
                                                </div>
                                                <div className="text-[11px] text-slate-400 capitalize">
                                                    {app.gender} • DOB: {app.date_of_birth}
                                                </div>
                                            </TableCell>

                                            <TableCell className="py-3.5">
                                                <div className="font-semibold text-xs text-slate-700 dark:text-slate-200">
                                                    {app.level_name || "Level not set"}
                                                </div>
                                                <div className="text-[11px] text-slate-400">
                                                    AY: {app.academic_year}
                                                </div>
                                            </TableCell>

                                            <TableCell className="py-3.5">
                                                <div className="font-semibold text-xs text-slate-800 dark:text-slate-200">
                                                    {guardianName}
                                                </div>
                                                <div className="text-[11px] text-slate-400 flex items-center gap-1 capitalize">
                                                    <Phone className="w-3 h-3 text-slate-400" />
                                                    {app.guardian_phone} ({app.guardian_relationship})
                                                </div>
                                            </TableCell>

                                            <TableCell className="py-3.5">
                                                {app.assigned_reviewer_name ? (
                                                    <span className="text-xs font-semibold text-slate-700 dark:text-slate-200 flex items-center gap-1">
                                                        <User className="w-3 h-3 text-slate-400" />
                                                        {app.assigned_reviewer_name}
                                                    </span>
                                                ) : (
                                                    <span className="text-xs text-slate-400 italic">
                                                        Unassigned
                                                    </span>
                                                )}
                                            </TableCell>

                                            <TableCell className="py-3.5">
                                                {getStatusBadge(app.status)}
                                            </TableCell>

                                            <TableCell className="text-right py-3.5 pr-6">
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        handleOpenDetail(app.id);
                                                    }}
                                                    className="h-8 px-3 rounded-lg text-xs font-bold text-blue-600 hover:text-blue-700 hover:bg-blue-50 dark:hover:bg-blue-900/30 gap-1"
                                                >
                                                    Review
                                                    <ChevronRight className="w-3.5 h-3.5" />
                                                </Button>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </div>
                )}
            </div>

            {/* Application Detail Drawer / Dialog */}
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
