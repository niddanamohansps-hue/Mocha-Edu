"use client";

import { use } from "react";
import { useRouter } from "next/navigation";
import { useStudentReportCard } from "@/hooks/useExaminations";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import Unauthorized from "@/components/Unauthorized";
import { PrintableReportCard } from "@/components/dashboard/examinations/PrintableReportCard";

export default function StudentReportCardDetailPage({
    params,
}: {
    params: Promise<{ id: string }>;
}) {
    const { id } = use(params);
    const router = useRouter();
    const { can, isOwner, activeRole } = usePermissions();
    const isStudent = activeRole === "student";
    const canView = isOwner || can("view_results") || isStudent;

    const { selectedYear } = useAcademicYear();

    const {
        data: reportCard,
        isLoading,
        isError,
        refetch,
    } = useStudentReportCard(id, selectedYear?.name);

    if (!canView) {
        return <Unauthorized />;
    }

    if (isLoading) {
        return <LoadingState className="py-20" />;
    }

    if (isError) {
        return <ErrorState onRetry={refetch} />;
    }

    if (!reportCard) {
        return <EmptyState title="Report card not found for this student." className="py-16" />;
    }

    return (
        <div className="space-y-6">
            <PrintableReportCard
                reportCard={reportCard}
                onViewTranscript={() => router.push(`/dashboard/examinations/transcript/${id}`)}
            />
        </div>
    );
}
