"use client";

import React from "react";
import { UseFormReturn, useFieldArray } from "react-hook-form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, Users, ShieldCheck, Phone, Briefcase } from "lucide-react";

interface GuardianDetailsStepProps {
    form: UseFormReturn<any>;
}

export default function GuardianDetailsStep({ form }: GuardianDetailsStepProps) {
    const {
        register,
        control,
        setValue,
        watch,
        formState: { errors },
    } = form;

    const { fields, append, remove } = useFieldArray({
        control,
        name: "parents",
    });

    const parentsErrors = errors.parents as any;

    return (
        <div className="space-y-4">
            {/* Guardian Cards */}
            <div className="space-y-3.5">
                {fields.map((field, index) => {
                    const isPrimary = index === 0;
                    const relationValue = watch(`parents.${index}.relation`) || (isPrimary ? "father" : "mother");
                    const genderValue = watch(`parents.${index}.gender`) || (relationValue === "mother" ? "female" : "male");
                    const isPrimaryChecked = watch(`parents.${index}.is_primary`) ?? isPrimary;

                    return (
                        <div
                            key={field.id}
                            className={`p-4 rounded-xl border transition-all ${
                                isPrimary
                                    ? "bg-slate-50/50 dark:bg-slate-900/40 border-slate-200/80 dark:border-slate-800"
                                    : "bg-white dark:bg-slate-900 border-slate-200/70 dark:border-slate-800"
                            }`}
                        >
                            {/* Card Header */}
                            <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-100 dark:border-slate-800">
                                <div className="flex items-center gap-2">
                                    <div className="h-6 w-6 rounded-lg bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 flex items-center justify-center font-bold text-xs">
                                        {index + 1}
                                    </div>
                                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200">
                                        {isPrimary ? "Primary Guardian / Parent" : `Secondary Guardian (${index + 1})`}
                                    </span>
                                    {isPrimary && (
                                        <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 font-semibold text-[10px] py-0">
                                            Required
                                        </Badge>
                                    )}
                                </div>

                                {!isPrimary && (
                                    <Button
                                        type="button"
                                        variant="ghost"
                                        size="sm"
                                        onClick={() => remove(index)}
                                        className="h-7 px-2 text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 text-xs"
                                    >
                                        <Trash2 className="h-3.5 w-3.5 mr-1" />
                                        <span>Remove</span>
                                    </Button>
                                )}
                            </div>

                            {/* Inputs Grid */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                                {/* Relation */}
                                <div className="space-y-1.5">
                                    <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Relationship <span className="text-rose-500">*</span>
                                    </Label>
                                    <Select
                                        value={relationValue}
                                        onValueChange={(val) => {
                                            setValue(`parents.${index}.relation`, val, { shouldValidate: true });
                                            // Automatically set gender heuristic if mother/father
                                            if (val === "mother") setValue(`parents.${index}.gender`, "female");
                                            if (val === "father") setValue(`parents.${index}.gender`, "male");
                                        }}
                                    >
                                        <SelectTrigger className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                                            <SelectValue placeholder="Relation" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="father" className="text-xs">Father</SelectItem>
                                            <SelectItem value="mother" className="text-xs">Mother</SelectItem>
                                            <SelectItem value="guardian" className="text-xs">Legal Guardian</SelectItem>
                                            <SelectItem value="other" className="text-xs">Other Relation</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                {/* First Name */}
                                <div className="space-y-1.5">
                                    <Label htmlFor={`parents.${index}.first_name`} className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        First Name <span className="text-rose-500">*</span>
                                    </Label>
                                    <Input
                                        id={`parents.${index}.first_name`}
                                        placeholder="e.g. Ramesh"
                                        {...register(`parents.${index}.first_name`)}
                                        className={`h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                                            parentsErrors?.[index]?.first_name ? "border-rose-400" : ""
                                        }`}
                                    />
                                    {parentsErrors?.[index]?.first_name && (
                                        <p className="text-[11px] font-medium text-rose-500">
                                            {parentsErrors[index].first_name.message}
                                        </p>
                                    )}
                                </div>

                                {/* Last Name */}
                                <div className="space-y-1.5">
                                    <Label htmlFor={`parents.${index}.last_name`} className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Last Name <span className="text-rose-500">*</span>
                                    </Label>
                                    <Input
                                        id={`parents.${index}.last_name`}
                                        placeholder="e.g. Sharma"
                                        {...register(`parents.${index}.last_name`)}
                                        className={`h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                                            parentsErrors?.[index]?.last_name ? "border-rose-400" : ""
                                        }`}
                                    />
                                    {parentsErrors?.[index]?.last_name && (
                                        <p className="text-[11px] font-medium text-rose-500">
                                            {parentsErrors[index].last_name.message}
                                        </p>
                                    )}
                                </div>

                                {/* Phone */}
                                <div className="space-y-1.5">
                                    <Label htmlFor={`parents.${index}.phone`} className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Phone Number <span className="text-rose-500">*</span>
                                    </Label>
                                    <div className="relative">
                                        <Phone className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                                        <Input
                                            id={`parents.${index}.phone`}
                                            placeholder="+91-9876543210"
                                            {...register(`parents.${index}.phone`)}
                                            className={`pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                                                parentsErrors?.[index]?.phone ? "border-rose-400" : ""
                                            }`}
                                        />
                                    </div>
                                    {parentsErrors?.[index]?.phone && (
                                        <p className="text-[11px] font-medium text-rose-500">
                                            {parentsErrors[index].phone.message}
                                        </p>
                                    )}
                                </div>
                            </div>

                            {/* Secondary Row: Occupation & Primary Flag */}
                            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 pt-3">
                                <div className="space-y-1.5">
                                    <Label htmlFor={`parents.${index}.occupation`} className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Occupation <span className="text-slate-400 font-normal">(Optional)</span>
                                    </Label>
                                    <div className="relative">
                                        <Briefcase className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                                        <Input
                                            id={`parents.${index}.occupation`}
                                            placeholder="e.g. Civil Engineer / Business"
                                            {...register(`parents.${index}.occupation`)}
                                            className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                                        />
                                    </div>
                                </div>

                                <div className="space-y-1.5">
                                    <Label className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                                        Gender
                                    </Label>
                                    <Select
                                        value={genderValue}
                                        onValueChange={(val) => setValue(`parents.${index}.gender`, val)}
                                    >
                                        <SelectTrigger className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                                            <SelectValue placeholder="Gender" />
                                        </SelectTrigger>
                                        <SelectContent>
                                            <SelectItem value="male" className="text-xs">Male</SelectItem>
                                            <SelectItem value="female" className="text-xs">Female</SelectItem>
                                            <SelectItem value="other" className="text-xs">Other</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>

                                <div className="sm:col-span-2 flex items-center pt-5 pl-1">
                                    <label className="flex items-center gap-2.5 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            {...register(`parents.${index}.is_primary`)}
                                            defaultChecked={isPrimary}
                                            className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 rounded-sm"
                                        />
                                        <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                                            Mark as primary contact for emergency notifications & SMS alerts
                                        </span>
                                    </label>
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* If zero parents (fallback), or Add Secondary button */}
            <div className="flex items-center justify-between pt-1">
                {fields.length < 2 ? (
                    <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() =>
                            append({
                                first_name: "",
                                last_name: "",
                                phone: "",
                                gender: "female",
                                relation: "mother",
                                occupation: "",
                                is_primary: false,
                            })
                        }
                        className="h-9 px-3 gap-1.5 text-xs font-semibold rounded-lg border-dashed border-slate-300 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:border-sky-400 hover:text-sky-600 dark:hover:text-sky-400 cursor-pointer"
                    >
                        <Plus className="h-3.5 w-3.5" />
                        <span>Add Secondary Guardian (e.g. Mother / Co-Guardian)</span>
                    </Button>
                ) : (
                    <span className="text-[11px] text-slate-400">
                        Maximum 2 guardians configured for direct walk-in enrollment.
                    </span>
                )}

                {errors.parents?.message && (
                    <p className="text-[11px] font-medium text-rose-500">
                        {errors.parents.message as string}
                    </p>
                )}
            </div>
        </div>
    );
}
