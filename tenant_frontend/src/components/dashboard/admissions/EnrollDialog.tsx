"use client";

import React, { useState } from "react";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { FormFieldWrapper } from "@/components/ui/form-layout";
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
            <DialogContent className="max-w-md max-h-[90vh] p-0 flex flex-col overflow-hidden rounded-2xl" showCloseButton={false}>
                <ModalHeader
                    icon={<GraduationCap className="w-5 h-5 text-sky-600" />}
                    title="Enroll Student"
                    subtitle="Generate official student enrollment record and allocate section."
                    onClose={handleClose}
                />

                {enrolledResult ? (
                    <div className="p-6 text-center space-y-4">
                        <div className="w-14 h-14 bg-emerald-100 text-emerald-600 dark:bg-emerald-950/60 dark:text-emerald-400 rounded-full flex items-center justify-center mx-auto shadow-inner">
                            <CheckCircle2 className="w-7 h-7" />
                        </div>
                        <div>
                            <h3 className="text-base font-bold text-slate-900 dark:text-white">
                                Student Enrolled Successfully!
                            </h3>
                            <p className="text-xs text-slate-500 mt-1">
                                An active student profile and academic record have been created.
                            </p>
                        </div>
                        <div className="p-3.5 bg-slate-50 dark:bg-slate-800/60 rounded-xl border border-slate-200/80 dark:border-slate-800 inline-block font-mono text-lg font-bold text-sky-600 dark:text-sky-400 tracking-wider">
                            {enrolledResult.enrollment_id}
                        </div>
                        <div className="pt-2">
                            <Button
                                onClick={handleClose}
                                className="w-full"
                            >
                                Done
                            </Button>
                        </div>
                    </div>
                ) : (
                    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
                        <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-4">
                            <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200/70 dark:border-slate-800 text-sm">
                                <div className="font-bold text-slate-900 dark:text-white">
                                    {application.first_name} {application.last_name}
                                </div>
                                <div className="text-xs text-slate-500 mt-1 flex flex-wrap items-center gap-2">
                                    <span>Target Grade: <strong className="text-slate-700 dark:text-slate-300">{application.level_name || application.level}</strong></span>
                                    <span>•</span>
                                    <span>Session: <strong className="text-slate-700 dark:text-slate-300">{application.academic_year}</strong></span>
                                </div>
                            </div>

                            <FormFieldWrapper label="Allocate Section / Division" htmlFor="sectionSelect" colSpan="full">
                                <Select value={sectionId} onValueChange={setSectionId}>
                                    <SelectTrigger id="sectionSelect">
                                        <SelectValue placeholder="Select section (optional)" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        <SelectItem value="none">
                                            <em>Unallocated (Assign Section Later)</em>
                                        </SelectItem>
                                        {availableSections.map((sec) => (
                                            <SelectItem key={sec.id} value={sec.id}>
                                                Section {sec.name} {sec.capacity ? `(Capacity: ${sec.capacity})` : ""}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </FormFieldWrapper>

                            {availableSections.length === 0 && (
                                <div className="p-3 bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 rounded-xl flex items-start gap-2.5 text-xs text-amber-800 dark:text-amber-200">
                                    <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
                                    <span>No active sections found for this grade level. The student can be enrolled unallocated and assigned later from the directory.</span>
                                </div>
                            )}
                        </DialogBody>

                        <DialogFooter className="px-6 py-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 flex items-center justify-end gap-3 shrink-0">
                            <Button
                                type="button"
                                variant="outline"
                                onClick={handleClose}
                                disabled={enrollMutation.isPending}
                            >
                                Cancel
                            </Button>
                            <Button
                                onClick={handleEnroll}
                                disabled={enrollMutation.isPending}
                                className="min-w-[120px]"
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
