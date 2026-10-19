"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useMakeAdmissionDecision } from "@/hooks/useAdmissions";
import { AdmissionApplication } from "@/types/Admissions";
import { Loader2, CheckCircle2, XCircle, Clock } from "lucide-react";

interface DecisionDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    application: AdmissionApplication | null;
}

export default function DecisionDialog({
    open,
    onOpenChange,
    application,
}: DecisionDialogProps) {
    const [decision, setDecision] = useState<"approved" | "rejected" | "waitlisted">("approved");
    const [reason, setReason] = useState("");
    const [notes, setNotes] = useState("");

    const decisionMutation = useMakeAdmissionDecision();

    if (!application) return null;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (decision === "rejected" && !reason.trim()) {
            return;
        }

        decisionMutation.mutate(
            {
                id: application.id,
                decision,
                reason: reason.trim(),
                notes: notes.trim(),
            },
            {
                onSuccess: () => {
                    onOpenChange(false);
                    setReason("");
                    setNotes("");
                },
            }
        );
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg rounded-3xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold">
                        Record Admission Decision
                    </DialogTitle>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                    <div className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/60 dark:border-slate-800 text-sm">
                        <div className="font-semibold text-slate-800 dark:text-white">
                            {application.first_name} {application.last_name}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">
                            Ref: {application.application_number} · Grade: {application.level_name || application.level} · Year: {application.academic_year}
                        </div>
                    </div>

                    <div className="space-y-1.5">
                        <Label htmlFor="decision">Decision Outcome *</Label>
                        <Select
                            value={decision}
                            onValueChange={(v) => setDecision(v as "approved" | "rejected" | "waitlisted")}
                        >
                            <SelectTrigger id="decision">
                                <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="approved">
                                    <div className="flex items-center text-emerald-600 font-medium">
                                        <CheckCircle2 className="w-4 h-4 mr-2" />
                                        Approve for Admission
                                    </div>
                                </SelectItem>
                                <SelectItem value="waitlisted">
                                    <div className="flex items-center text-amber-600 font-medium">
                                        <Clock className="w-4 h-4 mr-2" />
                                        Place on Waitlist
                                    </div>
                                </SelectItem>
                                <SelectItem value="rejected">
                                    <div className="flex items-center text-red-600 font-medium">
                                        <XCircle className="w-4 h-4 mr-2" />
                                        Reject Application
                                    </div>
                                </SelectItem>
                            </SelectContent>
                        </Select>
                    </div>

                    {decision === "rejected" && (
                        <div className="space-y-1.5">
                            <Label htmlFor="reason" className="text-red-600 dark:text-red-400">
                                Rejection Reason * (Required)
                            </Label>
                            <Textarea
                                id="reason"
                                required
                                rows={3}
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                placeholder="Explain why the application is not approved (e.g. seats full, eligibility criteria not met, documents incomplete)..."
                                className="border-red-200 dark:border-red-900 focus-visible:ring-red-500"
                            />
                        </div>
                    )}

                    <div className="space-y-1.5">
                        <Label htmlFor="notes">Internal Remarks / Offer Conditions (Optional)</Label>
                        <Textarea
                            id="notes"
                            rows={3}
                            value={notes}
                            onChange={(e) => setNotes(e.target.value)}
                            placeholder="Add notes for admissions committee, special scholarship terms, section recommendation..."
                        />
                    </div>

                    <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => onOpenChange(false)}
                            disabled={decisionMutation.isPending}
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={decisionMutation.isPending || (decision === "rejected" && !reason.trim())}
                            className={
                                decision === "approved"
                                    ? "bg-emerald-600 hover:bg-emerald-700 text-white"
                                    : decision === "rejected"
                                    ? "bg-red-600 hover:bg-red-700 text-white"
                                    : "bg-amber-600 hover:bg-amber-700 text-white"
                            }
                        >
                            {decisionMutation.isPending && (
                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                            )}
                            Confirm Decision
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

