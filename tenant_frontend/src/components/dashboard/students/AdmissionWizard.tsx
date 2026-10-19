"use client";

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import {
    User,
    GraduationCap,
    Users,
    Check,
    Loader2
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { useEnrollStudent, useUpdateStudent, useStudent, StudentEnrollmentData } from '@/hooks/useStudents';
import { useRouter } from 'next/navigation';

// Sub-components
import PersonalDetailsStep from './admission/PersonalDetailsStep';
import AcademicInfoStep from './admission/AcademicInfoStep';
import GuardianDetailsStep from './admission/GuardianDetailsStep';

const enrollmentSchema = z.object({
    // Personal Info
    first_name: z.string().min(2, "First name is required"),
    middle_name: z.string().optional(),
    last_name: z.string().min(2, "Last name is required"),
    email: z.string().email("Invalid email").optional().or(z.literal("")).transform(val => val === "" ? undefined : val),
    gender: z.enum(['male', 'female', 'other']),
    date_of_birth: z.string().min(1, "Date of birth is required"),
    phone: z.string().optional(),
    address: z.string().min(1, "Current address is required"),

    // Academic Info
    level_id: z.string().min(1, "Grade level is required"),
    section_id: z.string().optional(),
    academic_year: z.string().min(1, "Academic year is required"),
    admission_date: z.string().optional().or(z.literal("")).transform(val => val === "" ? undefined : val),
    previous_school: z.string().optional(),
    last_grade_passed: z.string().optional(),

    // Parents
    parents: z.array(z.object({
        first_name: z.string().min(2, "First name is required"),
        last_name: z.string().min(2, "Last name is required"),
        phone: z.string().min(1, "Phone is required"),
        gender: z.string(),
        occupation: z.string().optional(),
        relation: z.string(),
        is_primary: z.boolean()
    })).min(1, "At least one guardian information is required").default([])
});

type EnrollmentFormData = z.infer<typeof enrollmentSchema>;

interface AdmissionWizardProps {
    studentId?: string;
}

export default function AdmissionWizard({ studentId }: AdmissionWizardProps) {
    const { mutate: enrollStudent, isPending: isEnrolling } = useEnrollStudent();
    const { mutate: updateStudent, isPending: isUpdating } = useUpdateStudent();
    const { data: studentData, isLoading: isLoadingStudent } = useStudent(studentId as string, !!studentId);

    const router = useRouter();
    const isEditMode = !!studentId;
    const isPending = isEnrolling || isUpdating;

    const form = useForm<EnrollmentFormData>({
        resolver: zodResolver(enrollmentSchema) as any,
        defaultValues: {
            gender: 'male',
            academic_year: "",
            parents: []
        },
        mode: "onBlur"
    });

    React.useEffect(() => {
        if (studentData) {
            form.reset({
                ...studentData,
                // Ensure parents array is not null
                parents: studentData.parents || []
            });
        }
    }, [studentData, form]);

    const onSubmit = (data: EnrollmentFormData) => {
        if (isEditMode) {
            updateStudent({ id: studentId, data: data as unknown as StudentEnrollmentData }, {
                onSuccess: () => {
                    router.push('/dashboard/students');
                },
                onError: (error: any) => handleServerErrors(error)
            });
        } else {
            enrollStudent(data as unknown as StudentEnrollmentData, {
                onSuccess: () => {
                    router.push('/dashboard/students');
                },
                onError: (error: any) => handleServerErrors(error)
            });
        }
    };

    const handleServerErrors = (error: any) => {
        const serverErrors = error.response?.data;
        if (serverErrors && typeof serverErrors === 'object') {
            Object.keys(serverErrors).forEach((key) => {
                form.setError(key as any, {
                    type: 'manual',
                    message: Array.isArray(serverErrors[key])
                        ? serverErrors[key][0]
                        : 'Invalid value'
                });
            });
        }
    };

    if (isEditMode && isLoadingStudent) {
        return (
            <div className="flex h-[60vh] items-center justify-center">
                <Loader2 className="h-12 w-12 animate-spin text-sky-600" />
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto py-8">
            <div className="mb-10 text-center">
                <h1 className="text-3xl font-black text-slate-800 dark:text-white mb-2">
                    {isEditMode ? "Edit Student" : "Student Admission"}
                </h1>
                <p className="text-slate-500 dark:text-slate-400">
                    {isEditMode ? "Update the student information below" : "Complete the form below to enroll a new student"}
                </p>
            </div>

            <form onSubmit={form.handleSubmit(onSubmit)}>
                <Card className="border-none shadow-[0_32px_64px_-16px_rgba(0,0,0,0.05)] bg-white/70 dark:bg-slate-900/70 backdrop-blur-3xl rounded-[2.5rem] overflow-hidden">
                    <CardContent className="p-8 md:p-12 space-y-16">

                        {/* Section 1: Student Details */}
                        <div className="space-y-8">
                            <div className="flex items-center gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
                                <div>
                                    <h2 className="text-xl font-bold text-slate-800 dark:text-white">Student Details</h2>
                                    <p className="text-sm text-slate-500 font-medium">Personal information and contact details</p>
                                </div>
                            </div>
                            <PersonalDetailsStep form={form} />
                        </div>

                        {/* Section 2: Academic Info */}
                        <div className="space-y-8">
                            <div className="flex items-center gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
                                <div>
                                    <h2 className="text-xl font-bold text-slate-800 dark:text-white">Academic Information</h2>
                                    <p className="text-sm text-slate-500 font-medium">Class, section, and previous school history</p>
                                </div>
                            </div>
                            <AcademicInfoStep form={form} />
                        </div>

                        {/* Section 3: Guardians */}
                        <div className="space-y-8">
                            <div className="flex items-center gap-4 pb-6 border-b border-slate-100 dark:border-slate-800">
                                <div>
                                    <h2 className="text-xl font-bold text-slate-800 dark:text-white">Guardian Details</h2>
                                    <p className="text-sm text-slate-500 font-medium">Parent or guardian contact information</p>
                                </div>
                            </div>
                            <GuardianDetailsStep form={form} />
                        </div>

                    </CardContent>

                    {/* Footer Controls */}
                    <div className="px-8 md:px-12 py-8 bg-slate-50/50 dark:bg-slate-800/30 border-t border-slate-100/50 dark:border-slate-800/50 flex justify-end">
                        <Button
                            type="submit"
                            disabled={isPending}
                            className={cn(
                                "text-white rounded-2xl h-14 px-12 font-black shadow-2xl transition-all hover:scale-[1.02] active:scale-[0.98] w-full md:w-auto",
                                isEditMode
                                    ? "bg-sky-600 hover:bg-sky-700 shadow-sky-500/30"
                                    : "bg-emerald-600 hover:bg-emerald-700 shadow-emerald-500/30"
                            )}
                        >
                            {isPending ? (
                                <div className="flex items-center">
                                    <Loader2 className="h-5 w-5 animate-spin mr-3" />
                                    Processing...
                                </div>
                            ) : (
                                <div className="flex items-center">
                                    <Check className="h-5 w-5 mr-3" />
                                    {isEditMode ? "Update Student" : "Complete Admission"}
                                </div>
                            )}
                        </Button>
                    </div>
                </Card>
            </form>
        </div>
    );
}
