"use client";

import { useState } from "react";
import { useChildReportCard, useChildTranscript, useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { Button } from "@/components/ui/button";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { PrintableReportCard } from "@/components/dashboard/examinations/PrintableReportCard";
import { PrintableTranscript } from "@/components/dashboard/examinations/PrintableTranscript";
import { FileText, Award } from "lucide-react";

export default function ParentPortalResultsPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_child_results");

    const { selectedYear } = useAcademicYear();

    const { data: children } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);
    const [viewMode, setViewMode] = useState<"report-card" | "transcript">("report-card");

    const {
        data: reportCard,
        isLoading: loadingReport,
        isError: reportError,
        refetch: refetchReport,
    } = useChildReportCard(selectedChildId, selectedYear?.name);

    const {
        data: transcript,
        isLoading: loadingTranscript,
        isError: transcriptError,
        refetch: refetchTranscript,
    } = useChildTranscript(viewMode === "transcript" ? selectedChildId : undefined);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-4 print:hidden">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Examination Results & Transcripts</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Official report card and academic transcript for your child
                    </p>
                </div>

                {selectedChildId && (
                    <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-1 rounded-xl">
                        <Button
                            variant={viewMode === "report-card" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setViewMode("report-card")}
                            className="gap-2"
                        >
                            <FileText className="h-4 w-4" />
                            Report Card
                        </Button>
                        <Button
                            variant={viewMode === "transcript" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setViewMode("transcript")}
                            className="gap-2"
                        >
                            <Award className="h-4 w-4" />
                            Academic Transcript
                        </Button>
                    </div>
                )}
            </div>

            <div className="print:hidden">
                <ChildSwitcher
                    childOptions={children || []}
                    selectedId={selectedChildId}
                    onChange={setSelectedChildId}
                />
            </div>

            {!selectedChildId ? (
                <EmptyState
                    title={
                        children && children.length === 0
                            ? "No children are linked to your account yet."
                            : "Select a child to view their results and transcript."
                    }
                    className="py-16 text-slate-500 text-sm print:hidden"
                />
            ) : viewMode === "report-card" ? (
                <>
                    {loadingReport && <LoadingState className="py-20" />}
                    {reportError && !loadingReport && <ErrorState onRetry={refetchReport} />}
                    {reportCard && (
                        <PrintableReportCard
                            reportCard={reportCard}
                            onViewTranscript={() => setViewMode("transcript")}
                        />
                    )}
                </>
            ) : (
                <>
                    {loadingTranscript && <LoadingState className="py-20" />}
                    {transcriptError && !loadingTranscript && <ErrorState onRetry={refetchTranscript} />}
                    {transcript && (
                        <PrintableTranscript
                            transcript={transcript}
                            onBackToReportCard={() => setViewMode("report-card")}
                        />
                    )}
                </>
            )}
        </div>
    );
}
