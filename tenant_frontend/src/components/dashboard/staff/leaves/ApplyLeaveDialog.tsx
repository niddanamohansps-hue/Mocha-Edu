"use client";

import React, { useState } from "react";
import { useApplyLeave, useLeaveTypes, useMyLeaveBalances } from "@/hooks/useStaffLeaves";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
    FormSection,
    FormGrid,
    FormFieldWrapper,
} from "@/components/ui/form-layout";
import { Calendar, FileUp, Loader2 } from "lucide-react";

interface ApplyLeaveDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
}

export function ApplyLeaveDialog({ open, onOpenChange }: ApplyLeaveDialogProps) {
    const { data: leaveTypes = [] } = useLeaveTypes();
    const { data: balances = [] } = useMyLeaveBalances();
    const applyMutation = useApplyLeave();

    const [leaveTypeId, setLeaveTypeId] = useState<string>("");
    const [startDate, setStartDate] = useState<string>("");
    const [endDate, setEndDate] = useState<string>("");
    const [isHalfDay, setIsHalfDay] = useState<boolean>(false);
    const [halfDaySession, setHalfDaySession] = useState<string>("morning");
    const [reason, setReason] = useState<string>("");
    const [file, setFile] = useState<File | null>(null);

    const selectedType = leaveTypes.find((lt) => lt.id === leaveTypeId);
    const selectedBalance = balances.find((b) => b.leave_type === leaveTypeId);

    const handleStartDateChange = (val: string) => {
        setStartDate(val);
        if (isHalfDay || !endDate || endDate < val) {
            setEndDate(val);
        }
    };

    const handleHalfDayToggle = (checked: boolean) => {
        setIsHalfDay(checked);
        if (checked && startDate) {
            setEndDate(startDate);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!leaveTypeId || !startDate || !endDate || !reason.trim()) {
            return;
        }

        const formData = new FormData();
        formData.append("leave_type_id", leaveTypeId);
        formData.append("start_date", startDate);
        formData.append("end_date", isHalfDay ? startDate : endDate);
        formData.append("is_half_day", isHalfDay ? "true" : "false");
        if (isHalfDay) {
            formData.append("half_day_session", halfDaySession);
        }
        formData.append("reason", reason.trim());
        if (file) {
            formData.append("document", file);
        }

        applyMutation.mutate(formData, {
            onSuccess: () => {
                onOpenChange(false);
                // Reset form
                setLeaveTypeId("");
                setStartDate("");
                setEndDate("");
                setIsHalfDay(false);
                setReason("");
                setFile(null);
            },
        });
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl">
                <DialogHeader className="px-6 py-4.5 border-b border-slate-100 dark:border-slate-800 shrink-0">
                    <DialogTitle className="flex items-center gap-2 text-lg font-bold text-slate-900 dark:text-white">
                        <Calendar className="w-5 h-5 text-sky-600" />
                        Apply for Leave
                    </DialogTitle>
                    <DialogDescription className="text-xs text-slate-500">
                        Submit a leave request. Working days and quotas are calculated server-side.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0 overflow-hidden">
                    <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-5">
                        {/* Leave Type */}
                        <FormFieldWrapper label="Leave Category" htmlFor="leaveType" required>
                            <Select value={leaveTypeId} onValueChange={setLeaveTypeId} required>
                                <SelectTrigger id="leaveType">
                                    <SelectValue placeholder="Select leave category" />
                                </SelectTrigger>
                                <SelectContent>
                                    {leaveTypes.filter((t) => t.is_active).map((type) => {
                                        const bal = balances.find((b) => b.leave_type === type.id);
                                        const avail = bal ? bal.available_days : type.annual_allocation_days;
                                        return (
                                            <SelectItem key={type.id} value={type.id}>
                                                <div className="flex flex-wrap items-center justify-between gap-4 w-full">
                                                    <span>{type.name} ({type.code})</span>
                                                    <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">
                                                        {avail}d available
                                                    </span>
                                                </div>
                                            </SelectItem>
                                        );
                                    })}
                                </SelectContent>
                            </Select>

                            {selectedType && (
                                <div className="flex items-center gap-2 text-xs text-slate-500 pt-1.5">
                                    <span>{selectedType.is_paid ? "Paid Leave" : "Unpaid Leave"}</span>
                                    <span>•</span>
                                    <span>Max consecutive: {selectedType.max_consecutive_days ? `${selectedType.max_consecutive_days}d` : "None"}</span>
                                    {selectedType.requires_document && (
                                        <>
                                            <span>•</span>
                                            <span className="text-amber-600 font-medium">Document required</span>
                                        </>
                                    )}
                                </div>
                            )}
                        </FormFieldWrapper>

                        {/* Half Day Toggle */}
                        <div className="flex items-center justify-between gap-3 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50/60 dark:bg-slate-900/60">
                            <div className="space-y-0.5">
                                <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">Half-Day Leave</span>
                                <p className="text-[11px] text-slate-400">Apply for a 0.5-day morning or afternoon absence</p>
                            </div>
                            <Switch id="halfDay" checked={isHalfDay} onCheckedChange={handleHalfDayToggle} />
                        </div>

                        {/* Dates */}
                        <FormGrid>
                            <FormFieldWrapper label="Start Date" htmlFor="startDate" required>
                                <Input
                                    id="startDate"
                                    type="date"
                                    value={startDate}
                                    onChange={(e) => handleStartDateChange(e.target.value)}
                                    required
                                />
                            </FormFieldWrapper>

                            {!isHalfDay ? (
                                <FormFieldWrapper label="End Date" htmlFor="endDate" required>
                                    <Input
                                        id="endDate"
                                        type="date"
                                        min={startDate}
                                        value={endDate}
                                        onChange={(e) => setEndDate(e.target.value)}
                                        required
                                    />
                                </FormFieldWrapper>
                            ) : (
                                <FormFieldWrapper label="Session" htmlFor="session" required>
                                    <Select value={halfDaySession} onValueChange={setHalfDaySession}>
                                        <SelectTrigger id="session">
                                            <SelectValue />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="morning">Morning Session</SelectItem>
                                            <SelectItem value="afternoon">Afternoon Session</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </FormFieldWrapper>
                            )}
                        </FormGrid>

                        {/* Reason */}
                        <FormFieldWrapper label="Reason for Absence" htmlFor="reason" required colSpan="full">
                            <Textarea
                                id="reason"
                                rows={3}
                                placeholder="Provide reason for leave..."
                                value={reason}
                                onChange={(e) => setReason(e.target.value)}
                                required
                            />
                        </FormFieldWrapper>

                        {/* Document Upload */}
                        <FormFieldWrapper
                            label={
                                <span className="flex items-center gap-1.5">
                                    <FileUp className="w-3.5 h-3.5 text-slate-400" />
                                    <span>Supporting Proof {selectedType?.requires_document ? "(Mandatory *)" : "(Optional)"}</span>
                                </span>
                            }
                            htmlFor="docFile"
                            colSpan="full"
                        >
                            <Input
                                id="docFile"
                                type="file"
                                accept=".pdf,.jpg,.jpeg,.png,.docx"
                                onChange={(e) => setFile(e.target.files?.[0] || null)}
                                required={selectedType?.requires_document}
                                className="file:mr-3 file:py-1 file:px-2.5 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-sky-50 file:text-sky-700 hover:file:bg-sky-100"
                            />
                            <p className="text-[11px] text-slate-400 mt-1">
                                Accepted: PDF, JPG, PNG, DOCX (Max 5MB). Scanned for security.
                            </p>
                        </FormFieldWrapper>
                    </DialogBody>

                    <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={applyMutation.isPending} className="min-w-[120px]">
                            {applyMutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                            Submit Application
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}
