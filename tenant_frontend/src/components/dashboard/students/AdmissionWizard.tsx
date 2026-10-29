"use client";

import React, { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
    User,
    GraduationCap,
    Users,
    Sparkles,
    CheckCircle2,
    Loader2,
    ShieldCheck,
    ChevronDown,
    RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
    useEnrollStudent,
    useUpdateStudent,
    useStudent,
    StudentEnrollmentData,
} from "@/hooks/useStudents";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { useRouter } from "next/navigation";

// Sub-components
import PersonalDetailsStep from "./admission/PersonalDetailsStep";
import AcademicInfoStep from "./admission/AcademicInfoStep";
import GuardianDetailsStep from "./admission/GuardianDetailsStep";

const enrollmentSchema = z.object({
    // Personal Info
    first_name: z.string().min(2, "First name is required"),
    middle_name: z.string().optional(),
    last_name: z.string().min(2, "Last name is required"),
    email: z
        .string()
        .email("Invalid email")
        .optional()
        .or(z.literal(""))
        .transform((val) => (val === "" ? undefined : val)),
    gender: z.enum(["male", "female", "other"]),
    date_of_birth: z.string().min(1, "Date of birth is required"),
    phone: z.string().optional(),
    address: z.string().min(1, "Current address is required"),

    // Academic Info
    level_id: z.string().min(1, "Grade level is required"),
    section_id: z.string().optional(),
    academic_year: z.string().min(1, "Academic year is required"),
    admission_date: z
        .string()
        .optional()
        .or(z.literal(""))
        .transform((val) => (val === "" ? undefined : val)),
    previous_school: z.string().optional(),
    last_grade_passed: z.string().optional(),

    // Statutory Indian Compliance (Optional)
    apaar_id: z.string().optional(),
    pen: z.string().optional(),
    caste_category: z.string().optional(),
    is_rte: z.boolean().optional(),
    aadhaar_last_4: z.string().optional(),

    // Parents
    parents: z
        .array(
            z.object({
                first_name: z.string().min(2, "First name is required"),
                last_name: z.string().min(2, "Last name is required"),
                phone: z.string().min(1, "Phone is required"),
                gender: z.string().default("male"),
                occupation: z.string().optional(),
                relation: z.string().default("father"),
                is_primary: z.boolean().default(true),
            })
        )
        .min(1, "At least one guardian information is required")
        .default([]),
});

type EnrollmentFormData = z.infer<typeof enrollmentSchema>;

interface AdmissionWizardProps {
    studentId?: string;
}

