"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useStudentTranscript } from "@/hooks/useExaminations";
import { usePermissions } from "@/providers/PermissionProvider";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import Unauthorized from "@/components/Unauthorized";
import { PrintableTranscript } from "@/components/dashboard/examinations/PrintableTranscript";

export default function StudentTranscriptDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const router = useRouter();
    const { can, isOwner, activeRole } = usePermissions();
    const isStudent = activeRole === "student";
    const canView = isOwner || can("view_results") || isStudent;

    const {
        data: transcript,
        isLoading,
        isError,
        refetch,
    } = useStudentTranscript(id);

    if (!canView) {
        return <Unauthorized />;
    }

    if (isLoading) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} />;
    }

    if (!transcript) {
        return <EmptyState title="Transcript not found for this student." className="py-16" />;
    }

    return (
        <div className="space-y-6">
            <PrintableTranscript
                transcript={transcript}
                onBackToReportCard={() => router.push(`/dashboard/examinations/report-card/${id}`)}
            />
        </div>
    );
}

