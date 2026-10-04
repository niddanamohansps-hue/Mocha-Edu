"use client";

import { useState } from "react";
import { useSubmissions, useGradeSubmission, useAssignments } from "@/hooks/useCourseContent";
import { GradingDialog } from "@/components/dashboard/course-content/GradingDialog";
import { SubmissionsTable } from "@/components/dashboard/course-content/SubmissionsTable";
import { AssignmentFilter } from "@/components/dashboard/course-content/AssignmentFilter";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function GradingPage() {
    const [selectedAssignment, setSelectedAssignment] = useState<string>("");
    const [isGradingDialogOpen, setIsGradingDialogOpen] = useState(false);
    const [currentSubmission, setCurrentSubmission] = useState<any>(null);

    const { data: assignments, isLoading: loadingAssignments, isError: assignmentsError, refetch: refetchAssignments } = useAssignments();
    const { data: submissions, isLoading: loadingSubmissions } = useSubmissions(
        selectedAssignment || undefined
    );
    const { mutate: gradeSubmission, isPending: isGrading } = useGradeSubmission();

    const handleGrade = (data: { score: number; feedback: string }) => {
        if (!currentSubmission) return;

        gradeSubmission({
            submissionId: currentSubmission.id,
            data
        }, {
            onSuccess: () => {
                setIsGradingDialogOpen(false);
                setCurrentSubmission(null);
            }
        });
    };

    const openGradingDialog = (submission: any) => {
        setCurrentSubmission(submission);
        setIsGradingDialogOpen(true);
    };

    if (loadingAssignments) {
        return <LoadingState className="py-20" />;
    }

    if (assignmentsError) {
        return <ErrorState onRetry={refetchAssignments} />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Grade Submissions</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Review and grade student assignment submissions
                </p>
            </div>

            {/* Assignment Filter */}
            <AssignmentFilter
                assignments={assignments || []}
                selectedAssignment={selectedAssignment}
                onAssignmentChange={setSelectedAssignment}
            />

            {/* Grading Dialog */}
            <GradingDialog
                open={isGradingDialogOpen}
                onOpenChange={setIsGradingDialogOpen}
                submission={currentSubmission}
                onSubmit={handleGrade}
                isGrading={isGrading}
            />

            {/* Submissions Table */}
            <SubmissionsTable
                submissions={submissions || []}
                isLoading={loadingSubmissions}
                onGradeClick={openGradingDialog}
                selectedAssignment={selectedAssignment}
            />
        </div>
    );
}
