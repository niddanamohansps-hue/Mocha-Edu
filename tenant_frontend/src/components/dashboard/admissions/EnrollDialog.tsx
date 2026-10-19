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
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useSections } from "@/hooks/useAcademics";
import { useEnrollApplication } from "@/hooks/useAdmissions";
import { AdmissionApplication } from "@/types/Admissions";
import { Loader2, GraduationCap, AlertCircle, CheckCircle2 } from "lucide-react";

interface EnrollDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    application: AdmissionApplication | null;
}

export default function EnrollDialog({
    open,
    onOpenChange,
    application,
}: EnrollDialogProps) {
    const { data: allSections = [] } = useSections();
    const enrollMutation = useEnrollApplication();

    const [sectionId, setSectionId] = useState<string>("none");
    const [enrolledResult, setEnrolledResult] = useState<{
        enrollment_id: string;
        student_id: string;
    } | null>(null);

    if (!application) return null;

    // Filter sections for this application's level
    const availableSections = allSections.filter((s) => s.level === application.level);

    const handleEnroll = () => {
        enrollMutation.mutate(
            {
                id: application.id,
                section_id: sectionId === "none" ? null : sectionId,
            },
            {
                onSuccess: (data) => {
                    setEnrolledResult({
                        enrollment_id: data.enrollment_id,
                        student_id: data.student_id,
                    });
                },
            }
        );
    };

    const handleClose = () => {
        setEnrolledResult(null);
        setSectionId("none");
        onOpenChange(false);
    };

    return (
        <Dialog open={open} onOpenChange={handleClose}>
            <DialogContent className="max-w-md rounded-3xl">
                <DialogHeader>
                    <DialogTitle className="text-xl font-bold flex items-center gap-2">
                        <GraduationCap className="w-5 h-5 text-teal-600" />
                        Enroll Student
                    </DialogTitle>
                </DialogHeader>

                {enrolledResult ? (
                    <div className="py-6 text-center space-y-4">
                        <div className="w-16 h-16 bg-emerald-100 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400 rounded-full flex items-center justify-center mx-auto shadow-inner">
                            <CheckCircle2 className="w-8 h-8" />
                        </div>
                        <div>
                            <h3 className="text-lg font-bold text-slate-800 dark:text-white">
                                Student Enrolled Successfully!
                            </h3>
                            <p className="text-sm text-slate-500 mt-1">
                                An active student profile and academic record have been created.
                            </p>
                        </div>
                        <div className="p-4 bg-slate-50 dark:bg-slate-800/60 rounded-2xl border border-slate-200/80 dark:border-slate-800 inline-block font-mono text-xl font-bold text-teal-600 dark:text-teal-400 tracking-wider">
                            {enrolledResult.enrollment_id}
                        </div>
                        <div>
                            <Button
                                onClick={handleClose}
                                className="bg-teal-600 hover:bg-teal-700 text-white rounded-xl px-6"
                            >
                                Done
                            </Button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4 pt-2">
                        <div className="p-4 rounded-2xl bg-teal-50 dark:bg-teal-950/40 border border-teal-100 dark:border-teal-900 text-sm space-y-1">
                            <div className="font-bold text-teal-900 dark:text-teal-200">
                                {application.first_name} {application.last_name}
                            </div>
                            <div className="text-xs text-teal-700 dark:text-teal-300">
                                Application: {application.application_number}
                            </div>
                            <div className="text-xs text-teal-700 dark:text-teal-300">
                                Grade: {application.level_name || application.level} · Year: {application.academic_year}
                            </div>
                        </div>

                        <div className="flex items-start gap-2 p-3 rounded-xl bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 border border-amber-200/60 dark:border-amber-900/40 text-xs">
                            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600" />
                            <span>
                                This action is permanent and transactionally converts the applicant into an official active student in the school registry.
                            </span>
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="sectionSelect">Assign Section / Classroom (Optional)</Label>
                            <Select value={sectionId} onValueChange={setSectionId}>
                                <SelectTrigger id="sectionSelect">
                                    <SelectValue placeholder="Select section (or unassigned)" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="none">No Section Assigned Yet</SelectItem>
                                    {availableSections.map((s) => (
                                        <SelectItem key={s.id} value={s.id}>
                                            Section {s.name} (Capacity: {s.capacity || 40})
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>

                        <DialogFooter className="gap-2 sm:gap-0 pt-4 border-t">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleClose}
                                disabled={enrollMutation.isPending}
                            >
                                Cancel
                            </Button>
                            <Button
                                type="button"
                                onClick={handleEnroll}
                                disabled={enrollMutation.isPending}
                                className="bg-teal-600 hover:bg-teal-700 text-white font-semibold"
                            >
                                {enrollMutation.isPending && (
                                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                )}
                                Confirm Enrollment
                            </Button>
                        </DialogFooter>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

