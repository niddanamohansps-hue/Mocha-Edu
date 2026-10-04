"use client";

import { useState } from "react";
import {
    useAssignments,
    useCreateAssignment,
    useMySubmissions,
    useSubmitAssignment
} from "@/hooks/useCourseContent";
import { useSections } from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Plus, FileText } from "lucide-react";
import { CreateAssignmentDialog } from "@/components/dashboard/course-content/CreateAssignmentDialog";
import { SubmitAssignmentDialog } from "@/components/dashboard/course-content/SubmitAssignmentDialog";
import { AssignmentCard } from "@/components/dashboard/course-content/AssignmentCard";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";

export default function AssignmentsPage() {
    const { can, isOwner, activeRole } = usePermissions();
    const canCreate = isOwner || can("create_assignment");
    const isStudent = activeRole === 'student';

    const { data: assignments, isLoading: loadingAssignments, isError: assignmentsError, refetch: refetchAssignments } = useAssignments();
    const { data: mySubmissions, isLoading: loadingSubmissions } = useMySubmissions();
    const { mutate: createAssignment, isPending: isCreating } = useCreateAssignment();
    const { mutate: submitAssignment, isPending: isSubmitting } = useSubmitAssignment();

    const { data: sections } = useSections();

    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
    const [isSubmitDialogOpen, setIsSubmitDialogOpen] = useState(false);
    const [selectedAssignment, setSelectedAssignment] = useState<string | null>(null);

    const handleCreateAssignment = (data: any) => {
        createAssignment(data, {
            onSuccess: () => {
                setIsCreateDialogOpen(false);
            }
        });
    };

    const handleSubmit = (file: File) => {
        if (!selectedAssignment) return;

        submitAssignment({
            submissionId: selectedAssignment,
            data: { submission_file: file }
        }, {
            onSuccess: () => {
                setIsSubmitDialogOpen(false);
                setSelectedAssignment(null);
            }
        });
    };

    const handleSubmitClick = (submissionId: string) => {
        setSelectedAssignment(submissionId);
        setIsSubmitDialogOpen(true);
    };

    if (loadingAssignments || (isStudent && loadingSubmissions)) {
        return <LoadingState className="py-20" />;
    }

    if (assignmentsError) {
        return <ErrorState onRetry={refetchAssignments} />;
    }

    // Map submissions to assignments for students
    const assignmentsWithSubmissions = assignments?.map(assignment => {
        const submission = mySubmissions?.find(s => s.assignment === assignment.id);
        return { ...assignment, submission };
    }) || [];

    console.log("Assignments with submissions:", assignmentsWithSubmissions);
    console.log("Can submit:", isStudent);
    console.log("My submissions:", mySubmissions);

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Assignments</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {canCreate ? "Create and manage assignments" : "View and submit your assignments"}
                    </p>
                </div>
                {canCreate && (
                    <Button onClick={() => setIsCreateDialogOpen(true)} className="gap-2">
                        <Plus className="h-4 w-4" />
                        New Assignment
                    </Button>
                )}
            </div>

            {/* Create Assignment Dialog */}
            {canCreate && (
                <CreateAssignmentDialog
                    open={isCreateDialogOpen}
                    onOpenChange={setIsCreateDialogOpen}
                    onSubmit={handleCreateAssignment}
                    sections={sections}
                    isCreating={isCreating}
                />
            )}

            {/* Submit Assignment Dialog */}
            <SubmitAssignmentDialog
                open={isSubmitDialogOpen}
                onOpenChange={setIsSubmitDialogOpen}
                onSubmit={handleSubmit}
                isSubmitting={isSubmitting}
            />

            {/* Assignments Grid */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {assignmentsWithSubmissions && assignmentsWithSubmissions.length > 0 ? (
                    assignmentsWithSubmissions.map((assignment) => (
                        <AssignmentCard
                            key={assignment.id}
                            assignment={assignment}
                            isStudent={isStudent}
                            canCreate={canCreate}
                            onSubmitClick={handleSubmitClick}
                        />
                    ))
                ) : (
                    <EmptyState
                        icon={<FileText className="h-16 w-16 text-slate-200 dark:text-slate-700 mb-4" />}
                        title="No assignments found"
                        titleAs="h3"
                        description={canCreate ? "Create your first assignment to get started" : "Check back later for new assignments"}
                        className="col-span-full py-20 bg-slate-50/50 dark:bg-slate-900/50 rounded-2xl border-2 border-dashed border-slate-200 dark:border-slate-800"
                    />
                )}
            </div>
        </div>
    );
}
