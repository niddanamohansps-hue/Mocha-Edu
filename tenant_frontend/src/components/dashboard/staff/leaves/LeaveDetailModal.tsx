"use client";

import React, { useState } from "react";
import { LeaveApplication } from "@/types/Leave";
import { useCancelLeave, useLeaveApplicationDetail } from "@/hooks/useStaffLeaves";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Calendar,
    Clock,
    FileText,
    Download,
    CheckCircle2,
    XCircle,
    AlertCircle,
    RotateCcw,
    UserCheck,
    Loader2,
} from "lucide-react";
import { format } from "date-fns";

interface LeaveDetailModalProps {
    applicationId: string | null;
    onClose: () => void;
    canManage?: boolean;
    onViewAffectedPeriods?: (id: string) => void;
}

export function LeaveDetailModal({
    applicationId,
    onClose,
    canManage = false,
    onViewAffectedPeriods,
}: LeaveDetailModalProps) {
    const { data: app, isLoading } = useLeaveApplicationDetail(applicationId || undefined);
    const cancelMutation = useCancelLeave();
    const [cancelReason, setCancelReason] = useState("");
    const [showCancelPrompt, setShowCancelPrompt] = useState(false);

    if (!applicationId) return null;

    const handleCancel = () => {
        if (!applicationId) return;
        cancelMutation.mutate(
            { id: applicationId, reason: cancelReason },
            {
                onSuccess: () => {
                    setShowCancelPrompt(false);
                    onClose();
                },
            }
        );
    };

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
        <Dialog open={!!applicationId} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-xl max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <div className="flex items-center justify-between">
                        <DialogTitle className="flex items-center gap-2">
                            <Calendar className="w-5 h-5 text-indigo-600" />
                            Leave Application Details
                        </DialogTitle>
                        {app && getStatusBadge(app.status)}
                    </div>
                    <DialogDescription>
                        Application #{app?.id.slice(0, 8)} • Submitted on{" "}
                        {app?.applied_at ? format(new Date(app.applied_at), "MMM d, yyyy") : ""}
                    </DialogDescription>
                </DialogHeader>

                {isLoading || !app ? (
                    <div className="py-12 flex justify-center items-center">
                        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
                    </div>
                ) : (
                    <div className="space-y-4 pt-2">
                        {/* Staff Profile Overview */}
                        <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-between">
                            <div>
                                <h4 className="font-semibold text-slate-900 dark:text-white">{app.staff_name}</h4>
                                <p className="text-xs text-slate-500">
                                    {app.employee_id} • {app.designation || "Staff"} ({app.department || "General"})
                                </p>
                            </div>
                            <Badge variant="outline" className="font-mono text-xs">
                                {app.leave_type_code}
                            </Badge>
                        </div>

                        {/* Dates and Duration */}
                        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                            <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-950">
                                <span className="text-[11px] text-slate-400 block font-medium">Leave Type</span>
                                <span className="font-semibold text-sm text-slate-800 dark:text-slate-200">
                                    {app.leave_type_name}
                                </span>
                            </div>
                            <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-950">
                                <span className="text-[11px] text-slate-400 block font-medium">Working Days</span>
                                <span className="font-semibold text-sm text-indigo-600 dark:text-indigo-400">
                                    {app.working_days} {parseFloat(String(app.working_days)) === 1 ? "day" : "days"}
                                </span>
                            </div>
                            <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-950">
                                <span className="text-[11px] text-slate-400 block font-medium">Academic Year</span>
                                <span className="font-semibold text-sm text-slate-800 dark:text-slate-200">
                                    {app.academic_year}
                                </span>
                            </div>
                        </div>

                        <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-950 space-y-1">
                            <span className="text-[11px] text-slate-400 block font-medium">Date Range</span>
                            <div className="text-sm font-medium text-slate-800 dark:text-slate-200 flex items-center gap-2">
                                <span>{format(new Date(app.start_date), "MMM d, yyyy")}</span>
                                <span className="text-slate-400">→</span>
                                <span>{format(new Date(app.end_date), "MMM d, yyyy")}</span>
                                {app.is_half_day && (
                                    <Badge variant="secondary" className="text-[10px] ml-2">
                                        Half Day ({app.half_day_session})
                                    </Badge>
                                )}
                            </div>
                        </div>

                        {/* Reason */}
                        <div className="space-y-1">
                            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                                Reason for Leave
                            </span>
                            <div className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/30 text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                                {app.reason}
                            </div>
                        </div>

                        {/* Document Download */}
                        {app.document_url && (
                            <div className="flex items-center justify-between p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950">
                                <div className="flex items-center gap-2.5">
                                    <FileText className="w-5 h-5 text-indigo-500" />
                                    <div>
                                        <p className="text-xs font-medium text-slate-900 dark:text-white">
                                            {app.document_name || "Supporting Proof Document"}
                                        </p>
                                        <p className="text-[10px] text-slate-400">Authenticated confidential access</p>
                                    </div>
                                </div>
                                <Button size="sm" variant="outline" asChild>
                                    <a href={app.document_url} target="_blank" rel="noopener noreferrer">
                                        <Download className="w-4 h-4 mr-1.5" />
                                        Download
                                    </a>
                                </Button>
                            </div>
                        )}

                        {/* Approvals History */}
                        {app.approvals && app.approvals.length > 0 && (
                            <div className="space-y-2 pt-2 border-t border-slate-100 dark:border-slate-800">
                                <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider block">
                                    Review & Decision History
                                </span>
                                <div className="space-y-2">
                                    {app.approvals.map((ap) => (
                                        <div
                                            key={ap.id}
                                            className="p-3 rounded-lg border border-slate-100 dark:border-slate-800 text-xs space-y-1"
                                        >
                                            <div className="flex items-center justify-between">
                                                <div className="flex items-center gap-1.5 font-medium text-slate-800 dark:text-slate-200">
                                                    {ap.decision === "approved" ? (
                                                        <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                                                    ) : ap.decision === "rejected" ? (
                                                        <XCircle className="w-4 h-4 text-rose-500" />
                                                    ) : (
                                                        <RotateCcw className="w-4 h-4 text-slate-400" />
                                                    )}
                                                    <span className="capitalize">{ap.decision} by {ap.approver_name}</span>
                                                </div>
                                                <span className="text-slate-400 font-mono">
                                                    {format(new Date(ap.decided_at), "MMM d, h:mm a")}
                                                </span>
                                            </div>
                                            {ap.comments && (
                                                <p className="text-slate-600 dark:text-slate-400 pl-5">
                                                    "{ap.comments}"
                                                </p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Cancel Confirmation Prompt */}
                        {showCancelPrompt && (
                            <div className="p-3 rounded-lg border border-rose-200 dark:border-rose-900 bg-rose-50/50 dark:bg-rose-950/20 space-y-2">
                                <p className="text-xs font-semibold text-rose-800 dark:text-rose-300">
                                    Are you sure you want to cancel this leave application?
                                </p>
                                <input
                                    type="text"
                                    placeholder="Optional cancellation reason..."
                                    value={cancelReason}
                                    onChange={(e) => setCancelReason(e.target.value)}
                                    className="w-full text-xs p-2 rounded border border-rose-200 dark:border-rose-900 bg-white dark:bg-slate-900"
                                />
                                <div className="flex justify-end gap-2 pt-1">
                                    <Button size="sm" variant="outline" onClick={() => setShowCancelPrompt(false)}>
                                        Back
                                    </Button>
                                    <Button
                                        size="sm"
                                        variant="destructive"
                                        onClick={handleCancel}
                                        disabled={cancelMutation.isPending}
                                    >
                                        {cancelMutation.isPending && <Loader2 className="w-3.5 h-3.5 mr-1 animate-spin" />}
                                        Confirm Cancellation
                                    </Button>
                                </div>
                            </div>
                        )}

                        <DialogFooter className="pt-2 flex items-center justify-between gap-2">
                            <div>
                                {onViewAffectedPeriods && (
                                    <Button
                                        type="button"
                                        variant="secondary"
                                        size="sm"
                                        onClick={() => {
                                            onClose();
                                            onViewAffectedPeriods(app.id);
                                        }}
                                    >
                                        <Clock className="w-4 h-4 mr-1.5 text-indigo-500" />
                                        Timetable Impact
                                    </Button>
                                )}
                            </div>

                            <div className="flex items-center gap-2">
                                {["pending", "approved"].includes(app.status) && !showCancelPrompt && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        size="sm"
                                        className="text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                                        onClick={() => setShowCancelPrompt(true)}
                                    >
                                        Cancel Leave
                                    </Button>
                                )}
                                <Button type="button" variant="outline" size="sm" onClick={onClose}>
                                    Close
                                </Button>
                            </div>
                        </DialogFooter>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

