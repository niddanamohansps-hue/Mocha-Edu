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
    RotateCcw,
    ArrowRight,
    ArrowLeft,
    Check,
    Layers,
    FileCheck2,
    Calendar,
    Phone,
    MapPin,
    AlertCircle,
    Building2,
    IdCard,
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

const STEPS = [
    { id: 1, title: "Student Details", subtitle: "Name, demographics & address", icon: User },
    { id: 2, title: "Academic Placement", subtitle: "Session, grade level & section", icon: GraduationCap },
    { id: 3, title: "Parent & Guardian", subtitle: "Primary contacts & emergency", icon: Users },
    { id: 4, title: "Statutory & Review", subtitle: "Government IDs & final check", icon: ShieldCheck },
];

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

    const [currentStep, setCurrentStep] = useState<number>(1);
    const [viewMode, setViewMode] = useState<"stepper" | "single">("stepper");

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
                parents:
                    studentData.parents && studentData.parents.length > 0
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
    const watchedMiddleName = form.watch("middle_name") || "";
    const watchedLastName = form.watch("last_name") || "";
    const watchedGender = form.watch("gender") || "male";
    const watchedDOB = form.watch("date_of_birth") || "";
    const watchedPhone = form.watch("phone") || "";
    const watchedAddress = form.watch("address") || "";
    const watchedAcademicYear = form.watch("academic_year") || initialYear;
    const watchedLevelId = form.watch("level_id") || "";
    const watchedAdmissionDate = form.watch("admission_date") || todayDate;
    const watchedParents = form.watch("parents") || [];
    const watchedApaar = form.watch("apaar_id") || "";
    const watchedPen = form.watch("pen") || "";
    const watchedCaste = form.watch("caste_category") || "GEN";
    const watchedIsRte = form.watch("is_rte") || false;

    const studentFullName = [watchedFirstName, watchedMiddleName, watchedLastName].filter(Boolean).join(" ");
    const primaryParent = watchedParents.find((p) => p.is_primary) || watchedParents[0];

    const handleNextStep = async () => {
        let fieldsToValidate: any[] = [];
        if (currentStep === 1) {
            fieldsToValidate = ["first_name", "last_name", "gender", "date_of_birth", "address"];
        } else if (currentStep === 2) {
            fieldsToValidate = ["level_id", "academic_year"];
        } else if (currentStep === 3) {
            fieldsToValidate = ["parents"];
        }

        const isValid = await form.trigger(fieldsToValidate);
        if (isValid) {
            setCurrentStep((prev) => Math.min(prev + 1, 4));
            window.scrollTo({ top: 0, behavior: "smooth" });
        }
    };

    const handlePrevStep = () => {
        setCurrentStep((prev) => Math.max(prev - 1, 1));
        window.scrollTo({ top: 0, behavior: "smooth" });
    };

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
        <div className="space-y-6">
            {/* 1. Header Banner with Mode Toggle */}
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
                                {isEditMode ? "Profile Maintenance" : "Instant Enrollment Desk"}
                            </Badge>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            {isEditMode
                                ? "Update student demographics, grade level placement, and linked guardian contact records."
                                : "Admit and enroll prospective students directly into active academic cohorts on the spot."}
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2.5 self-start sm:self-auto shrink-0">
                    <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs py-1">
                        Session: {watchedAcademicYear}
                    </Badge>

                    {/* Mode Toggle */}
                    <div className="flex items-center rounded-lg border border-slate-200 dark:border-slate-800 p-0.5 bg-slate-50 dark:bg-slate-950 text-xs">
                        <button
                            type="button"
                            onClick={() => setViewMode("stepper")}
                            className={cn(
                                "px-2.5 py-1 rounded-md font-medium transition cursor-pointer",
                                viewMode === "stepper"
                                    ? "bg-white dark:bg-slate-800 text-sky-600 dark:text-sky-400 shadow-2xs font-semibold"
                                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                            )}
                        >
                            Step-by-Step
                        </button>
                        <button
                            type="button"
                            onClick={() => setViewMode("single")}
                            className={cn(
                                "px-2.5 py-1 rounded-md font-medium transition cursor-pointer",
                                viewMode === "single"
                                    ? "bg-white dark:bg-slate-800 text-sky-600 dark:text-sky-400 shadow-2xs font-semibold"
                                    : "text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
                            )}
                        >
                            All Sections
                        </button>
                    </div>
                </div>
            </div>

            {/* 2. Modern Interactive Stepper Bar (When viewMode is 'stepper') */}
            {viewMode === "stepper" && (
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl p-4 shadow-2xs">
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        {STEPS.map((s) => {
                            const isCurrent = currentStep === s.id;
                            const isCompleted = currentStep > s.id;
                            const StepIcon = s.icon;

                            return (
                                <button
                                    key={s.id}
                                    type="button"
                                    onClick={() => setCurrentStep(s.id)}
                                    className={cn(
                                        "flex items-center gap-3 p-3 rounded-xl border text-left transition cursor-pointer relative",
                                        isCurrent
                                            ? "border-sky-500 bg-sky-50/50 dark:bg-sky-950/40 ring-1 ring-sky-500/20"
                                            : isCompleted
                                            ? "border-emerald-300/80 dark:border-emerald-900/60 bg-emerald-50/20 dark:bg-emerald-950/20 hover:border-emerald-400"
                                            : "border-slate-200/80 dark:border-slate-800 bg-white dark:bg-slate-900 hover:border-slate-300 dark:hover:border-slate-700 opacity-80"
                                    )}
                                >
                                    <div
                                        className={cn(
                                            "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 transition-colors",
                                            isCompleted
                                                ? "bg-emerald-500 text-white"
                                                : isCurrent
                                                ? "bg-sky-600 text-white"
                                                : "bg-slate-100 dark:bg-slate-800 text-slate-500"
                                        )}
                                    >
                                        {isCompleted ? <Check className="w-4 h-4 stroke-[2.5]" /> : <StepIcon className="w-4 h-4" />}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                                                Step {s.id}
                                            </span>
                                            {isCompleted && (
                                                <span className="text-[10px] font-semibold text-emerald-600 dark:text-emerald-400">
                                                    Done
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-xs font-bold text-slate-900 dark:text-white truncate">
                                            {s.title}
                                        </div>
                                    </div>
                                </button>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* 3. Main Form Area with Live Preview Sidebar */}
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
                    {/* Form Left Column (8 cols in stepper, full or 8 in single) */}
                    <div className="lg:col-span-8 space-y-5">
                        {/* STEP 1: Student Demographics */}
                        {(viewMode === "single" || currentStep === 1) && (
                            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                                    <div className="flex items-center gap-2.5">
                                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                                            <User className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                                1. Student Identity & Contact Information
                                            </h4>
                                            <p className="text-[11px] text-slate-400">Legal full name, date of birth, gender, and home address</p>
                                        </div>
                                    </div>
                                    <Badge variant="outline" className="text-[10px] py-0 text-slate-500">
                                        Required Fields *
                                    </Badge>
                                </div>
                                <PersonalDetailsStep form={form} />
                            </div>
                        )}

                        {/* STEP 2: Academic Placement */}
                        {(viewMode === "single" || currentStep === 2) && (
                            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                                    <div className="flex items-center gap-2.5">
                                        <div className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                                            <GraduationCap className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                                2. Academic Placement & Cohort Allocation
                                            </h4>
                                            <p className="text-[11px] text-slate-400">Grade class level, section assignment, admission date, and prior school</p>
                                        </div>
                                    </div>
                                </div>
                                <AcademicInfoStep form={form} />
                            </div>
                        )}

                        {/* STEP 3: Parent & Guardian Details */}
                        {(viewMode === "single" || currentStep === 3) && (
                            <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                                <div className="flex items-center justify-between pb-3 border-b border-slate-100 dark:border-slate-800">
                                    <div className="flex items-center gap-2.5">
                                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                                            <Users className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                                3. Parent & Guardian Contact Channels
                                            </h4>
                                            <p className="text-[11px] text-slate-400">Primary family contact for portal access, SMS alerts, and fee billing</p>
                                        </div>
                                    </div>
                                    <Badge variant="outline" className="text-[10px] py-0 text-emerald-700 bg-emerald-50 border-emerald-300">
                                        Min 1 Guardian
                                    </Badge>
                                </div>
                                <GuardianDetailsStep form={form} />
                            </div>
                        )}

                        {/* STEP 4: Indian Statutory Compliance & Final Review */}
                        {(viewMode === "single" || currentStep === 4) && (
                            <div className="space-y-4">
                                {/* Statutory Card */}
                                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                                    <div className="flex items-center gap-2.5 pb-3 border-b border-slate-100 dark:border-slate-800">
                                        <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                                            <ShieldCheck className="w-4 h-4" />
                                        </div>
                                        <div>
                                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                                4. Statutory & Government Registries (UDISE+ / APAAR / RTE)
                                            </h4>
                                            <p className="text-[11px] text-slate-400">Optional government educational IDs and social category disclosures</p>
                                        </div>
                                    </div>

                                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
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

                                        <div className="sm:col-span-4 flex items-center pt-2 pl-1">
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
                                </div>

                                {/* Comprehensive Pre-Submission Review Desk */}
                                {viewMode === "stepper" && currentStep === 4 && (
                                    <div className="bg-slate-50 dark:bg-slate-950/60 border border-slate-200/90 dark:border-slate-800 rounded-xl p-5 space-y-4">
                                        <div className="flex items-center justify-between pb-3 border-b border-slate-200/70 dark:border-slate-800">
                                            <div className="flex items-center gap-2">
                                                <FileCheck2 className="w-4 h-4 text-emerald-600" />
                                                <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                                    Pre-Enrollment Verification Summary
                                                </h4>
                                            </div>
                                            <Badge className="bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 text-[10px]">
                                                Ready for Enrollment
                                            </Badge>
                                        </div>

                                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                                            <div className="p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200/70 dark:border-slate-800 space-y-1.5">
                                                <span className="text-[10px] font-bold uppercase text-slate-400">Student Identity</span>
                                                <div className="font-semibold text-slate-900 dark:text-white">{studentFullName || "—"}</div>
                                                <div className="text-slate-500 flex items-center gap-3">
                                                    <span className="capitalize">{watchedGender}</span>
                                                    <span>•</span>
                                                    <span>DOB: {watchedDOB || "—"}</span>
                                                </div>
                                                <div className="text-slate-500 truncate">{watchedAddress || "—"}</div>
                                            </div>

                                            <div className="p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200/70 dark:border-slate-800 space-y-1.5">
                                                <span className="text-[10px] font-bold uppercase text-slate-400">Placement & Session</span>
                                                <div className="font-semibold text-slate-900 dark:text-white">
                                                    Cohort Session: {watchedAcademicYear}
                                                </div>
                                                <div className="text-slate-500">
                                                    Admission Date: {watchedAdmissionDate}
                                                </div>
                                                <div className="text-slate-500">
                                                    Category: {watchedCaste} {watchedIsRte ? "• RTE Quota" : ""}
                                                </div>
                                            </div>

                                            <div className="sm:col-span-2 p-3 bg-white dark:bg-slate-900 rounded-lg border border-slate-200/70 dark:border-slate-800 space-y-1.5">
                                                <span className="text-[10px] font-bold uppercase text-slate-400">Primary Family Contact</span>
                                                {primaryParent ? (
                                                    <div className="flex flex-wrap items-center justify-between gap-2">
                                                        <div>
                                                            <span className="font-semibold text-slate-900 dark:text-white">
                                                                {primaryParent.first_name} {primaryParent.last_name}
                                                            </span>
                                                            <span className="text-slate-400 capitalize ml-2">
                                                                ({primaryParent.relation})
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-3 text-slate-600 dark:text-slate-300">
                                                            <span className="flex items-center gap-1 font-mono">
                                                                <Phone className="w-3 h-3 text-slate-400" />
                                                                {primaryParent.phone || "No phone entered"}
                                                            </span>
                                                            {primaryParent.occupation && (
                                                                <span>Occ: {primaryParent.occupation}</span>
                                                            )}
                                                        </div>
                                                    </div>
                                                ) : (
                                                    <div className="text-rose-500 text-xs">No primary guardian specified</div>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* Right Column: Live Admissions Badge Preview (4 cols) */}
                    <div className="lg:col-span-4 sticky top-6 space-y-4">
                        <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-4 space-y-3.5">
                            <div className="flex items-center justify-between pb-2.5 border-b border-slate-100 dark:border-slate-800">
                                <div className="flex items-center gap-2">
                                    <IdCard className="w-4 h-4 text-sky-600 dark:text-sky-400" />
                                    <span className="text-xs font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider">
                                        Live Badge Preview
                                    </span>
                                </div>
                                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                            </div>

                            {/* Institutional ID Preview Card */}
                            <div className="bg-gradient-to-br from-sky-600 to-indigo-700 text-white rounded-xl p-4 shadow-sm relative overflow-hidden">
                                <div className="absolute top-0 right-0 w-28 h-28 bg-white/10 rounded-full blur-xl pointer-events-none" />

                                <div className="flex items-center justify-between pb-2 border-b border-white/20">
                                    <div className="text-[10px] font-bold tracking-widest uppercase opacity-90">
                                        EduSekai
                                    </div>
                                    <Badge className="bg-white/20 hover:bg-white/30 text-white text-[9px] py-0 border-none font-semibold">
                                        {watchedAcademicYear}
                                    </Badge>
                                </div>

                                <div className="flex items-center gap-3 mt-3">
                                    <div className="w-12 h-12 rounded-xl bg-white/20 border border-white/30 flex items-center justify-center font-bold text-lg shrink-0">
                                        {studentFullName ? studentFullName.slice(0, 2).toUpperCase() : "ST"}
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <div className="text-sm font-bold truncate">
                                            {studentFullName || "Student Full Name"}
                                        </div>
                                        <div className="text-[11px] text-white/80 capitalize">
                                            {watchedGender} • {watchedDOB || "DOB: Pending"}
                                        </div>
                                        <div className="text-[10px] text-white/70 truncate">
                                            Adm Date: {watchedAdmissionDate}
                                        </div>
                                    </div>
                                </div>

                                <div className="mt-3 pt-2 border-t border-white/20 flex items-center justify-between text-[11px]">
                                    <span className="text-white/80">Guardian:</span>
                                    <span className="font-semibold text-right truncate max-w-[160px]">
                                        {primaryParent?.first_name ? `${primaryParent.first_name} (${primaryParent.relation})` : "Not assigned"}
                                    </span>
                                </div>
                            </div>

                            {/* Step Progress Checklist */}
                            <div className="p-3 bg-slate-50 dark:bg-slate-950 rounded-lg border border-slate-100 dark:border-slate-800 space-y-2 text-xs">
                                <span className="text-[10px] font-bold uppercase text-slate-400 block">
                                    Admissions Checklist
                                </span>
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-600 dark:text-slate-300">Name & Demographics</span>
                                    {watchedFirstName && watchedLastName && watchedDOB ? (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                    ) : (
                                        <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                                    )}
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-600 dark:text-slate-300">Academic Placement</span>
                                    {watchedLevelId ? (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                    ) : (
                                        <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                                    )}
                                </div>
                                <div className="flex items-center justify-between">
                                    <span className="text-slate-600 dark:text-slate-300">Primary Guardian</span>
                                    {primaryParent?.first_name && primaryParent?.phone ? (
                                        <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                                    ) : (
                                        <AlertCircle className="w-3.5 h-3.5 text-amber-500" />
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* 4. Bottom Sticky Action Footer */}
                <div className="sticky bottom-4 z-20 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200/90 dark:border-slate-800 rounded-xl p-3.5 shadow-xl flex flex-col sm:flex-row items-center justify-between gap-3">
                    {/* Live Applicant Summary Preview */}
                    <div className="flex items-center gap-3 self-start sm:self-auto">
                        <div className="h-9 w-9 rounded-xl bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-300/80 flex items-center justify-center font-bold text-xs shrink-0">
                            {studentFullName ? studentFullName.slice(0, 2).toUpperCase() : "NA"}
                        </div>
                        <div>
                            <div className="text-xs font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                                <span>{studentFullName || "New Walk-in Student"}</span>
                                <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 text-[10px] py-0">
                                    AY: {watchedAcademicYear}
                                </Badge>
                            </div>
                            <div className="text-[11px] text-slate-400 mt-0.5">
                                {viewMode === "stepper"
                                    ? `Step ${currentStep} of 4: ${STEPS[currentStep - 1]?.title}`
                                    : "All Sections View • Ready to enroll"}
                            </div>
                        </div>
                    </div>

                    {/* Step Navigation & Action Buttons */}
                    <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
                        {viewMode === "stepper" && currentStep > 1 && (
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={isPending}
                                onClick={handlePrevStep}
                                className="gap-1.5"
                            >
                                <ArrowLeft className="w-3.5 h-3.5" />
                                <span>Previous</span>
                            </Button>
                        )}

                        <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={isPending}
                            onClick={() => form.reset()}
                            className="gap-1.5"
                        >
                            <RotateCcw className="w-3.5 h-3.5" />
                            <span>Reset</span>
                        </Button>

                        {viewMode === "stepper" && currentStep < 4 ? (
                            <Button
                                type="button"
                                size="sm"
                                onClick={handleNextStep}
                                className="gap-2"
                            >
                                <span>Next: {STEPS[currentStep]?.title}</span>
                                <ArrowRight className="w-3.5 h-3.5" />
                            </Button>
                        ) : (
                            <Button
                                type="submit"
                                disabled={isPending}
                                className={cn(
                                    "gap-2",
                                    !isEditMode && "bg-emerald-600 hover:bg-emerald-500 text-white"
                                )}
                            >
                                {isPending ? (
                                    <>
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                        <span>Enrolling Student...</span>
                                    </>
                                ) : (
                                    <>
                                        <CheckCircle2 className="h-4 w-4" />
                                        <span>{isEditMode ? "Save Changes" : "Complete Admission"}</span>
                                    </>
                                )}
                            </Button>
                        )}
                    </div>
                </div>
            </form>
        </div>
    );
}
