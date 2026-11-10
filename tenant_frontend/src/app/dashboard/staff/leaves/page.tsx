"use client";

import React, { useState, useMemo } from "react";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import {
    useAllLeaveBalances,
    useApproverInbox,
    useMyLeaveApplications,
    useMyLeaveBalances,
} from "@/hooks/useStaffLeaves";
import { LeaveApplication } from "@/types/Leave";
import { LeaveBalanceCards } from "@/components/dashboard/staff/leaves/LeaveBalanceCards";
import { ApplyLeaveDialog } from "@/components/dashboard/staff/leaves/ApplyLeaveDialog";
import { LeaveDetailModal } from "@/components/dashboard/staff/leaves/LeaveDetailModal";
import { LeaveDecisionModal } from "@/components/dashboard/staff/leaves/LeaveDecisionModal";
import { AffectedPeriodsModal } from "@/components/dashboard/staff/leaves/AffectedPeriodsModal";
import { LeaveTypesConfigTab } from "@/components/dashboard/staff/leaves/LeaveTypesConfigTab";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Calendar,
    Clock,
    Plus,
    FileText,
    CheckCircle2,
    XCircle,
    Eye,
    Settings,
    UserCheck,
    Loader2,
    Inbox,
    Search,
    X,
    Sparkles,
    ShieldAlert,
    AlertCircle,
    CalendarCheck,
    Check,
} from "lucide-react";
import { format } from "date-fns";
import { EmptyState } from "@/components/feedback/EmptyState";

function formatDateSafe(dateStr?: string | null) {
    if (!dateStr) return "—";
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr.split("T")[0];
        return format(d, "MMM d, yyyy");
    } catch {
        return dateStr.split("T")[0];
    }
}

