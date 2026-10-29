"use client";

import React, { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
    User,
    Briefcase,
    CheckCircle2,
    Loader2,
    ArrowLeft,
    RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRouter } from "next/navigation";
import { useUpdateStaff, useStaffMember } from "@/hooks/useStaff";
import PersonalDetailsStep from "./onboarding/PersonalDetailsStep";
import StaffProfessionalInfoStep from "./onboarding/StaffProfessionalInfoStep";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

const editSchema = z.object({
    // Personal Info
    first_name: z.string().min(2, "First name is required"),
    middle_name: z.string().optional().nullable(),
    last_name: z.string().min(2, "Last name is required"),
    email: z
        .string()
        .email("Invalid email")
        .optional()
        .or(z.literal(""))
        .transform((val) => (val === "" ? undefined : val)),
    gender: z.enum(["male", "female", "other"]),
    date_of_birth: z
        .string()
        .optional()
        .nullable()
        .or(z.literal(""))
        .transform((val) => (val === "" ? null : val)),
    phone: z.string().optional().nullable(),
    address: z.string().optional().nullable(),

    // Professional Info (Generic Staff)
    designation: z.string().min(2, "Designation is required"),
    department: z.string().optional().nullable(),
    qualification: z.string().optional().nullable(),
    joining_date: z
        .string()
        .optional()
        .nullable()
        .or(z.literal(""))
        .transform((val) => (val === "" ? null : val)),
    experience_years: z.any().transform((val) => Number(val) || 0),
});

type EditFormData = z.infer<typeof editSchema>;

interface StaffEditWizardProps {
    staffId: string;
}

export default function StaffEditWizard({ staffId }: StaffEditWizardProps) {
    const {
        data: staff,
        isLoading: isLoadingStaff,
        isError: staffError,
        refetch: refetchStaff,
    } = useStaffMember(staffId);
    const { mutate: updateStaff, isPending } = useUpdateStaff();
    const router = useRouter();

    const form = useForm<EditFormData>({
        resolver: zodResolver(editSchema) as any,
        defaultValues: {
            gender: "male",
            experience_years: 0,
        },
        mode: "onBlur",
    });

    useEffect(() => {
        if (staff) {
            form.reset({
                first_name: staff.profile_details.first_name,
                middle_name: staff.profile_details.middle_name,
                last_name: staff.profile_details.last_name,
                email: staff.profile_details.email,
                gender: staff.profile_details.gender as any,
                date_of_birth: staff.profile_details.date_of_birth,
                phone: staff.profile_details.phone,
                address: staff.profile_details.address,

                designation: staff.designation,
                department: staff.department,
                qualification: staff.qualification,
                joining_date: staff.joining_date,
                experience_years: staff.experience_years,
            });
        }
    }, [staff, form]);

    const watchedFirstName = form.watch("first_name") || "";
    const watchedLastName = form.watch("last_name") || "";
    const watchedDesignation = form.watch("designation") || "";
    const staffFullName = `${watchedFirstName} ${watchedLastName}`.trim();

    const onSubmit = (data: EditFormData) => {
        updateStaff(
            { id: staffId, data: data },
            {
                onSuccess: () => {
                    router.push("/dashboard/staff");
                },
            }
        );
    };

    if (isLoadingStaff) {
        return <LoadingState className="h-[40vh]" iconClassName="h-8 w-8" />;
    }

    if (staffError) {
        return <ErrorState onRetry={refetchStaff} className="m-6" />;
    }

    return (
        <div className="space-y-4">
            {/* Header Banner */}
            <div className="p-4 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => router.push("/dashboard/staff")}
                        className="h-8 w-8 p-0 rounded-lg text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                        title="Back to Staff Directory"
                    >
                        <ArrowLeft className="w-4 h-4" />
                    </Button>
                    <div className="p-2.5 rounded-xl bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400 border border-sky-200/60 dark:border-sky-900 shrink-0">
                        <Briefcase className="w-5 h-5" />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                Edit Staff Member Profile
                            </h3>
                            <Badge
                                variant="outline"
                                className="text-[10px] py-0 font-semibold border-sky-300 text-sky-700 bg-sky-50 dark:bg-sky-950/40"
                            >
                                {staff?.employee_id || "Active Record"}
                            </Badge>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            Modify employee details, job designation, qualification, and contact channels.
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs py-1">
                        ID: {staff?.employee_id}
                    </Badge>
                </div>
            </div>

            {/* Form Sections */}
            <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-4">
                {/* Section 1: Personal Details */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                    <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <User className="w-4 h-4" />
                        </div>
                        <div>
                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                1. Personal &amp; Contact Details
                            </h4>
                            <p className="text-[11px] text-slate-400">Name, phone, email, and home address</p>
                        </div>
                    </div>
                    <PersonalDetailsStep form={form} />
                </div>

                {/* Section 2: Professional Profile */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                    <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Briefcase className="w-4 h-4" />
                        </div>
                        <div>
                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                2. Role &amp; Employment Profile
                            </h4>
                            <p className="text-[11px] text-slate-400">Designation, department, experience, and joining records</p>
                        </div>
                    </div>
                    <StaffProfessionalInfoStep form={form} />
                </div>

                {/* Bottom Sticky Action Footer */}
                <div className="sticky bottom-4 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200/90 dark:border-slate-800 rounded-xl p-3 shadow-lg flex flex-col sm:flex-row items-center justify-between gap-3">
                    <div className="flex items-center gap-2.5 self-start sm:self-auto">
                        <div className="h-8 w-8 rounded-full bg-sky-100 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 border border-sky-300/80 flex items-center justify-center font-bold text-xs shrink-0">
                            {staffFullName ? staffFullName.slice(0, 2).toUpperCase() : "EM"}
                        </div>
                        <div>
                            <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                {staffFullName || staff?.profile_details.first_name}
                            </div>
                            <div className="text-[10px] text-slate-400">
                                {watchedDesignation || staff?.designation} • {staff?.employee_id}
                            </div>
                        </div>
                    </div>

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
                            <span>Reset</span>
                        </Button>

                        <Button
                            type="submit"
                            disabled={isPending}
                            className="h-9.5 px-5 text-xs font-semibold rounded-lg text-white shadow-sm transition active:scale-95 cursor-pointer flex items-center gap-2 bg-sky-600 hover:bg-sky-500"
                        >
                            {isPending ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    <span>Updating...</span>
                                </>
                            ) : (
                                <>
                                    <CheckCircle2 className="h-4 w-4" />
                                    <span>Save Changes</span>
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </form>
        </div>
    );
}
