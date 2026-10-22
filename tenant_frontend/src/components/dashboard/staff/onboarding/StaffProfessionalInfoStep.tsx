"use client";

import React from 'react';
import { UseFormReturn } from 'react-hook-form';
import { FloatingLabelInput } from '@/components/ui/floating-label-input';

interface ProfessionalInfoStepProps {
    form: UseFormReturn<any>;
}

import { useRoles } from '@/hooks/useRoles';
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Label } from "@/components/ui/label";

export default function StaffProfessionalInfoStep({ form }: ProfessionalInfoStepProps) {
    const { register, setValue, watch, formState: { errors } } = form;
    const { data: roles, isLoading: loadingRoles } = useRoles();

    // Watch designation to show current value in Select
    const designation = watch("designation");

    return (
        <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-2">
                    <Label htmlFor="designation" className={errors.designation ? "text-red-500" : ""}>
                        Job title *
                    </Label>
                    <Select
                        onValueChange={(val) => {
                            setValue("designation", val, { shouldValidate: true });
                        }}
                        defaultValue={designation}
                    >
                        <SelectTrigger className="h-14 rounded-xl bg-slate-50 dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                            <SelectValue placeholder={loadingRoles ? "Loading roles..." : "Select a designation"} />
                        </SelectTrigger>
                        <SelectContent>
                            {loadingRoles ? (
                                <SelectItem value="loading" disabled>Loading...</SelectItem>
                            ) : Array.isArray(roles) ? (
                                roles.map((role) => (
                                    <SelectItem key={role.id} value={role.name}>
                                        {role.name}
                                    </SelectItem>
                                ))
                            ) : (
                                <SelectItem value="no-roles" disabled>No roles found</SelectItem>
                            )}
                        </SelectContent>
                    </Select>
                    {errors.designation && (
                        <p className="text-sm font-medium text-red-500">{errors.designation.message as string}</p>
                    )}
                </div>

                <FloatingLabelInput
                    id="department"
                    label="Department (e.g., Finance)"
                    {...register('department')}
                    error={errors.department?.message as string}
                />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <FloatingLabelInput
                    id="qualification"
                    label="Qualification (e.g., MBA)"
                    {...register('qualification')}
                    error={errors.qualification?.message as string}
                />
                <FloatingLabelInput
                    id="joining_date"
                    label="Joining Date"
                    type="date"
                    {...register('joining_date')}
                    error={errors.joining_date?.message as string}
                />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <FloatingLabelInput
                    id="experience_years"
                    label="Years of Experience"
                    type="number"
                    {...register('experience_years', { valueAsNumber: true })}
                    error={errors.experience_years?.message as string}
                />
            </div>
        </div>
    );
}
