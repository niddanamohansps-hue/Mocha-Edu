"use client";

import React from "react";
import { UseFormReturn } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useRoles } from "@/hooks/useRoles";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Briefcase, Building, Award, Calendar, Clock } from "lucide-react";

interface ProfessionalInfoStepProps {
    form: UseFormReturn<any>;
}

export default function StaffProfessionalInfoStep({ form }: ProfessionalInfoStepProps) {
    const {
        register,
        setValue,
        watch,
        formState: { errors },
    } = form;

    const { data: roles = [], isLoading: loadingRoles } = useRoles();
    const designation = watch("designation");

    return (
        <div className="space-y-4">
            {/* Designation & Department */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
                <div className="space-y-1.5">
                    <Label htmlFor="designation" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Job Title / Designation <span className="text-rose-500">*</span>
                    </Label>
                    <Select
                        value={designation || ""}
                        onValueChange={(val) => {
                            setValue("designation", val, { shouldValidate: true });
                        }}
                    >
                        <SelectTrigger
                            id="designation"
                            className={`h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 ${
                                errors.designation ? "border-rose-400" : ""
                            }`}
                        >
                            <SelectValue placeholder={loadingRoles ? "Loading roles..." : "Select designation / role"} />
                        </SelectTrigger>
                        <SelectContent>
                            {loadingRoles ? (
                                <SelectItem value="loading" disabled className="text-xs">
                                    Loading roles...
                                </SelectItem>
                            ) : Array.isArray(roles) && roles.length > 0 ? (
                                roles.map((role) => (
                                    <SelectItem key={role.id} value={role.name} className="text-xs">
                                        {role.name}
                                    </SelectItem>
                                ))
                            ) : (
                                <SelectItem value="Teacher" className="text-xs">Teacher</SelectItem>
                            )}
                        </SelectContent>
                    </Select>
                    {errors.designation && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.designation.message as string}</p>
                    )}
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="department" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Department <span className="text-slate-400 font-normal">(Optional)</span>
                    </Label>
                    <div className="relative">
                        <Building className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="department"
                            placeholder="e.g. Science, Mathematics, Administration, Accounts"
                            {...register("department")}
                            className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>
                </div>
            </div>

            {/* Qualification & Joining Date */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 pt-1">
                <div className="space-y-1.5">
                    <Label htmlFor="qualification" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Highest Qualification <span className="text-slate-400 font-normal">(Optional)</span>
                    </Label>
                    <div className="relative">
                        <Award className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="qualification"
                            placeholder="e.g. M.Sc B.Ed, MBA, B.Tech"
                            {...register("qualification")}
                            className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="joining_date" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Joining Date <span className="text-slate-400 font-normal">(Optional)</span>
                    </Label>
                    <Input
                        id="joining_date"
                        type="date"
                        {...register("joining_date")}
                        className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="experience_years" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Years of Experience <span className="text-slate-400 font-normal">(Years)</span>
                    </Label>
                    <div className="relative">
                        <Clock className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="experience_years"
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
        </div>
    );
}
