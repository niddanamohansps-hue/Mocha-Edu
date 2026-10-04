"use client";

import React, { useEffect } from 'react';
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
import { useUpdateStaff, useStaffMember } from '@/hooks/useStaff';
import PersonalDetailsStep from './onboarding/PersonalDetailsStep';
import StaffProfessionalInfoStep from './onboarding/StaffProfessionalInfoStep';
import { LoadingState } from '@/components/feedback/LoadingState';
import { ErrorState } from '@/components/feedback/ErrorState';

// Schema matches backend StaffMemberSerializer / Update
// We use the same validation rules as onboarding
const editSchema = z.object({
    // Personal Info
    first_name: z.string().min(2, "First name is required"),
    middle_name: z.string().optional().nullable(),
    last_name: z.string().min(2, "Last name is required"),
    email: z.string().email("Invalid email").optional().or(z.literal("")).transform(val => val === "" ? undefined : val),
    gender: z.enum(['male', 'female', 'other']),
    date_of_birth: z.string().optional().nullable().or(z.literal("")).transform(val => val === "" ? null : val),
    phone: z.string().optional().nullable(),
    address: z.string().optional().nullable(),

    // Professional Info (Generic Staff)
    designation: z.string().min(2, "Designation is required"),
    department: z.string().optional().nullable(),
    qualification: z.string().optional().nullable(),
    joining_date: z.string().optional().nullable().or(z.literal("")).transform(val => val === "" ? null : val),
    experience_years: z.any().transform(val => Number(val) || 0),
});

type EditFormData = z.infer<typeof editSchema>;

interface StaffEditWizardProps {
    staffId: string;
}

export default function StaffEditWizard({ staffId }: StaffEditWizardProps) {
    const { data: staff, isLoading: isLoadingStaff, isError: staffError, refetch: refetchStaff } = useStaffMember(staffId);
    const { mutate: updateStaff, isPending } = useUpdateStaff();
    const router = useRouter();

    const form = useForm<EditFormData>({
        resolver: zodResolver(editSchema) as any,
        defaultValues: {
            gender: 'male',
            experience_years: 0,
        },
        mode: "onBlur"
    });

    // Populate form when data is fetched
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

    const onSubmit = (data: EditFormData) => {
        updateStaff({ id: staffId, data: data }, {
            onSuccess: () => {
                router.push('/dashboard/staff');
            }
        });
    };

    if (isLoadingStaff) {
        return <LoadingState className="h-[50vh]" iconClassName="h-10 w-10" />;
    }

    if (staffError) {
        return <ErrorState onRetry={refetchStaff} className="m-6" />;
    }

    return (
        <div className="max-w-5xl mx-auto py-8">
            <div className="mb-10 text-center">
                <h1 className="text-3xl font-black text-slate-800 dark:text-white mb-2">
                    Edit Staff Member
                </h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Update the details for {staff?.profile_details.first_name} {staff?.profile_details.last_name}
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
                                    <p className="text-sm text-slate-500 font-medium">Designation, department, and experience</p>
                                </div>
                            </div>
                            <StaffProfessionalInfoStep form={form} />
                        </div>

                    </CardContent>

                    {/* Footer Controls */}
                    <div className="px-8 md:px-12 py-8 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100/50 dark:border-slate-800/50 flex justify-end gap-3">
                        <Button
                            type="button"
                            variant="outline"
                            onClick={() => router.back()}
                            className="rounded-2xl h-14 px-8 font-bold"
                        >
                            Cancel
                        </Button>
                        <Button
                            type="submit"
                            disabled={isPending}
                            className="text-white rounded-2xl h-14 px-12 font-black shadow-2xl transition-all hover:scale-[1.02] active:scale-[0.98] w-full md:w-auto bg-sky-600 hover:bg-sky-700 shadow-sky-500/30"
                        >
                            {isPending ? (
                                <div className="flex items-center">
                                    <Loader2 className="h-5 w-5 animate-spin mr-3" />
                                    Saving...
                                </div>
                            ) : (
                                <div className="flex items-center">
                                    <Check className="h-5 w-5 mr-3" />
                                    Save Changes
                                </div>
                            )}
                        </Button>
                    </div>
                </Card>
            </form>
        </div>
    );
}
