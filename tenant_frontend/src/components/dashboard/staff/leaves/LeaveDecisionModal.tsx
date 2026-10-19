"use client";

import React, { useState } from "react";
import { LeaveApplication } from "@/types/Leave";
import { useApproveLeave, useRejectLeave } from "@/hooks/useStaffLeaves";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { CheckCircle2, XCircle, AlertCircle, Loader2 } from "lucide-react";
import { format } from "date-fns";

interface LeaveDecisionModalProps {
    application: LeaveApplication | null;
    action: "approve" | "reject" | null;
    onClose: () => void;
}

export function LeaveDecisionModal({ application, action, onClose }: LeaveDecisionModalProps) {
    const [comments, setComments] = useState("");
    const approveMutation = useApproveLeave();
    const rejectMutation = useRejectLeave();

    if (!application || !action) return null;

    const isApprove = action === "approve";
    const isPending = approveMutation.isPending || rejectMutation.isPending;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (!isApprove && (!comments || !comments.trim())) {
            return;
        }

        if (isApprove) {
            approveMutation.mutate(
                { id: application.id, comments: comments.trim() },
                {
                    onSuccess: () => {
                        setComments("");
                        onClose();
                    },
                }
            );
        } else {
            rejectMutation.mutate(
                { id: application.id, comments: comments.trim() },
                {
                    onSuccess: () => {
                        setComments("");
                        onClose();
                    },
                }
            );
        }
    };

    return (
        <Dialog open={!!application && !!action} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        {isApprove ? (
                            <>
                                <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                                <span>Approve Leave Application</span>
                            </>
                        ) : (
                            <>
                                <XCircle className="w-5 h-5 text-rose-600" />
                                <span>Reject Leave Application</span>
                            </>
                        )}
                    </DialogTitle>
                    <DialogDescription>
                        {isApprove
                            ? "Approving this application will deduct days from balance and update daily staff attendance records."
                            : "Rejecting this application will release reserved pending days back to the staff member's quota."}
                    </DialogDescription>
                </DialogHeader>

                <div className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-xs space-y-1 my-2">
                    <p className="font-semibold text-slate-800 dark:text-slate-200">{application.staff_name} ({application.employee_id})</p>
                    <p className="text-slate-500">
                        {application.leave_type_name} • {application.working_days} working days
                    </p>
                    <p className="text-slate-500">
                        {format(new Date(application.start_date), "MMM d")} → {format(new Date(application.end_date), "MMM d, yyyy")}
                    </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-1.5">
                        <Label htmlFor="decisionComments">
                            {isApprove ? "Approval Comments (Optional)" : "Rejection Reason (Mandatory *)"}
                        </Label>
                        <Textarea
                            id="decisionComments"
                            rows={3}
                            placeholder={isApprove ? "Add any notes or substitute instructions..." : "Specify reason for declining request..."}
                            value={comments}
                            onChange={(e) => setComments(e.target.value)}
                            required={!isApprove}
                        />
                    </div>

                    <DialogFooter className="pt-2">
                        <Button type="button" variant="outline" onClick={onClose} disabled={isPending}>
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={isPending}
                            className={isApprove ? "bg-emerald-600 hover:bg-emerald-700" : "bg-rose-600 hover:bg-rose-700"}
                        >
                            {isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                            {isApprove ? "Confirm Approval" : "Confirm Rejection"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