export default function AdmissionWizard({ studentId }: AdmissionWizardProps) {
    const { selectedYear, currentYear } = useAcademicYear();
    const activeYear = selectedYear || currentYear;

    const { mutate: enrollStudent, isPending: isEnrolling } = useEnrollStudent();
    const { mutate: updateStudent, isPending: isUpdating } = useUpdateStudent();
    const { data: studentData, isLoading: isLoadingStudent } = useStudent(
        studentId as string,
        !!studentId
    );

    const router = useRouter();
    const isEditMode = !!studentId;
    const isPending = isEnrolling || isUpdating;

    const initialYear = activeYear?.name || "2026-27";
    const todayDate = new Date().toISOString().split("T")[0];

    const form = useForm<EnrollmentFormData>({
        resolver: zodResolver(enrollmentSchema) as any,
        defaultValues: {
            gender: "male",
            academic_year: initialYear,
            admission_date: todayDate,
            caste_category: "GEN",
            is_rte: false,
            parents: [
                {
                    first_name: "",
                    last_name: "",
                    phone: "",
                    gender: "male",
                    relation: "father",
                    occupation: "",
                    is_primary: true,
                },
            ],
        },
        mode: "onBlur",
    });

    // Populate data in edit mode
    useEffect(() => {
        if (studentData) {
            form.reset({
                ...studentData,
                academic_year: studentData.academic_year || initialYear,
                parents: studentData.parents && studentData.parents.length > 0
                    ? studentData.parents
                    : [
                          {
                              first_name: "",
                              last_name: "",
                              phone: "",
                              gender: "male",
                              relation: "father",
                              occupation: "",
                              is_primary: true,
                          },
                      ],
            });
        }
    }, [studentData, form, initialYear]);

    // Live preview watches
    const watchedFirstName = form.watch("first_name") || "";
    const watchedLastName = form.watch("last_name") || "";
    const watchedAcademicYear = form.watch("academic_year") || initialYear;
    const studentFullName = `${watchedFirstName} ${watchedLastName}`.trim();

    const onSubmit = (data: EnrollmentFormData) => {
        if (isEditMode) {
            updateStudent(
                { id: studentId, data: data as unknown as StudentEnrollmentData },
                {
                    onSuccess: () => {
                        router.push("/dashboard/students");
                    },
                    onError: (error: any) => handleServerErrors(error),
                }
            );
        } else {
            enrollStudent(data as unknown as StudentEnrollmentData, {
                onSuccess: () => {
                    router.push("/dashboard/students");
                },
                onError: (error: any) => handleServerErrors(error),
            });
        }
    };

    const handleServerErrors = (error: any) => {
        const serverErrors = error.response?.data;
        if (serverErrors && typeof serverErrors === "object") {
            Object.keys(serverErrors).forEach((key) => {
                form.setError(key as any, {
                    type: "manual",
                    message: Array.isArray(serverErrors[key])
                        ? serverErrors[key][0]
                        : "Invalid value",
                });
            });
        }
    };

    if (isEditMode && isLoadingStudent) {
        return (
            <div className="flex h-[40vh] items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-sky-600" />
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* 1. Executive Top Header Banner */}
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 border border-emerald-200/60 dark:border-emerald-900 shrink-0">
                        <Sparkles className="w-5 h-5" />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                {isEditMode ? "Edit Student Profile" : "Direct Walk-in Student Admission"}
                            </h3>
                            <Badge
                                variant="outline"
                                className="text-[10px] py-0 font-semibold border-emerald-300 text-emerald-700 bg-emerald-50 dark:bg-emerald-950/40"
                            >
                                {isEditMode ? "Profile Maintenance" : "Instant Enrollment"}
                            </Badge>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            {isEditMode
                                ? "Update student demographics, grade level placement, and linked guardian contact records."
                                : "Admit and enroll prospective students directly into active academic cohorts on the spot."}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs py-1">
                        Session: {watchedAcademicYear}
                    </Badge>
                </div>
            </div>

            {/* 2. Main High-Density Form */}
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                {/* Section 1: Student Information */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                    <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <User className="w-4 h-4" />
                        </div>
                        <div>
                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                1. Student Identity & Contact
                            </h4>
                            <p className="text-[11px] text-slate-400">Legal name, demographics, and residential address</p>
                        </div>
                    </div>
                    <PersonalDetailsStep form={form} />
                </div>

                {/* Section 2: Academic Placement & Cohort */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                    <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
                        <div className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                            <GraduationCap className="w-4 h-4" />
                        </div>
                        <div>
                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                2. Academic Placement & History
                            </h4>
                            <p className="text-[11px] text-slate-400">Grade class level, section allocation, admission date, and prior schooling</p>
                        </div>
                    </div>
                    <AcademicInfoStep form={form} />
                </div>

                {/* Section 3: Parent & Guardian Details */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                    <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <Users className="w-4 h-4" />
                        </div>
                        <div>
                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                3. Parent & Guardian Contact Channels
                            </h4>
                            <p className="text-[11px] text-slate-400">Primary family contact for portal access, SMS alerts, and fee communication</p>
                        </div>
                    </div>
                    <GuardianDetailsStep form={form} />
                </div>

                {/* Section 4: Indian Statutory Compliance (Collapsible Accordion) */}
                <details className="group bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-4 transition-all">
                    <summary className="flex items-center justify-between cursor-pointer list-none">
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
                                <ShieldCheck className="w-4 h-4" />
                            </div>
                            <div>
                                <span className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                                    4. Statutory & Government Compliance (UDISE+ / APAAR / RTE)
                                </span>
                                <span className="text-[11px] text-slate-400 block">
                                    Optional Indian educational registry IDs and category disclosures
                                </span>
                            </div>
                        </div>
                        <ChevronDown className="w-4 h-4 text-slate-400 transition-transform group-open:rotate-180" />
                    </summary>

                    <div className="pt-4 mt-3 border-t border-slate-100 dark:border-slate-800 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
                        <div className="space-y-1.5">
                            <Label htmlFor="apaar_id" className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                APAAR ID <span className="text-slate-400">(12 Digits)</span>
                            </Label>
                            <Input
                                id="apaar_id"
                                placeholder="e.g. 123456789012"
                                maxLength={12}
                                {...form.register("apaar_id")}
                                className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="pen" className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                PEN <span className="text-slate-400">(Permanent Edu No)</span>
                            </Label>
                            <Input
                                id="pen"
                                placeholder="e.g. 20261234567"
                                maxLength={11}
                                {...form.register("pen")}
                                className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label htmlFor="aadhaar_last_4" className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                Aadhaar (Last 4 Digits)
                            </Label>
                            <Input
                                id="aadhaar_last_4"
                                placeholder="XXXX"
                                maxLength={4}
                                {...form.register("aadhaar_last_4")}
                                className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <Label className="text-xs font-medium text-slate-600 dark:text-slate-400">
                                Social Category
                            </Label>
                            <Select
                                value={form.watch("caste_category") || "GEN"}
                                onValueChange={(val) => form.setValue("caste_category", val)}
                            >
                                <SelectTrigger className="h-9.5 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
                                    <SelectValue placeholder="Category" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="GEN" className="text-xs">General (GEN)</SelectItem>
                                    <SelectItem value="OBC" className="text-xs">Other Backward Class (OBC)</SelectItem>
                                    <SelectItem value="SC" className="text-xs">Scheduled Caste (SC)</SelectItem>
                                    <SelectItem value="ST" className="text-xs">Scheduled Tribe (ST)</SelectItem>
                                    <SelectItem value="EWS" className="text-xs">Economically Weaker Section (EWS)</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>

                        <div className="sm:col-span-2 flex items-center pt-2 pl-1">
                            <label className="flex items-center gap-2.5 cursor-pointer">
                                <input
                                    type="checkbox"
                                    {...form.register("is_rte")}
                                    className="h-4 w-4 rounded border-slate-300 text-sky-600 focus:ring-sky-500 rounded-sm"
                                />
                                <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                                    Enrolled under Right to Education (RTE) statutory quota
                                </span>
                            </label>
                        </div>
                    </div>
                </details>

                {/* 3. Bottom Sticky Action Footer */}
                <div className="sticky bottom-4 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200/90 dark:border-slate-800 rounded-xl p-3 shadow-lg flex flex-col sm:flex-row items-center justify-between gap-3">
                    {/* Live Applicant Summary Preview */}
                    <div className="flex items-center gap-2.5 self-start sm:self-auto">
                        <div className="h-8 w-8 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300/80 flex items-center justify-center font-bold text-xs shrink-0">
                            {studentFullName ? studentFullName.slice(0, 2).toUpperCase() : "NA"}
                        </div>
                        <div>
                            <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                {studentFullName || "New Walk-in Student"}
                            </div>
                            <div className="text-[10px] text-slate-400">
                                AY: {watchedAcademicYear} • Direct Onboarding
                            </div>
                        </div>
                    </div>

                    {/* Action Buttons */}
                    <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={isPending}
                            onClick={() => form.reset()}
                            className="h-9 px-3 text-xs text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 gap-1.5 cursor-pointer"
                        >
                            <RotateCcw className="w-3.5 h-3.5" />
                            <span>Reset Form</span>
                        </Button>

                        <Button
                            type="submit"
                            disabled={isPending}
                            className={cn(
                                "h-9.5 px-5 text-xs font-semibold rounded-lg text-white shadow-sm transition active:scale-95 cursor-pointer flex items-center gap-2",
                                isEditMode
                                    ? "bg-sky-600 hover:bg-sky-500"
                                    : "bg-emerald-600 hover:bg-emerald-500"
                            )}
                        >
                            {isPending ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    <span>Processing Enrollment...</span>
                                </>
                            ) : (
                                <>
                                    <CheckCircle2 className="h-4 w-4" />
                                    <span>{isEditMode ? "Save Changes" : "Complete Admission"}</span>
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </form>
        </div>
    );
}
