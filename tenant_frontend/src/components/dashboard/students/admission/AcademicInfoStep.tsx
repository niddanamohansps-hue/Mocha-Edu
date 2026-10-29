"use client";

import React, { useEffect } from "react";
import { UseFormReturn } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useAcademicLevels, useSections, useAcademicYears } from "@/hooks/useAcademics";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { GraduationCap, School, Calendar } from "lucide-react";

interface AcademicInfoStepProps {
    form: UseFormReturn<any>;
}

export default function AcademicInfoStep({ form }: AcademicInfoStepProps) {
    const {
        register,
        formState: { errors },
        setValue,
        watch,
    } = form;

    const { selectedYear, currentYear } = useAcademicYear();
    const activeYear = selectedYear || currentYear;

    const { data: levels = [], isLoading: isLoadingLevels } = useAcademicLevels();
    const { data: allSections = [], isLoading: isLoadingSections } = useSections();
    const { data: years = [] } = useAcademicYears();

    const selectedLevelId = watch("level_id") || "";
    const selectedSectionId = watch("section_id") || "";
    const selectedAcademicYear = watch("academic_year") || activeYear?.name || "2026-27";

    // Auto-fill academic year if not yet set
    useEffect(() => {
        if (!watch("academic_year") && activeYear?.name) {
            setValue("academic_year", activeYear.name, { shouldValidate: true });
        }
    }, [activeYear, setValue, watch]);

    // Filter sections for the selected level
    const availableSections = allSections.filter((s) => s.level === selectedLevelId);

    return (
        <div className="space-y-4">
            {/* Academic Cohort & Placement Grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Academic Year */}
                <div className="space-y-1.5">
                    <Label htmlFor="academic_year" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Academic Year <span className="text-rose-500">*</span>
                    </Label>
                    <Select
                        value={selectedAcademicYear}
                        onValueChange={(val) => setValue("academic_year", val, { shouldValidate: true })}
                    >
                        <SelectTrigger
                            id="academic_year"
                            className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                        >
                            <SelectValue placeholder="Select Academic Year" />
                        </SelectTrigger>
                        <SelectContent>
                            {years.length > 0 ? (
                                years.map((y) => (
                                    <SelectItem key={y.id} value={y.name} className="text-xs">
                                        {y.name} {y.is_current ? "(Current)" : ""}
                                    </SelectItem>
                                ))
                            ) : (
                                <SelectItem value="2026-27" className="text-xs">2026-27 (Current)</SelectItem>
                            )}
                        </SelectContent>
                    </Select>
                    {errors.academic_year && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.academic_year.message as string}</p>
                    )}
                </div>

                {/* Enrolling Grade / Level */}
                <div className="space-y-1.5">
                    <Label htmlFor="level_id" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Grade / Class Level <span className="text-rose-500">*</span>
                    </Label>
                    <Select
                        value={selectedLevelId}
                        onValueChange={(val) => {
                            setValue("level_id", val, { shouldValidate: true });
                            setValue("section_id", ""); // Reset section on level switch
                        }}
                    >
                        <SelectTrigger
                            id="level_id"
                            className={`h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 ${
                                errors.level_id ? "border-rose-400" : ""
                            }`}
                        >
                            <SelectValue placeholder={isLoadingLevels ? "Loading classes..." : "Select Class / Grade"} />
                        </SelectTrigger>
                        <SelectContent>
                            {levels.map((lvl) => (
                                <SelectItem key={lvl.id} value={lvl.id} className="text-xs">
                                    {lvl.name} {lvl.program_name ? `(${lvl.program_name})` : ""}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                    {errors.level_id && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.level_id.message as string}</p>
                    )}
                </div>

                {/* Section Allocation */}
                <div className="space-y-1.5">
                    <Label htmlFor="section_id" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Section Allocation <span className="text-slate-400 font-normal">(Optional)</span>
                    </Label>
                    <Select
                        value={selectedSectionId}
                        onValueChange={(val) => setValue("section_id", val === "unassigned" ? "" : val)}
                        disabled={!selectedLevelId}
                    >
                        <SelectTrigger
                            id="section_id"
                            className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                        >
                            <SelectValue
                                placeholder={
                                    !selectedLevelId
                                        ? "Choose Grade First"
                                        : availableSections.length === 0
                                        ? "No Sections Configured"
                                        : "Select Section (or unassigned)"
                                }
                            />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="unassigned" className="text-xs text-slate-400">
                                Unassigned / Auto-allocate
                            </SelectItem>
                            {availableSections.map((sec) => (
                                <SelectItem key={sec.id} value={sec.id} className="text-xs">
                                    Section {sec.name} {sec.capacity ? `(Cap: ${sec.capacity})` : ""}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                {/* Admission Date */}
                <div className="space-y-1.5">
                    <Label htmlFor="admission_date" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Date of Admission <span className="text-slate-400 font-normal">(Default: Today)</span>
                    </Label>
                    <Input
                        id="admission_date"
                        type="date"
                        {...register("admission_date")}
                        className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                </div>
            </div>

            {/* Previous Academic History */}
            <div className="pt-2">
                <div className="flex items-center gap-2 mb-3">
                    <School className="w-3.5 h-3.5 text-slate-400" />
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                        Prior Schooling & Transfer History (Optional)
                    </span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                    <div className="space-y-1.5">
                        <Label htmlFor="previous_school" className="text-xs font-medium text-slate-600 dark:text-slate-400">
                            Previous School Name
                        </Label>
                        <Input
                            id="previous_school"
                            placeholder="e.g. St. Xavier's High School"
                            {...register("previous_school")}
                            className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>

                    <div className="space-y-1.5">
                        <Label htmlFor="last_grade_passed" className="text-xs font-medium text-slate-600 dark:text-slate-400">
                            Last Grade / Class Passed
                        </Label>
                        <Input
                            id="last_grade_passed"
                            placeholder="e.g. Grade 5 / Percentage: 88%"
                            {...register("last_grade_passed")}
                            className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
