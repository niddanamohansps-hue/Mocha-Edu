"use client";

import React from "react";
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
import { User, Calendar, Phone, Mail, MapPin } from "lucide-react";

interface PersonalDetailsStepProps {
    form: UseFormReturn<any>;
}

export default function PersonalDetailsStep({ form }: PersonalDetailsStepProps) {
    const {
        register,
        formState: { errors },
        setValue,
        watch,
    } = form;

    const currentGender = watch("gender") || "male";

    return (
        <div className="space-y-4">
            {/* Student Full Name (3-column grid) */}
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
                <div className="space-y-1.5">
                    <Label htmlFor="first_name" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        First Name <span className="text-rose-500">*</span>
                    </Label>
                    <Input
                        id="first_name"
                        placeholder="e.g. Aarav"
                        {...register("first_name")}
                        className={`h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                            errors.first_name ? "border-rose-400 focus:border-rose-500 focus:ring-rose-500/20" : ""
                        }`}
                    />
                    {errors.first_name && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.first_name.message as string}</p>
                    )}
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="middle_name" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Middle Name <span className="text-slate-400 font-normal">(Optional)</span>
                    </Label>
                    <Input
                        id="middle_name"
                        placeholder="e.g. Kumar"
                        {...register("middle_name")}
                        className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="last_name" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Last Name <span className="text-rose-500">*</span>
                    </Label>
                    <Input
                        id="last_name"
                        placeholder="e.g. Sharma"
                        {...register("last_name")}
                        className={`h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                            errors.last_name ? "border-rose-400 focus:border-rose-500 focus:ring-rose-500/20" : ""
                        }`}
                    />
                    {errors.last_name && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.last_name.message as string}</p>
                    )}
                </div>
            </div>

            {/* Demographics & Contact (4-column grid) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 pt-1">
                <div className="space-y-1.5">
                    <Label htmlFor="gender" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Gender <span className="text-rose-500">*</span>
                    </Label>
                    <Select
                        value={currentGender}
                        onValueChange={(val) => setValue("gender", val, { shouldValidate: true })}
                    >
                        <SelectTrigger
                            id="gender"
                            className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                        >
                            <SelectValue placeholder="Select gender" />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="male" className="text-xs">Male</SelectItem>
                            <SelectItem value="female" className="text-xs">Female</SelectItem>
                            <SelectItem value="other" className="text-xs">Other</SelectItem>
                        </SelectContent>
                    </Select>
                    {errors.gender && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.gender.message as string}</p>
                    )}
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="date_of_birth" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Date of Birth <span className="text-rose-500">*</span>
                    </Label>
                    <div className="relative">
                        <Input
                            id="date_of_birth"
                            type="date"
                            {...register("date_of_birth")}
                            className={`h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                                errors.date_of_birth ? "border-rose-400 focus:border-rose-500 focus:ring-rose-500/20" : ""
                            }`}
                        />
                    </div>
                    {errors.date_of_birth && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.date_of_birth.message as string}</p>
                    )}
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="phone" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Student Phone <span className="text-slate-400 font-normal">(Optional)</span>
                    </Label>
                    <div className="relative">
                        <Phone className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="phone"
                            placeholder="+91-9876543210"
                            {...register("phone")}
                            className="pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                        />
                    </div>
                    {errors.phone && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.phone.message as string}</p>
                    )}
                </div>

                <div className="space-y-1.5">
                    <Label htmlFor="email" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                        Student Email <span className="text-slate-400 font-normal">(Optional)</span>
                    </Label>
                    <div className="relative">
                        <Mail className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                        <Input
                            id="email"
                            type="email"
                            placeholder="student@example.com"
                            {...register("email")}
                            className={`pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                                errors.email ? "border-rose-400 focus:border-rose-500" : ""
                            }`}
                        />
                    </div>
                    {errors.email && (
                        <p className="text-[11px] font-medium text-rose-500">{errors.email.message as string}</p>
                    )}
                </div>
            </div>

            {/* Address */}
            <div className="space-y-1.5 pt-1">
                <Label htmlFor="address" className="text-xs font-semibold text-slate-700 dark:text-slate-300">
                    Current Residential Address <span className="text-rose-500">*</span>
                </Label>
                <div className="relative">
                    <MapPin className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
                    <Input
                        id="address"
                        placeholder="House / Flat No, Street, Landmark, City, State, PIN Code"
                        {...register("address")}
                        className={`pl-8 h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20 ${
                            errors.address ? "border-rose-400 focus:border-rose-500" : ""
                        }`}
                    />
                </div>
                {errors.address && (
                    <p className="text-[11px] font-medium text-rose-500">{errors.address.message as string}</p>
                )}
            </div>
        </div>
    );
}
