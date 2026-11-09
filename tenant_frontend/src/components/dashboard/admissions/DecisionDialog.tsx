"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogDescription,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { FormFieldWrapper } from "@/components/ui/form-layout";
import { seatLimitMessage, useMakeAdmissionDecision } from "@/hooks/useAdmissions";
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

    const [overLimit, setOverLimit] = useState(false);
    const decisionMutation = useMakeAdmissionDecision();
    const classFull = decision === "approved" ? seatLimitMessage(decisionMutation.error) : null;

    if (!application) return null;

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (decision === "rejected" && !reason.trim()) {
            return;
        }
        if (classFull && !overLimit) return;

        decisionMutation.mutate(
            {
                id: application.id,
                decision,
                reason: reason.trim(),
                notes: notes.trim(),
                confirm_over_limit: overLimit,
            },
            {
                onSuccess: () => {
                    onOpenChange(false);
                    setReason("");
                    setNotes("");
                    setOverLimit(false);
                },
            }
        );
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl">
                <DialogHeader className="px-6 py-4.5 border-b border-slate-100 dark:border-slate-800 shrink-0">
                    <DialogTitle className="text-lg font-bold text-slate-900 dark:text-white">
                        Record Admission Decision
                    </DialogTitle>
                    <DialogDescription className="text-xs text-slate-500">
                        Select admission status, capture mandatory rejection reasons or conditional terms.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                        <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800 text-sm">
                            <div className="font-bold text-slate-900 dark:text-white">
                                {application.first_name} {application.last_name}
                            </div>
                            <div className="text-xs text-slate-500 mt-1 flex flex-wrap items-center gap-2">
                                <span>Ref: <strong className="text-slate-700 dark:text-slate-300 font-mono">{application.application_number}</strong></span>
                                <span>•</span>
                                <span>Grade: <strong className="text-slate-700 dark:text-slate-300">{application.level_name || application.level}</strong></span>
                                <span>•</span>
                                <span>Year: <strong className="text-slate-700 dark:text-slate-300">{application.academic_year}</strong></span>
                            </div>
                        </div>

                        <FormFieldWrapper label="Decision Outcome" htmlFor="decision" required colSpan="full">
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
                                        <div className="flex items-center text-rose-600 font-medium">
                                            <XCircle className="w-4 h-4 mr-2" />
                                            Reject Application
                                        </div>
                                    </SelectItem>
                                </SelectContent>
                            </Select>
                        </FormFieldWrapper>

                        {decision === "rejected" && (
                            <FormFieldWrapper
                                label="Rejection Reason"
                                htmlFor="reason"
                                required
                                colSpan="full"
                            >
                                <Textarea
                                    id="reason"
                                    required
                                    rows={3}
                                    value={reason}
                                    onChange={(e) => setReason(e.target.value)}
                                    placeholder="Explain why the application is not approved (e.g. seats full, eligibility criteria not met, documents incomplete)..."
                                    className="border-rose-200 dark:border-rose-900 focus-visible:ring-rose-500"
                                />
                            </FormFieldWrapper>
                        )}

                        <FormFieldWrapper
                            label="Internal Remarks / Offer Conditions (Optional)"
                            htmlFor="notes"
                            colSpan="full"
                        >
                            <Textarea
                                id="notes"
                                rows={3}
                                value={notes}
                                onChange={(e) => setNotes(e.target.value)}
                                placeholder="Add notes for admissions committee, special scholarship terms, section recommendation..."
                            />
                        </FormFieldWrapper>

                        {classFull && (
                            <label className="flex items-start gap-2.5 rounded-xl border border-amber-300 bg-amber-50/80 p-3.5 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/30 dark:text-amber-200 cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="mt-0.5 h-4 w-4 rounded border-amber-400 text-amber-600 focus:ring-amber-500"
                                    checked={overLimit}
                                    onChange={(e) => setOverLimit(e.target.checked)}
                                />
                                <span>
                                    <strong className="block font-semibold">{classFull}</strong>
                                    <span className="block text-slate-500 dark:text-slate-400 mt-0.5">
                                        Tick to authorize administrator override and enroll anyway.
                                    </span>
                                </span>
                            </label>
                        )}
                    </DialogBody>

                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
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
                            disabled={
                                decisionMutation.isPending ||
                                (decision === "rejected" && !reason.trim()) ||
                                (Boolean(classFull) && !overLimit)
                            }
                            className={
                                decision === "approved"
                                    ? "bg-emerald-600 hover:bg-emerald-700 text-white min-w-[130px]"
                                    : decision === "rejected"
                                    ? "bg-rose-600 hover:bg-rose-700 text-white min-w-[130px]"
                                    : "bg-amber-600 hover:bg-amber-700 text-white min-w-[130px]"
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
