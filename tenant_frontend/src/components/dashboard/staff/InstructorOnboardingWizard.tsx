"use client";

import React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import * as z from "zod";
import {
    User,
    GraduationCap,
    CheckCircle2,
    Loader2,
    ArrowLeft,
    RotateCcw,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRouter } from "next/navigation";
import { useOnboardInstructor } from "@/hooks/useStaff";
import PersonalDetailsStep from "./onboarding/PersonalDetailsStep";
import ProfessionalInfoStep from "./onboarding/ProfessionalInfoStep";

const onboardingSchema = z.object({
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
    date_of_birth: z
        .string()
        .optional()
        .or(z.literal(""))
        .transform((val) => (val === "" ? null : val)),
    phone: z.string().optional(),
    address: z.string().optional(),

    // Professional Info (Instructor/Faculty)
    specialization: z.string().default("General"),
    qualification: z.string().optional(),
    joining_date: z
        .string()
        .optional()
        .or(z.literal(""))
        .transform((val) => (val === "" ? null : val)),
    experience_years: z.any().transform((val) => Number(val) || 0),
    bio: z.string().optional(),
});

type OnboardingFormData = z.infer<typeof onboardingSchema>;

export default function InstructorOnboardingWizard() {
    const { mutate: onboardInstructor, isPending } = useOnboardInstructor();
    const router = useRouter();

    const form = useForm<OnboardingFormData>({
        resolver: zodResolver(onboardingSchema) as any,
        defaultValues: {
            gender: "male",
            specialization: "General",
            experience_years: 0,
            joining_date: new Date().toISOString().split("T")[0],
        },
        mode: "onBlur",
    });

    const watchedFirstName = form.watch("first_name") || "";
    const watchedLastName = form.watch("last_name") || "";
    const watchedSpecialization = form.watch("specialization") || "General";
    const facultyFullName = `${watchedFirstName} ${watchedLastName}`.trim();

    const onSubmit = (data: OnboardingFormData) => {
        onboardInstructor(data as any, {
            onSuccess: () => {
                router.push("/dashboard/staff");
            },
        });
    };

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
                    <div className="p-2.5 rounded-xl bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400 border border-purple-200/60 dark:border-purple-900 shrink-0">
                        <GraduationCap className="w-5 h-5" />
                    </div>
                    <div>
                        <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                Onboard Faculty &amp; Instructor
                            </h3>
                            <Badge
                                variant="outline"
                                className="text-[10px] py-0 font-semibold border-purple-300 text-purple-700 bg-purple-50 dark:bg-purple-950/40"
                            >
                                Academic Faculty
                            </Badge>
                        </div>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                            Register teaching faculty, subject specialization, qualifications, and profile summary.
                        </p>
                    </div>
                </div>

                <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    <Badge className="bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 border border-slate-200 dark:border-slate-700 text-xs py-1">
                        Teaching Roster
                    </Badge>
                </div>
            </div>

            {/* Main Form */}
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
                            <p className="text-[11px] text-slate-400">Legal name, contact phone, and portal email</p>
                        </div>
                    </div>
                    <PersonalDetailsStep form={form} />
                </div>

                {/* Section 2: Teaching Specialization & Bio */}
                <div className="bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs p-5 space-y-4">
                    <div className="flex items-center gap-2 pb-3 border-b border-slate-100 dark:border-slate-800">
                        <div className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                            <GraduationCap className="w-4 h-4" />
                        </div>
                        <div>
                            <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                                2. Academic Specialization &amp; Credentials
                            </h4>
                            <p className="text-[11px] text-slate-400">Subject expertise, degrees, experience, and academic biography</p>
                        </div>
                    </div>
                    <ProfessionalInfoStep form={form} />
                </div>

                {/* Bottom Docked Action Footer */}
                <div className="sticky bottom-4 z-10 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border border-slate-200/90 dark:border-slate-800 rounded-xl p-3 shadow-lg flex flex-col sm:flex-row items-center justify-between gap-3">
                    {/* Live Preview Pill */}
                    <div className="flex items-center gap-2.5 self-start sm:self-auto">
                        <div className="h-8 w-8 rounded-full bg-purple-100 dark:bg-purple-950/60 text-purple-700 dark:text-purple-300 border border-purple-300/80 flex items-center justify-center font-bold text-xs shrink-0">
                            {facultyFullName ? facultyFullName.slice(0, 2).toUpperCase() : "FA"}
                        </div>
                        <div>
                            <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                                {facultyFullName || "New Faculty Member"}
                            </div>
                            <div className="text-[10px] text-slate-400">
                                {watchedSpecialization} • Faculty Instructor
                            </div>
                        </div>
                    </div>

                    {/* Actions */}
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
                            className="h-9.5 px-5 text-xs font-semibold rounded-lg text-white shadow-sm transition active:scale-95 cursor-pointer flex items-center gap-2 bg-purple-600 hover:bg-purple-500"
                        >
                            {isPending ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    <span>Onboarding...</span>
                                </>
                            ) : (
                                <>
                                    <CheckCircle2 className="h-4 w-4" />
                                    <span>Onboard Faculty Member</span>
                                </>
                            )}
                        </Button>
                    </div>
                </div>
            </form>
        </div>
    );
}
