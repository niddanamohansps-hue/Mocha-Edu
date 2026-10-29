"use client";

import React from "react";
import { UseFormReturn } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Award, BookOpen, Clock, FileText } from "lucide-react";

interface ProfessionalInfoStepProps {
    form: UseFormReturn<any>;
}

export default function ProfessionalInfoStep({ form }: ProfessionalInfoStepProps) {
    const {
        register,
        formState: { errors },
    } = form;

    return (
        <div className="space-y-4">
            {/* Specialization & Qualification */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="space-y-1.5">
                    <Label htmlFor="specialization" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Subject Specialization <span className="text-slate-400 font-normal">(e.g. Mathematics, Physics)</span>
                    </Label>
                    <div className="relative">
                        <BookOpen className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="specialization"
                            placeholder="e.g. Senior Secondary Mathematics"
                            {...register("specialization")}
                            className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="inst_qualification" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Academic Qualification
                    </Label>
                    <div className="relative">
                        <Award className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="inst_qualification"
                            placeholder="e.g. M.Sc, M.Ed, Ph.D"
                            {...register("qualification")}
                            className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>
                </div>
            </div>

            {/* Joining Date & Experience */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5 pt-1">
                <div className="space-y-1.5">
                    <Label htmlFor="inst_joining_date" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Joining Date
                    </Label>
                    <Input
                        id="inst_joining_date"
                        type="date"
                        {...register("joining_date")}
                        className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="inst_experience" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Teaching Experience <span className="text-slate-400 font-normal">(Years)</span>
                    </Label>
                    <div className="relative">
                        <Clock className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="inst_experience"
                            type="number"
                            min="0"
                            step="0.5"
                            placeholder="0"
                            {...register("experience_years", { valueAsNumber: true })}
                            className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>
                </div>
            </div>

            {/* Short Bio */}
            <div className="space-y-1.5 pt-1">
                <Label htmlFor="inst_bio" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Faculty Bio & Academic Summary <span className="text-slate-400 font-normal">(Optional)</span>
                </Label>
                <div className="relative">
                    <FileText className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                    <Input
                        id="inst_bio"
                        placeholder="Brief summary of teaching background, achievements, and pedagogy focus"
                        {...register("bio")}
                        className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                </div>
            </div>
        </div>
    );
}