export default function StaffLeavesPage() {
    const { can, isOwner } = usePermissions();
    const { selectedYear } = useAcademicYear();

    const canManageLeaves = isOwner || can("manage_staff_leaves");
    const canManageTypes = isOwner || can("manage_leave_types");
    const canViewAll = isOwner || can("view_all_leaves") || canManageLeaves;

    const academicYear = selectedYear?.name || "";

    // Queries
    const { data: myBalances = [], isLoading: loadingBalances } = useMyLeaveBalances(academicYear);

    const [statusFilter, setStatusFilter] = useState<string>("all");
    const [mySearch, setMySearch] = useState<string>("");
    const { data: myAppsData, isLoading: loadingMyApps } = useMyLeaveApplications({
        status: statusFilter === "all" ? undefined : statusFilter,
        academic_year: academicYear,
    });
    const myApplications = myAppsData?.results || [];

    const [inboxStatus, setInboxStatus] = useState<string>("pending");
    const [inboxSearch, setInboxSearch] = useState<string>("");
    const { data: inboxData, isLoading: loadingInbox } = useApproverInbox({
        status: inboxStatus === "all" ? undefined : inboxStatus,
    });
    const inboxApplications = inboxData?.results || [];

    const [quotasSearch, setQuotasSearch] = useState<string>("");
    const { data: allBalancesData, isLoading: loadingAllBalances } = useAllLeaveBalances({
        academic_year: academicYear,
    });
    const allBalances = allBalancesData?.results || [];

    // Dialog & Modal State
    const [applyOpen, setApplyOpen] = useState(false);
    const [detailAppId, setDetailAppId] = useState<string | null>(null);
    const [decisionApp, setDecisionApp] = useState<LeaveApplication | null>(null);
    const [decisionAction, setDecisionAction] = useState<"approve" | "reject" | null>(null);
    const [affectedPeriodsAppId, setAffectedPeriodsAppId] = useState<string | null>(null);

    // Filtered lists
    const filteredMyApplications = useMemo(() => {
        if (!mySearch.trim()) return myApplications;
        const q = mySearch.toLowerCase();
        return myApplications.filter(
            (a) =>
                a.leave_type_name.toLowerCase().includes(q) ||
                (a.reason && a.reason.toLowerCase().includes(q))
        );
    }, [myApplications, mySearch]);

    const filteredInbox = useMemo(() => {
        if (!inboxSearch.trim()) return inboxApplications;
        const q = inboxSearch.toLowerCase();
        return inboxApplications.filter(
            (a) =>
                a.staff_name.toLowerCase().includes(q) ||
                a.employee_id.toLowerCase().includes(q) ||
                a.leave_type_name.toLowerCase().includes(q)
        );
    }, [inboxApplications, inboxSearch]);

    const filteredBalances = useMemo(() => {
        if (!quotasSearch.trim()) return allBalances;
        const q = quotasSearch.toLowerCase();
        return allBalances.filter(
            (b) =>
                b.staff_name.toLowerCase().includes(q) ||
                b.employee_id.toLowerCase().includes(q) ||
                b.leave_type_name.toLowerCase().includes(q)
        );
    }, [allBalances, quotasSearch]);

    // Top pulse metrics
    const metrics = useMemo(() => {
        const totalAllocated = myBalances.reduce((sum, b) => sum + parseFloat(String(b.allocated_days || 0)), 0);
        const totalAvailable = myBalances.reduce((sum, b) => sum + parseFloat(String(b.available_days || 0)), 0);
        const totalUsed = myBalances.reduce((sum, b) => sum + parseFloat(String(b.used_days || 0)), 0);
        const pendingInboxCount = inboxApplications.filter((a) => a.status === "pending").length;
        return { totalAllocated, totalAvailable, totalUsed, pendingInboxCount };
    }, [myBalances, inboxApplications]);

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "approved":
                return (
                    <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                        Approved
                    </Badge>
                );
            case "rejected":
                return (
                    <Badge className="bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300/80 font-semibold text-[11px]">
                        Rejected
                    </Badge>
                );
            case "cancelled":
                return (
                    <Badge variant="outline" className="text-[11px] text-slate-400 border-slate-300">
                        Cancelled
                    </Badge>
                );
            default:
                return (
                    <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-[11px]">
                        Pending Review
                    </Badge>
                );
        }
    };

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Calendar className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Staff Leave & Faculty Absence Hub</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Faculty leave requests, quota entitlements, pending approver inbox, and timetable substitution coordination
                    </p>
                </div>

                <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                        onClick={() => setApplyOpen(true)}
                        size="sm"
                        className="gap-1.5"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Apply for Leave</span>
                    </Button>
                </div>
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Available Leave Days */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Available Quota</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <CalendarCheck className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalAvailable}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            days left
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Out of {metrics.totalAllocated} allocated days
                    </p>
                </div>

                {/* Days Consumed */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Days Taken</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Clock className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalUsed}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">days consumed</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Current academic year
                    </p>
                </div>

                {/* Pending Approver Requests */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Approver Pending</span>
                        <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                            <Inbox className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.pendingInboxCount}
                        </span>
                        <span className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold">
                            awaiting sign-off
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        In your review queue
                    </p>
                </div>

                {/* Academic Session */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Academic Year</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Calendar className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {academicYear || "Active"}
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Active quota entitlement cycle
                    </p>
                </div>
            </div>

            {/* 3. Main Navigation Tabs */}
            <Tabs defaultValue="my-leaves" className="space-y-4">
                <div className="border-b border-slate-200 dark:border-slate-800">
                    <TabsList className="bg-transparent h-10 p-0 gap-6">
                        <TabsTrigger
                            value="my-leaves"
                            className="h-10 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                        >
                            <Calendar className="w-4 h-4" />
                            <span>My Leaves & Quotas</span>
                        </TabsTrigger>

                        {canManageLeaves && (
                            <TabsTrigger
                                value="approver-inbox"
                                className="h-10 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                            >
                                <Inbox className="w-4 h-4" />
                                <span>Approver Inbox</span>
                                {metrics.pendingInboxCount > 0 && (
                                    <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500 text-white font-bold">
                                        {metrics.pendingInboxCount}
                                    </span>
                                )}
                            </TabsTrigger>
                        )}

                        {canViewAll && (
                            <TabsTrigger
                                value="staff-quotas"
                                className="h-10 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                            >
                                <UserCheck className="w-4 h-4" />
                                <span>Staff Quotas Directory</span>
                            </TabsTrigger>
                        )}

                        {canManageTypes && (
                            <TabsTrigger
                                value="leave-types"
                                className="h-10 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                            >
                                <Settings className="w-4 h-4" />
                                <span>Leave Policy Rules</span>
                            </TabsTrigger>
                        )}
                    </TabsList>
                </div>

                {/* TAB 1: MY LEAVES & QUOTAS */}
                <TabsContent value="my-leaves" className="space-y-6 outline-none">
                    {/* Quota Balance Cards */}
                    <div className="space-y-2.5">
                        <h3 className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                            My Annual Quota Balances ({academicYear || "Active Year"})
                        </h3>
                        <LeaveBalanceCards balances={myBalances} isLoading={loadingBalances} />
                    </div>

                    {/* Applications Table */}
                    <div className="space-y-3.5">
                        <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
                            <div className="relative flex-1 w-full">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                <Input
                                    placeholder="Search my applications by category or reason..."
                                    value={mySearch}
                                    onChange={(e) => setMySearch(e.target.value)}
                                    className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                                />
                                {mySearch && (
                                    <button
                                        onClick={() => setMySearch("")}
                                        className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </button>
                                )}
                            </div>

                            <div className="w-40 shrink-0">
                                <Select value={statusFilter} onValueChange={setStatusFilter}>
                                    <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                        <SelectValue placeholder="All Statuses" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all" className="text-xs">All Statuses</SelectItem>
                                        <SelectItem value="pending" className="text-xs">Pending Review</SelectItem>
                                        <SelectItem value="approved" className="text-xs">Approved</SelectItem>
                                        <SelectItem value="rejected" className="text-xs">Rejected</SelectItem>
                                        <SelectItem value="cancelled" className="text-xs">Cancelled</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {loadingMyApps ? (
                            <div className="p-16 flex flex-col items-center justify-center gap-3">
                                <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
                                <span className="text-xs text-slate-500 font-medium">Loading applications...</span>
                            </div>
                        ) : filteredMyApplications.length === 0 ? (
                            <EmptyState
                                title={mySearch ? "No applications matched your search" : "No leave requests found"}
                                description="Submit a leave application when you require planned time off or sick leave."
                                action={
                                    !mySearch ? (
                                        <Button
                                            onClick={() => setApplyOpen(true)}
                                            size="sm"
                                            className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                                        >
                                            <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                            <span>Apply for Leave</span>
                                        </Button>
                                    ) : undefined
                                }
                            />
                        ) : (
                            <TableShell>
                                <Table>
                                    <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                        <TableRow className="hover:bg-transparent">
                                            <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Category
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Leave Dates
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Duration
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Reason
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Proof
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Status
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Applied On
                                            </TableHead>
                                            <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Actions
                                            </TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredMyApplications.map((app) => (
                                            <TableRow
                                                key={app.id}
                                                className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                            >
                                                {/* Category */}
                                                <TableCell className="py-3.5 pl-4">
                                                    <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                        {app.leave_type_name}
                                                    </div>
                                                    <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                        {app.leave_type_code}
                                                    </code>
                                                </TableCell>

                                                {/* Dates */}
                                                <TableCell className="py-3.5 text-xs text-slate-700 dark:text-slate-300 font-medium">
                                                    <div>
                                                        {formatDateSafe(app.start_date)} → {formatDateSafe(app.end_date)}
                                                    </div>
                                                    {app.is_half_day && (
                                                        <span className="text-[10px] text-sky-600 dark:text-sky-400 font-semibold block">
                                                            Half Day ({app.half_day_session})
                                                        </span>
                                                    )}
                                                </TableCell>

                                                {/* Duration */}
                                                <TableCell className="py-3.5 text-xs font-bold text-slate-900 dark:text-white">
                                                    {app.working_days} {parseFloat(String(app.working_days)) === 1 ? "day" : "days"}
                                                </TableCell>

                                                {/* Reason */}
                                                <TableCell className="py-3.5 text-xs max-w-xs truncate text-slate-600 dark:text-slate-400">
                                                    {app.reason}
                                                </TableCell>

                                                {/* Proof */}
                                                <TableCell className="py-3.5">
                                                    {app.has_document ? (
                                                        <FileText className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                                                    ) : (
                                                        <span className="text-slate-300 dark:text-slate-600 text-xs">—</span>
                                                    )}
                                                </TableCell>

                                                {/* Status */}
                                                <TableCell className="py-3.5">
                                                    {getStatusBadge(app.status)}
                                                </TableCell>

                                                {/* Applied On */}
                                                <TableCell className="py-3.5 text-xs text-slate-500 font-medium">
                                                    {formatDateSafe(app.applied_at)}
                                                </TableCell>

                                                {/* Actions */}
                                                <TableCell className="py-3.5 pr-4 text-right">
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 px-2.5 text-xs text-sky-600 hover:text-sky-700 hover:bg-sky-50 dark:hover:bg-sky-950/40 rounded-lg cursor-pointer"
                                                        onClick={() => setDetailAppId(app.id)}
                                                    >
                                                        <Eye className="w-3.5 h-3.5 mr-1" />
                                                        <span>Details</span>
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableShell>
                        )}
                    </div>
                </TabsContent>

                {/* TAB 2: APPROVER INBOX */}
                {canManageLeaves && (
                    <TabsContent value="approver-inbox" className="space-y-4 outline-none">
                        <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
                            <div className="relative flex-1 w-full">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                <Input
                                    placeholder="Search approver queue by staff name or employee ID..."
                                    value={inboxSearch}
                                    onChange={(e) => setInboxSearch(e.target.value)}
                                    className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                                />
                                {inboxSearch && (
                                    <button
                                        onClick={() => setInboxSearch("")}
                                        className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </button>
                                )}
                            </div>

                            <div className="w-40 shrink-0">
                                <Select value={inboxStatus} onValueChange={setInboxStatus}>
                                    <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="pending" className="text-xs">Pending Review</SelectItem>
                                        <SelectItem value="approved" className="text-xs">Approved</SelectItem>
                                        <SelectItem value="rejected" className="text-xs">Rejected</SelectItem>
                                        <SelectItem value="all" className="text-xs">All Applications</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        {loadingInbox ? (
                            <div className="p-16 flex flex-col items-center justify-center gap-3">
                                <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
                                <span className="text-xs text-slate-500 font-medium">Loading approval inbox...</span>
                            </div>
                        ) : filteredInbox.length === 0 ? (
                            <EmptyState
                                title="No applications in this inbox"
                                description="You have reviewed all pending faculty leave requests. New staff submissions will show up here."
                            />
                        ) : (
                            <TableShell>
                                <Table>
                                    <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                        <TableRow className="hover:bg-transparent">
                                            <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Staff Member
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Leave Category
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Dates Requested
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Working Days
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Proof
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Status
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Reason
                                            </TableHead>
                                            <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Decisions
                                            </TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredInbox.map((app) => {
                                            return (
                                                <TableRow
                                                    key={app.id}
                                                    className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                                >
                                                    {/* Staff Member with Avatar */}
                                                    <TableCell className="py-3.5 pl-4">
                                                        <div className="flex items-center gap-2.5">
                                                            <Avatar name={app.staff_name} size="sm" />
                                                            <div>
                                                                <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                                    {app.staff_name}
                                                                </div>
                                                                <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                                    {app.employee_id}
                                                                </code>
                                                            </div>
                                                        </div>
                                                    </TableCell>

                                                    {/* Leave Category */}
                                                    <TableCell className="py-3.5 text-xs text-slate-800 dark:text-slate-200">
                                                        <span className="font-semibold">{app.leave_type_name}</span>
                                                        <span className="text-slate-400 text-[10px] block font-mono">
                                                            {app.leave_type_code}
                                                        </span>
                                                    </TableCell>

                                                    {/* Dates */}
                                                    <TableCell className="py-3.5 text-xs text-slate-700 dark:text-slate-300">
                                                        {formatDateSafe(app.start_date)} → {formatDateSafe(app.end_date)}
                                                    </TableCell>

                                                    {/* Working Days */}
                                                    <TableCell className="py-3.5 text-xs font-bold text-slate-900 dark:text-white">
                                                        {app.working_days}d
                                                    </TableCell>

                                                    {/* Proof */}
                                                    <TableCell className="py-3.5">
                                                        {app.has_document ? (
                                                            <FileText className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                                                        ) : (
                                                            <span className="text-slate-300 dark:text-slate-600 text-xs">—</span>
                                                        )}
                                                    </TableCell>

                                                    {/* Status */}
                                                    <TableCell className="py-3.5">
                                                        {getStatusBadge(app.status)}
                                                    </TableCell>

                                                    {/* Reason */}
                                                    <TableCell className="py-3.5 text-xs max-w-xs truncate text-slate-600 dark:text-slate-400">
                                                        {app.reason}
                                                    </TableCell>

                                                    {/* Actions */}
                                                    <TableCell className="py-3.5 pr-4 text-right">
                                                        <div className="flex items-center justify-end gap-1">
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                className="h-8 px-2 text-xs text-slate-600 hover:text-slate-900"
                                                                onClick={() => setDetailAppId(app.id)}
                                                            >
                                                                Details
                                                            </Button>
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                className="h-8 px-2 text-xs text-indigo-600 hover:text-indigo-700"
                                                                onClick={() => setAffectedPeriodsAppId(app.id)}
                                                            >
                                                                <Clock className="w-3.5 h-3.5 mr-1" />
                                                                <span>Timetable</span>
                                                            </Button>
                                                            {app.status === "pending" && (
                                                                <>
                                                                    <Button
                                                                        size="sm"
                                                                        className="bg-emerald-600 hover:bg-emerald-500 text-white"
                                                                        onClick={() => {
                                                                            setDecisionApp(app);
                                                                            setDecisionAction("approve");
                                                                        }}
                                                                    >
                                                                        <Check className="w-3.5 h-3.5 mr-1" />
                                                                        <span>Approve</span>
                                                                    </Button>
                                                                    <Button
                                                                        size="sm"
                                                                        variant="outline"
                                                                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50 border-rose-200 dark:border-rose-900"
                                                                        onClick={() => {
                                                                            setDecisionApp(app);
                                                                            setDecisionAction("reject");
                                                                        }}
                                                                    >
                                                                        Reject
                                                                    </Button>
                                                                </>
                                                            )}
                                                        </div>
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </TableShell>
                        )}
                    </TabsContent>
                )}

                {/* TAB 3: STAFF QUOTAS DIRECTORY */}
                {canViewAll && (
                    <TabsContent value="staff-quotas" className="space-y-4 outline-none">
                        <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex items-center justify-between gap-3">
                            <div className="relative flex-1">
                                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                                <Input
                                    placeholder="Search staff quotas by employee name, ID, or leave type..."
                                    value={quotasSearch}
                                    onChange={(e) => setQuotasSearch(e.target.value)}
                                    className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                                />
                                {quotasSearch && (
                                    <button
                                        onClick={() => setQuotasSearch("")}
                                        className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                                    >
                                        <X className="h-3.5 w-3.5" />
                                    </button>
                                )}
                            </div>
                        </div>

                        {loadingAllBalances ? (
                            <div className="p-16 flex flex-col items-center justify-center gap-3">
                                <Loader2 className="w-7 h-7 animate-spin text-sky-600" />
                                <span className="text-xs text-slate-500 font-medium">Loading staff quotas...</span>
                            </div>
                        ) : filteredBalances.length === 0 ? (
                            <EmptyState
                                title="No staff quotas found"
                                description="No employee leave balance records found for the active academic cycle."
                            />
                        ) : (
                            <TableShell>
                                <Table>
                                    <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                        <TableRow className="hover:bg-transparent">
                                            <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Staff Member
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Leave Category
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Allocated
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Used
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Pending
                                            </TableHead>
                                            <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Available
                                            </TableHead>
                                            <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                                Type
                                            </TableHead>
                                        </TableRow>
                                    </TableHeader>
                                    <TableBody>
                                        {filteredBalances.map((bal) => {
                                            const available = parseFloat(String(bal.available_days || 0));

                                            return (
                                                <TableRow
                                                    key={bal.id}
                                                    className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                                >
                                                    {/* Staff Member with Avatar */}
                                                    <TableCell className="py-3.5 pl-4">
                                                        <div className="flex items-center gap-2.5">
                                                            <Avatar name={bal.staff_name} size="sm" />
                                                            <div>
                                                                <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                                    {bal.staff_name}
                                                                </div>
                                                                <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                                    {bal.employee_id}
                                                                </code>
                                                            </div>
                                                        </div>
                                                    </TableCell>

                                                    {/* Category */}
                                                    <TableCell className="py-3.5 text-xs text-slate-800 dark:text-slate-200">
                                                        <span className="font-semibold">{bal.leave_type_name}</span>
                                                        <span className="text-slate-400 text-[10px] block font-mono">
                                                            {bal.leave_type_code}
                                                        </span>
                                                    </TableCell>

                                                    {/* Allocated */}
                                                    <TableCell className="py-3.5 text-xs font-semibold text-slate-700 dark:text-slate-300">
                                                        {bal.allocated_days}d
                                                    </TableCell>

                                                    {/* Used */}
                                                    <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-400">
                                                        {bal.used_days}d
                                                    </TableCell>

                                                    {/* Pending */}
                                                    <TableCell className="py-3.5 text-xs text-amber-600 dark:text-amber-400 font-medium">
                                                        {bal.pending_days}d
                                                    </TableCell>

                                                    {/* Available */}
                                                    <TableCell className="py-3.5">
                                                        <Badge
                                                            variant="outline"
                                                            className={`text-xs font-bold ${
                                                                available > 3
                                                                    ? "border-emerald-300 text-emerald-700 bg-emerald-50 dark:bg-emerald-950/40"
                                                                    : available > 0
                                                                    ? "border-amber-300 text-amber-700 bg-amber-50 dark:bg-amber-950/40"
                                                                    : "border-rose-300 text-rose-700 bg-rose-50 dark:bg-rose-950/40"
                                                            }`}
                                                        >
                                                            {available} days
                                                        </Badge>
                                                    </TableCell>

                                                    {/* Type */}
                                                    <TableCell className="py-3.5 pr-4 text-right text-xs">
                                                        {bal.is_paid ? (
                                                            <span className="text-emerald-600 font-medium">Paid</span>
                                                        ) : (
                                                            <span className="text-slate-400">Unpaid</span>
                                                        )}
                                                    </TableCell>
                                                </TableRow>
                                            );
                                        })}
                                    </TableBody>
                                </Table>
                            </TableShell>
                        )}
                    </TabsContent>
                )}

                {/* TAB 4: LEAVE POLICIES CONFIG */}
                {canManageTypes && (
                    <TabsContent value="leave-types" className="outline-none">
                        <LeaveTypesConfigTab />
                    </TabsContent>
                )}
            </Tabs>

            {/* Modals & Dialogs */}
            <ApplyLeaveDialog
                open={applyOpen}
                onOpenChange={setApplyOpen}
            />

            <LeaveDetailModal
                applicationId={detailAppId}
                onClose={() => setDetailAppId(null)}
            />

            {decisionApp && decisionAction && (
                <LeaveDecisionModal
                    application={decisionApp}
                    action={decisionAction}
                    onClose={() => {
                        setDecisionApp(null);
                        setDecisionAction(null);
                    }}
                />
            )}

            <AffectedPeriodsModal
                applicationId={affectedPeriodsAppId}
                onClose={() => setAffectedPeriodsAppId(null)}
            />
        </div>
    );
}
