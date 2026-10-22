"use client";

import React, { useState } from "react";
import { useApplyLeave, useLeaveTypes, useMyLeaveBalances } from "@/hooks/useStaffLeaves";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { AlertCircle, Calendar, FileUp, Loader2 } from "lucide-react";

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
            <DialogContent className="sm:max-w-lg max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Calendar className="w-5 h-5 text-indigo-600" />
                        Apply for Leave
                    </DialogTitle>
                    <DialogDescription>
                        Submit a leave request. Working days and quotas are calculated server-side.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={handleSubmit} className="space-y-4 pt-2">
                    {/* Leave Type */}
                    <div className="space-y-1.5">
                        <Label htmlFor="leaveType">Leave Type *</Label>
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
                            <div className="flex items-center gap-2 text-xs text-slate-500 pt-1">
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
                    </div>

                    {/* Half Day Toggle */}
                    <div className="flex flex-wrap items-center justify-between gap-2 p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                        <div className="space-y-0.5">
                            <Label htmlFor="halfDay" className="text-sm font-medium">Half-Day Leave</Label>
                            <p className="text-xs text-slate-500">Apply for a 0.5-day morning or afternoon absence</p>
                        </div>
                        <Switch id="halfDay" checked={isHalfDay} onCheckedChange={handleHalfDayToggle} />
                    </div>

                    {/* Dates */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div className="space-y-1.5">
                            <Label htmlFor="startDate">Start Date *</Label>
                            <Input
                                id="startDate"
                                type="date"
                                value={startDate}
                                onChange={(e) => handleStartDateChange(e.target.value)}
                                required
                            />
                        </div>

                        {!isHalfDay ? (
                            <div className="space-y-1.5">
                                <Label htmlFor="endDate">End Date *</Label>
                                <Input
                                    id="endDate"
                                    type="date"
                                    min={startDate}
                                    value={endDate}
                                    onChange={(e) => setEndDate(e.target.value)}
                                    required
                                />
                            </div>
                        ) : (
                            <div className="space-y-1.5">
                                <Label htmlFor="session">Session *</Label>
                                <Select value={halfDaySession} onValueChange={setHalfDaySession}>
                                    <SelectTrigger id="session">
                                        <SelectValue />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="morning">Morning Session</SelectItem>
                                        <SelectItem value="afternoon">Afternoon Session</SelectItem>
                                    </SelectContent>
                                </Select>
                            </div>
                        )}
                    </div>

                    {/* Reason */}
                    <div className="space-y-1.5">
                        <Label htmlFor="reason">Reason for Absence *</Label>
                        <Textarea
                            id="reason"
                            rows={3}
                            placeholder="Provide reason for leave..."
                            value={reason}
                            onChange={(e) => setReason(e.target.value)}
                            required
                        />
                    </div>

                    {/* Document Upload */}
                    <div className="space-y-1.5">
                        <Label htmlFor="docFile" className="flex items-center gap-2">
                            <FileUp className="w-4 h-4 text-slate-500" />
                            <span>Supporting Proof {selectedType?.requires_document ? "(Mandatory *)" : "(Optional)"}</span>
                        </Label>
                        <Input
                            id="docFile"
                            type="file"
                            accept=".pdf,.jpg,.jpeg,.png,.docx"
                            onChange={(e) => setFile(e.target.files?.[0] || null)}
                            required={selectedType?.requires_document}
                        />
                        <p className="text-[11px] text-slate-400">
                            Accepted: PDF, JPG, PNG, DOCX (Max 5MB). Scanned for security.
                        </p>
                    </div>

                    <DialogFooter className="pt-2">
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={applyMutation.isPending} className="bg-indigo-600 hover:bg-indigo-700">
                            {applyMutation.isPending && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                            Submit Application
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

