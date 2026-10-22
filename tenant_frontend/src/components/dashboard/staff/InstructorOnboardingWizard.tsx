"use client";

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
    Check,
    Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useRouter } from 'next/navigation';
import { useOnboardInstructor } from '@/hooks/useStaff';
import PersonalDetailsStep from './onboarding/PersonalDetailsStep';
import ProfessionalInfoStep from './onboarding/ProfessionalInfoStep';

// Schema matches backend InstructorOnboardingSerializer
const onboardingSchema = z.object({
    // Personal Info
    first_name: z.string().min(2, "First name is required"),
    middle_name: z.string().optional(),
    last_name: z.string().min(2, "Last name is required"),
    email: z.string().email("Invalid email").optional().or(z.literal("")).transform(val => val === "" ? undefined : val),
    gender: z.enum(['male', 'female', 'other']),
    date_of_birth: z.string().optional().or(z.literal("")).transform(val => val === "" ? null : val),
    phone: z.string().optional(),
    address: z.string().optional(),

    // Professional Info (Instructor/Staff)
    specialization: z.string().default("General"),
    qualification: z.string().optional(),
    joining_date: z.string().optional().or(z.literal("")).transform(val => val === "" ? null : val),
    experience_years: z.any().transform(val => Number(val) || 0), // Handle string/number input
    bio: z.string().optional(),
});

type OnboardingFormData = z.infer<typeof onboardingSchema>;

export default function InstructorOnboardingWizard() {
    const { mutate: onboardInstructor, isPending } = useOnboardInstructor();
    const router = useRouter();

    const form = useForm<OnboardingFormData>({
        resolver: zodResolver(onboardingSchema) as any,
        defaultValues: {
            gender: 'male',
            specialization: 'General',
            experience_years: 0,
        },
        mode: "onBlur"
    });

    const onSubmit = (data: OnboardingFormData) => {
        // Cast types to match expected API format if needed
        onboardInstructor(data as any, {
            onSuccess: () => {
                router.push('/dashboard/staff');
            }
        });
    };

    return (
        <div className="max-w-5xl mx-auto py-8">
            <div className="mb-10 text-center">
                <h1 className="text-3xl font-black text-slate-800 dark:text-white mb-2">
                    Add a teacher
                </h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Complete the form below to hire a new instructor
                </p>
            </div>

            <form onSubmit={form.handleSubmit(onSubmit)}>
                <Card className="border-none shadow-[0_32px_64px_-16px_rgba(0,0,0,0.05)] bg-white/70 dark:bg-slate-900/70 backdrop-blur-3xl rounded-[2.5rem] overflow-hidden">
                    <CardContent className="p-8 md:p-12 space-y-16">

                        {/* Section 1: Personal Details */}
                        <div className="space-y-8">
                            <div className="flex items-center gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
                                <div>
                                    <h2 className="text-xl font-bold text-slate-800 dark:text-white">Personal Details</h2>
                                    <p className="text-sm text-slate-500 font-medium">Basic identity and contact information</p>
                                </div>
                            </div>
                            <PersonalDetailsStep form={form} />
                        </div>

                        {/* Section 2: Professional Info */}
                        <div className="space-y-8">
                            <div className="flex items-center gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
                                <div>
                                    <h2 className="text-xl font-bold text-slate-800 dark:text-white">Professional Profile</h2>
                                    <p className="text-sm text-slate-500 font-medium">Qualification, specialization, and experience</p>
                                </div>
                            </div>
                            <ProfessionalInfoStep form={form} />
                        </div>

                    </CardContent>

                    {/* Footer Controls */}
                    <div className="px-8 md:px-12 py-8 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100/50 dark:border-slate-800/50 flex justify-end">
                        <Button
                            type="submit"
                            disabled={isPending}
                            className="text-white rounded-2xl h-14 px-12 font-black shadow-2xl transition-all hover:scale-[1.02] active:scale-[0.98] w-full md:w-auto bg-emerald-600 hover:bg-emerald-700 shadow-emerald-500/30"
                        >
                            {isPending ? (
                                <div className="flex items-center">
                                    <Loader2 className="h-5 w-5 animate-spin mr-3" />
                                    Processing...
                                </div>
                            ) : (
                                <div className="flex items-center">
                                    <Check className="h-5 w-5 mr-3" />
                                    Complete Onboarding
                                </div>
                            )}
                        </Button>
                    </div>
                </Card>
            </form>
        </div>
    );
}
