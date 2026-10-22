"use client";

import React, { useState } from "react";
import { AffectedPeriodSlot, SubstituteCandidate } from "@/types/Leave";
import { useAffectedPeriods, useAssignSubstitution } from "@/hooks/useStaffLeaves";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Clock, UserCheck, AlertCircle, CheckCircle2, Loader2, Sparkles } from "lucide-react";

interface AffectedPeriodsModalProps {
    applicationId: string | null;
    onClose: () => void;
}

export function AffectedPeriodsModal({ applicationId, onClose }: AffectedPeriodsModalProps) {
    const { data: slots = [], isLoading } = useAffectedPeriods(applicationId || undefined);
    const assignMutation = useAssignSubstitution();

    const [selectedSlot, setSelectedSlot] = useState<AffectedPeriodSlot | null>(null);
    const [substituteId, setSubstituteId] = useState<string>("");
    const [reason, setReason] = useState<string>("Leave coverage");

    if (!applicationId) return null;

    const handleAssign = (slot: AffectedPeriodSlot) => {
        if (!substituteId) return;
        assignMutation.mutate(
            {
                entry_id: slot.entry_id,
                date: slot.date,
                substitute_instructor_id: parseInt(substituteId, 10),
                reason,
            },
            {
                onSuccess: () => {
                    setSelectedSlot(null);
                    setSubstituteId("");
                },
            }
        );
    };

    return (
        <Dialog open={!!applicationId} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Clock className="w-5 h-5 text-indigo-600" />
                        Timetable Impact & Substitute Teachers
                    </DialogTitle>
                    <DialogDescription>
                        Review scheduled teaching periods affected by this leave and assign available substitute faculty.
                    </DialogDescription>
                </DialogHeader>

                {isLoading ? (
                    <div className="py-12 flex justify-center">
                        <Loader2 className="w-8 h-8 animate-spin text-slate-400" />
                    </div>
                ) : slots.length === 0 ? (
                    <div className="p-8 text-center rounded-xl border border-dashed border-slate-200 dark:border-slate-800 text-slate-500">
                        <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-emerald-500 opacity-60" />
                        <p className="font-medium text-sm text-slate-800 dark:text-slate-200">No Teaching Periods Impacted</p>
                        <p className="text-xs text-slate-400 mt-1">
                            This staff member has no timetable entries scheduled during this leave period.
                        </p>
                    </div>
                ) : (
                    <div className="space-y-3 pt-1">
                        {slots.map((slot, index) => {
                            const isAssigning = selectedSlot?.entry_id === slot.entry_id && selectedSlot?.date === slot.date;

                            return (
                                <div
                                    key={`${slot.entry_id}-${slot.date}-${index}`}
                                    className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 shadow-sm space-y-2.5"
                                >
                                    <div className="flex flex-wrap items-start justify-between gap-2">
                                        <div>
                                            <div className="flex items-center gap-2">
                                                <Badge variant="outline" className="text-xs font-mono">
                                                    {slot.date} ({slot.day_of_week})
                                                </Badge>
                                                <span className="font-semibold text-sm text-slate-900 dark:text-white">
                                                    {slot.period.name} ({slot.period.start_time} - {slot.period.end_time})
                                                </span>
                                            </div>
                                            <p className="text-xs text-slate-500 mt-1">
                                                Section: <span className="font-medium text-slate-700 dark:text-slate-300">{slot.section}</span> •{" "}
                                                Subject: <span className="font-medium text-slate-700 dark:text-slate-300">{slot.subject}</span>
                                                {slot.room && ` • Room: ${slot.room}`}
                                            </p>
                                        </div>

                                        {slot.existing_substitution ? (
                                            <Badge className="bg-emerald-600 gap-1 text-xs">
                                                <CheckCircle2 className="w-3 h-3" />
                                                Substituted: {slot.existing_substitution.substitute_instructor}
                                            </Badge>
                                        ) : (
                                            <Badge variant="secondary" className="text-amber-600 bg-amber-50 dark:bg-amber-950/40 text-xs">
                                                Coverage Needed
                                            </Badge>
                                        )}
                                    </div>

                                    {/* Action Bar / Form */}
                                    {!slot.existing_substitution && (
                                        <div className="pt-2 border-t border-slate-100 dark:border-slate-800/80">
                                            {isAssigning ? (
                                                <div className="space-y-2.5 p-2.5 rounded-lg bg-slate-50 dark:bg-slate-900 border border-slate-200 dark:border-slate-800">
                                                    <div className="space-y-1">
                                                        <label className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                                            Available Substitute Faculty ({slot.eligible_substitutes.length} free)
                                                        </label>
                                                        <Select value={substituteId} onValueChange={setSubstituteId}>
                                                            <SelectTrigger className="h-9 text-xs">
                                                                <SelectValue placeholder="Select substitute teacher" />
                                                            </SelectTrigger>
                                                            <SelectContent>
                                                                {slot.eligible_substitutes.map((cand) => (
                                                                    <SelectItem key={cand.instructor_id} value={String(cand.instructor_id)}>
                                                                        <div className="flex items-center gap-2">
                                                                            <span>{cand.name}</span>
                                                                            <span className="text-slate-400 font-normal">({cand.specialization})</span>
                                                                            {cand.is_same_subject && (
                                                                                <span className="text-[10px] bg-indigo-50 text-indigo-700 px-1 py-0.5 rounded font-medium">
                                                                                    Subject Match
                                                                                </span>
                                                                            )}
                                                                        </div>
                                                                    </SelectItem>
                                                                ))}
                                                            </SelectContent>
                                                        </Select>
                                                    </div>

                                                    <div className="flex justify-end gap-2 pt-1">
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => setSelectedSlot(null)}
                                                            disabled={assignMutation.isPending}
                                                        >
                                                            Cancel
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            onClick={() => handleAssign(slot)}
                                                            disabled={!substituteId || assignMutation.isPending}
                                                            className="bg-indigo-600 hover:bg-indigo-700"
                                                        >
                                                            {assignMutation.isPending && <Loader2 className="w-3.5 h-3.5 mr-1.5 animate-spin" />}
                                                            Confirm Assignment
                                                        </Button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <div className="flex flex-wrap items-center justify-between gap-2">
                                                    <span className="text-xs text-slate-500">
                                                        {slot.eligible_substitutes.length} faculty free this period
                                                    </span>
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        className="h-8 text-xs text-indigo-600 hover:text-indigo-700"
                                                        onClick={() => {
                                                            setSelectedSlot(slot);
                                                            setSubstituteId("");
                                                        }}
                                                    >
                                                        <UserCheck className="w-3.5 h-3.5 mr-1" />
                                                        Assign Substitute
                                                    </Button>
                                                </div>
                                            )}
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

