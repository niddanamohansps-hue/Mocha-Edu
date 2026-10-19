"use client";

import React, { useState } from "react";
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
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
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
    CheckSquare,
    Settings,
    UserCheck,
    Loader2,
    Inbox,
} from "lucide-react";
import { format } from "date-fns";

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
    const { data: myAppsData, isLoading: loadingMyApps } = useMyLeaveApplications({
        status: statusFilter === "all" ? undefined : statusFilter,
        academic_year: academicYear,
    });
    const myApplications = myAppsData?.results || [];

    const [inboxStatus, setInboxStatus] = useState<string>("pending");
    const { data: inboxData, isLoading: loadingInbox } = useApproverInbox({
        status: inboxStatus === "all" ? undefined : inboxStatus,
    });
    const inboxApplications = inboxData?.results || [];

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

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "approved":
                return <Badge className="bg-emerald-600">Approved</Badge>;
            case "rejected":
                return <Badge variant="destructive">Rejected</Badge>;
            case "cancelled":
                return <Badge variant="secondary">Cancelled</Badge>;
            default:
                return <Badge className="bg-amber-500">Pending Review</Badge>;
        }
    };

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
                        Staff Leave Management
                    </h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                        Request leave, track balance quotas, review staff requests, and coordinate faculty substitutions.
                    </p>
                </div>

                <div className="flex items-center gap-2.5">
                    <Button onClick={() => setApplyOpen(true)} className="bg-indigo-600 hover:bg-indigo-700 shadow-sm">
                        <Plus className="w-4 h-4 mr-1.5" />
                        Apply for Leave
                    </Button>
                </div>
            </div>

            {/* Navigation Tabs */}
            <Tabs defaultValue="my-leaves" className="space-y-4">
                <TabsList className="bg-slate-100 dark:bg-slate-800 p-1">
                    <TabsTrigger value="my-leaves" className="gap-1.5 text-xs font-medium">
                        <Calendar className="w-4 h-4" />
                        <span>My Leaves</span>
                    </TabsTrigger>

                    {canManageLeaves && (
                        <TabsTrigger value="approver-inbox" className="gap-1.5 text-xs font-medium relative">
                            <Inbox className="w-4 h-4" />
                            <span>Approver Inbox</span>
                            {inboxApplications.length > 0 && inboxStatus === "pending" && (
                                <span className="ml-1 px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500 text-white font-bold">
                                    {inboxApplications.length}
                                </span>
                            )}
                        </TabsTrigger>
                    )}

                    {canViewAll && (
                        <TabsTrigger value="staff-quotas" className="gap-1.5 text-xs font-medium">
                            <UserCheck className="w-4 h-4" />
                            <span>Staff Quotas</span>
                        </TabsTrigger>
                    )}

                    {canManageTypes && (
                        <TabsTrigger value="leave-types" className="gap-1.5 text-xs font-medium">
                            <Settings className="w-4 h-4" />
                            <span>Leave Policies</span>
                        </TabsTrigger>
                    )}
                </TabsList>

                {/* ========================================================= */}
                {/* TAB 1: MY LEAVES                                          */}
                {/* ========================================================= */}
                <TabsContent value="my-leaves" className="space-y-6">
                    {/* Balance Quotas */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                My Leave Quotas ({academicYear || "Active Year"})
                            </h2>
                        </div>
                        <LeaveBalanceCards balances={myBalances} isLoading={loadingBalances} />
                    </div>

                    {/* Applications List */}
                    <div className="space-y-3">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                            <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                My Leave Applications History
                            </h2>

                            <div className="flex items-center gap-2">
                                <Select value={statusFilter} onValueChange={setStatusFilter}>
                                    <SelectTrigger className="w-36 h-8 text-xs">
                                        <SelectValue placeholder="All Statuses" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="all">All Statuses</SelectItem>
                                        <SelectItem value="pending">Pending</SelectItem>
                                        <SelectItem value="approved">Approved</SelectItem>
                                        <SelectItem value="rejected">Rejected</SelectItem>
                                        <SelectItem value="cancelled">Cancelled</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        </div>

                        <Card className="border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                            <Table>
                                <TableHeader className="bg-slate-50 dark:bg-slate-900">
                                    <TableRow>
                                        <TableHead>Category</TableHead>
                                        <TableHead>Date Window</TableHead>
                                        <TableHead>Duration</TableHead>
                                        <TableHead>Reason</TableHead>
                                        <TableHead>Proof</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Applied On</TableHead>
                                        <TableHead className="text-right">Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {loadingMyApps ? (
                                        <TableRow>
                                            <TableCell colSpan={8} className="text-center py-10 text-slate-400">
                                                <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                                            </TableCell>
                                        </TableRow>
                                    ) : myApplications.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={8} className="text-center py-8 text-slate-400 text-xs">
                                                No leave applications found for this filter.
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        myApplications.map((app) => (
                                            <TableRow key={app.id}>
                                                <TableCell>
                                                    <div className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                                                        {app.leave_type_name}
                                                    </div>
                                                    <span className="font-mono text-[10px] text-slate-400">
                                                        {app.leave_type_code}
                                                    </span>
                                                </TableCell>
                                                <TableCell className="text-xs">
                                                    <div>
                                                        {format(new Date(app.start_date), "MMM d")} → {format(new Date(app.end_date), "MMM d, yyyy")}
                                                    </div>
                                                    {app.is_half_day && (
                                                        <span className="text-[10px] text-indigo-600 dark:text-indigo-400 font-medium">
                                                            Half Day ({app.half_day_session})
                                                        </span>
                                                    )}
                                                </TableCell>
                                                <TableCell className="text-xs font-semibold">
                                                    {app.working_days} {parseFloat(String(app.working_days)) === 1 ? "day" : "days"}
                                                </TableCell>
                                                <TableCell className="text-xs max-w-xs truncate text-slate-600 dark:text-slate-400">
                                                    {app.reason}
                                                </TableCell>
                                                <TableCell>
                                                    {app.has_document ? (
                                                        <FileText className="w-4 h-4 text-indigo-500" />
                                                    ) : (
                                                        <span className="text-slate-300 dark:text-slate-600 text-xs">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>{getStatusBadge(app.status)}</TableCell>
                                                <TableCell className="text-xs text-slate-400 font-mono">
                                                    {format(new Date(app.applied_at), "MMM d, yyyy")}
                                                </TableCell>
                                                <TableCell className="text-right">
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 text-xs text-indigo-600"
                                                        onClick={() => setDetailAppId(app.id)}
                                                    >
                                                        <Eye className="w-3.5 h-3.5 mr-1" />
                                                        Details
                                                    </Button>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </Card>
                    </div>
                </TabsContent>

                {/* ========================================================= */}
                {/* TAB 2: APPROVER INBOX                                     */}
                {/* ========================================================= */}
                {canManageLeaves && (
                    <TabsContent value="approver-inbox" className="space-y-4">
                        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                            <div>
                                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                    Staff Leave Review Inbox
                                </h2>
                                <p className="text-xs text-slate-500">
                                    Review, approve, or decline pending requests. Approvals automatically sync daily attendance.
                                </p>
                            </div>

                            <Select value={inboxStatus} onValueChange={setInboxStatus}>
                                <SelectTrigger className="w-36 h-8 text-xs">
                                    <SelectValue />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="pending">Pending</SelectItem>
                                    <SelectItem value="approved">Approved</SelectItem>
                                    <SelectItem value="rejected">Rejected</SelectItem>
                                    <SelectItem value="all">All Applications</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <Card className="border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                            <Table>
                                <TableHeader className="bg-slate-50 dark:bg-slate-900">
                                    <TableRow>
                                        <TableHead>Staff Member</TableHead>
                                        <TableHead>Leave Category</TableHead>
                                        <TableHead>Dates</TableHead>
                                        <TableHead>Working Days</TableHead>
                                        <TableHead>Proof</TableHead>
                                        <TableHead>Status</TableHead>
                                        <TableHead>Reason</TableHead>
                                        <TableHead className="text-right">Decision Actions</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {loadingInbox ? (
                                        <TableRow>
                                            <TableCell colSpan={8} className="text-center py-10 text-slate-400">
                                                <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                                            </TableCell>
                                        </TableRow>
                                    ) : inboxApplications.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={8} className="text-center py-8 text-slate-400 text-xs">
                                                No applications matching this filter.
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        inboxApplications.map((app) => (
                                            <TableRow key={app.id}>
                                                <TableCell>
                                                    <div className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                                                        {app.staff_name}
                                                    </div>
                                                    <span className="font-mono text-[10px] text-slate-400">
                                                        {app.employee_id}
                                                    </span>
                                                </TableCell>
                                                <TableCell className="text-xs">
                                                    {app.leave_type_name} ({app.leave_type_code})
                                                </TableCell>
                                                <TableCell className="text-xs">
                                                    {format(new Date(app.start_date), "MMM d")} → {format(new Date(app.end_date), "MMM d")}
                                                </TableCell>
                                                <TableCell className="text-xs font-semibold">
                                                    {app.working_days}d
                                                </TableCell>
                                                <TableCell>
                                                    {app.has_document ? (
                                                        <FileText className="w-4 h-4 text-indigo-500" />
                                                    ) : (
                                                        <span className="text-slate-300 text-xs">—</span>
                                                    )}
                                                </TableCell>
                                                <TableCell>{getStatusBadge(app.status)}</TableCell>
                                                <TableCell className="text-xs max-w-xs truncate text-slate-600 dark:text-slate-400">
                                                    {app.reason}
                                                </TableCell>
                                                <TableCell className="text-right space-x-1">
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 text-xs"
                                                        onClick={() => setDetailAppId(app.id)}
                                                    >
                                                        Details
                                                    </Button>
                                                    <Button
                                                        size="sm"
                                                        variant="ghost"
                                                        className="h-8 text-xs text-indigo-600"
                                                        onClick={() => setAffectedPeriodsAppId(app.id)}
                                                    >
                                                        <Clock className="w-3.5 h-3.5 mr-1" />
                                                        Timetable
                                                    </Button>
                                                    {app.status === "pending" && (
                                                        <>
                                                            <Button
                                                                size="sm"
                                                                className="h-8 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
                                                                onClick={() => {
                                                                    setDecisionApp(app);
                                                                    setDecisionAction("approve");
                                                                }}
                                                            >
                                                                Approve
                                                            </Button>
                                                            <Button
                                                                size="sm"
                                                                variant="outline"
                                                                className="h-8 text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                                                onClick={() => {
                                                                    setDecisionApp(app);
                                                                    setDecisionAction("reject");
                                                                }}
                                                            >
                                                                Reject
                                                            </Button>
                                                        </>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </Card>
                    </TabsContent>
                )}

                {/* ========================================================= */}
                {/* TAB 3: STAFF QUOTAS                                       */}
                {/* ========================================================= */}
                {canViewAll && (
                    <TabsContent value="staff-quotas" className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div>
                                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-200">
                                    School Staff Leave Balances ({academicYear || "Active Year"})
                                </h2>
                                <p className="text-xs text-slate-500">
                                    Audit staff entitlement allocations, consumed days, and available balances.
                                </p>
                            </div>
                        </div>

                        <Card className="border border-slate-200 dark:border-slate-800 shadow-sm overflow-hidden">
                            <Table>
                                <TableHeader className="bg-slate-50 dark:bg-slate-900">
                                    <TableRow>
                                        <TableHead>Staff Member</TableHead>
                                        <TableHead>Leave Category</TableHead>
                                        <TableHead>Allocated</TableHead>
                                        <TableHead>Used</TableHead>
                                        <TableHead>Pending</TableHead>
                                        <TableHead>Available</TableHead>
                                        <TableHead>Type</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {loadingAllBalances ? (
                                        <TableRow>
                                            <TableCell colSpan={7} className="text-center py-10 text-slate-400">
                                                <Loader2 className="w-6 h-6 animate-spin mx-auto" />
                                            </TableCell>
                                        </TableRow>
                                    ) : allBalances.length === 0 ? (
                                        <TableRow>
                                            <TableCell colSpan={7} className="text-center py-8 text-slate-400 text-xs">
                                                No staff quota records found.
                                            </TableCell>
                                        </TableRow>
                                    ) : (
                                        allBalances.map((bal) => (
                                            <TableRow key={bal.id}>
                                                <TableCell>
                                                    <div className="font-semibold text-slate-800 dark:text-slate-200 text-xs">
                                                        {bal.staff_name}
                                                    </div>
                                                    <span className="font-mono text-[10px] text-slate-400">
                                                        {bal.employee_id}
                                                    </span>
                                                </TableCell>
                                                <TableCell className="text-xs">
                                                    {bal.leave_type_name} ({bal.leave_type_code})
                                                </TableCell>
                                                <TableCell className="text-xs font-medium">{bal.allocated_days}d</TableCell>
                                                <TableCell className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                                    {bal.used_days}d
                                                </TableCell>
                                                <TableCell className="text-xs font-medium text-amber-600">
                                                    {bal.pending_days}d
                                                </TableCell>
                                                <TableCell className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                                    {bal.available_days}d
                                                </TableCell>
                                                <TableCell>
                                                    <Badge variant={bal.is_paid ? "default" : "secondary"} className="text-[10px]">
                                                        {bal.is_paid ? "Paid" : "Unpaid"}
                                                    </Badge>
                                                </TableCell>
                                            </TableRow>
                                        ))
                                    )}
                                </TableBody>
                            </Table>
                        </Card>
                    </TabsContent>
                )}

                {/* ========================================================= */}
                {/* TAB 4: LEAVE POLICIES                                     */}
                {/* ========================================================= */}
                {canManageTypes && (
                    <TabsContent value="leave-types">
                        <LeaveTypesConfigTab />
                    </TabsContent>
                )}
            </Tabs>

            {/* Modals and Dialogs */}
            <ApplyLeaveDialog open={applyOpen} onOpenChange={setApplyOpen} />

            <LeaveDetailModal
                applicationId={detailAppId}
                onClose={() => setDetailAppId(null)}
                canManage={canManageLeaves}
                onViewAffectedPeriods={(id) => setAffectedPeriodsAppId(id)}
            />

            <LeaveDecisionModal
                application={decisionApp}
                action={decisionAction}
                onClose={() => {
                    setDecisionApp(null);
                    setDecisionAction(null);
                }}
            />

            <AffectedPeriodsModal
                applicationId={affectedPeriodsAppId}
                onClose={() => setAffectedPeriodsAppId(null)}
            />
        </div>
    );
}

