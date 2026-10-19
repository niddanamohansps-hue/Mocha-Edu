"use client";

import { useState } from "react";
import { LoaderCircle, FileText, Award } from "lucide-react";
import { useMe } from "@/hooks/useAuth";
import {
    useBelowPassingReport,
    useExaminations,
    useStudentReportCard,
    useStudentTranscript,
} from "@/hooks/useExaminations";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { PrintableReportCard } from "@/components/dashboard/examinations/PrintableReportCard";
import { PrintableTranscript } from "@/components/dashboard/examinations/PrintableTranscript";

export default function ExaminationResultsPage() {
    const { data: user } = useMe();
    const { can, isOwner, activeRole } = usePermissions();
    const isStudent = activeRole === "student";
    const canView = isOwner || can("view_results") || isStudent;

    const { selectedYear } = useAcademicYear();

    const [studentId, setStudentId] = useState(isStudent ? user?.profile?.student_id ?? "" : "");
    const effectiveStudentId = isStudent ? user?.profile?.student_id ?? undefined : studentId || undefined;

    const [viewMode, setViewMode] = useState<"report-card" | "transcript">("report-card");

    const {
        data: reportCard,
        isLoading: loadingReport,
        isError: reportError,
        refetch: refetchReport,
    } = useStudentReportCard(effectiveStudentId, selectedYear?.name);

    const {
        data: transcript,
        isLoading: loadingTranscript,
        isError: transcriptError,
        refetch: refetchTranscript,
    } = useStudentTranscript(viewMode === "transcript" ? effectiveStudentId : undefined);

    const { data: examinations } = useExaminations(selectedYear?.name);
    const [reportExamId, setReportExamId] = useState("");
    const { data: belowPassing, isLoading: loadingBelow } = useBelowPassingReport(reportExamId || undefined);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-8">
            <div className="flex flex-wrap items-center justify-between gap-4 print:hidden">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Examination Results & Transcripts</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {isStudent ? "Your official report card and academic transcript" : "Published results, report cards, and student transcripts"}
                    </p>
                </div>

                {effectiveStudentId && (
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

            {!isStudent && (
                <div className="w-80 print:hidden">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Student ID (UUID)</label>
                    <Input
                        placeholder="Paste student UUID..."
                        value={studentId}
                        onChange={(e) => setStudentId(e.target.value)}
                    />
                </div>
            )}

            {!effectiveStudentId && (
                <EmptyState
                    title={isStudent ? "No student record linked to your account yet." : "Enter a student ID to view their report card and transcript."}
                    className="py-12 text-slate-500 text-sm print:hidden"
                />
            )}

            {/* View Mode: Report Card */}
            {effectiveStudentId && viewMode === "report-card" && (
                <>
                    {loadingReport && <LoadingState className="py-16" />}
                    {reportError && !loadingReport && <ErrorState onRetry={refetchReport} />}
                    {reportCard && (
                        <PrintableReportCard
                            reportCard={reportCard}
                            onViewTranscript={() => setViewMode("transcript")}
                        />
                    )}
                </>
            )}

            {/* View Mode: Academic Transcript */}
            {effectiveStudentId && viewMode === "transcript" && (
                <>
                    {loadingTranscript && <LoadingState className="py-16" />}
                    {transcriptError && !loadingTranscript && <ErrorState onRetry={refetchTranscript} />}
                    {transcript && (
                        <PrintableTranscript
                            transcript={transcript}
                            onBackToReportCard={() => setViewMode("report-card")}
                        />
                    )}
                </>
            )}

            {/* Below-Passing Report for staff */}
            {(isOwner || can("view_exam_reports")) && (
                <div className="space-y-4 pt-6 border-t border-slate-200 dark:border-slate-800 print:hidden">
                    <h2 className="text-lg font-bold">Below-Passing Performance Report</h2>
                    <div className="w-72">
                        <Select value={reportExamId} onValueChange={setReportExamId}>
                            <SelectTrigger><SelectValue placeholder="Select examination" /></SelectTrigger>
                            <SelectContent>
                                {examinations?.filter((e) => e.is_published).map((e) => (
                                    <SelectItem key={e.id} value={e.id}>{e.name}</SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>
                    {loadingBelow ? (
                        <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                    ) : belowPassing && belowPassing.students.length > 0 ? (
                        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 dark:bg-slate-900">
                                    <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                        <th className="px-4 py-3">Student</th>
                                        <th className="px-4 py-3">Enrollment ID</th>
                                        <th className="px-4 py-3">Percentage</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {belowPassing.students.map((s) => (
                                        <tr key={s.student} className="border-t border-slate-100 dark:border-slate-800">
                                            <td className="px-4 py-2 font-medium">{s.full_name}</td>
                                            <td className="px-4 py-2 text-slate-500">{s.enrollment_id}</td>
                                            <td className="px-4 py-2 text-red-600 font-bold">{s.percentage}%</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    ) : reportExamId ? (
                        <EmptyState title="No students below passing for this examination." className="py-4 text-slate-500 text-sm" />
                    ) : null}
                </div>
            )}
        </div>
    );
}
