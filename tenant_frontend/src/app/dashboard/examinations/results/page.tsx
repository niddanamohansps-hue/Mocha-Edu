"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useMe } from "@/hooks/useAuth";
import {
    useBelowPassingReport,
    useExaminations,
    useStudentReportCard,
} from "@/hooks/useExaminations";
import { usePermissions } from "@/providers/PermissionProvider";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { StatusBadge } from "@/components/common/StatusBadge";

export default function ExaminationResultsPage() {
    const { data: user } = useMe();
    const { can, isOwner, activeRole } = usePermissions();
    const isStudent = activeRole === "student";
    const canView = isOwner || can("view_results") || isStudent;

    const [studentId, setStudentId] = useState(isStudent ? user?.profile?.student_id ?? "" : "");
    const effectiveStudentId = isStudent ? user?.profile?.student_id ?? undefined : studentId || undefined;

    const { data: reportCard, isLoading: loadingReport, isError: reportError, refetch: refetchReport } = useStudentReportCard(effectiveStudentId);

    const { data: examinations } = useExaminations();
    const [reportExamId, setReportExamId] = useState("");
    const { data: belowPassing, isLoading: loadingBelow } = useBelowPassingReport(reportExamId || undefined);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-8">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Examination Results</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    {isStudent ? "Your published results" : "Published results and reports"}
                </p>
            </div>

            {!isStudent && (
                <div className="w-72">
                    <label className="text-xs font-medium text-slate-500 mb-1 block">Student ID</label>
                    <Input placeholder="Paste a student ID" value={studentId} onChange={(e) => setStudentId(e.target.value)} />
                </div>
            )}

            {!effectiveStudentId && (
                <EmptyState
                    title={isStudent ? "No student record linked to your account yet." : "Enter a student ID to view their results."}
                    className="py-6 text-slate-500 text-sm"
                />
            )}

            {effectiveStudentId && loadingReport && <LoadingState className="py-16" />}

            {effectiveStudentId && reportError && !loadingReport && <ErrorState onRetry={refetchReport} />}

            {effectiveStudentId && reportCard && reportCard.examinations.length === 0 && (
                <EmptyState title="No published results yet." className="py-6 text-slate-500 text-sm" />
            )}

            {effectiveStudentId && reportCard && reportCard.examinations.length > 0 && (
                <div className="space-y-6">
                    {reportCard.examinations.map((result) => (
                        <Card key={result.id} className="border-none shadow-md">
                            <CardContent className="p-6 space-y-4">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <p className="text-xs text-slate-500 uppercase font-bold">Overall</p>
                                        <p className="text-2xl font-black">
                                            {result.percentage}% - {result.overall_grade || "—"}
                                        </p>
                                    </div>
                                    <StatusBadge
                                        label={result.is_pass ? "PASS" : "FAIL"}
                                        className={`text-sm font-bold px-3 ${result.is_pass ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-700"}`}
                                    />
                                </div>
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                            <th className="py-2">Subject</th>
                                            <th className="py-2">Marks</th>
                                            <th className="py-2">%</th>
                                            <th className="py-2">Grade</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {result.subject_breakdown.map((sub) => (
                                            <tr key={sub.subject} className="border-t border-slate-100 dark:border-slate-800">
                                                <td className="py-2 font-medium">{sub.subject_name}</td>
                                                <td className="py-2">
                                                    {sub.is_absent ? "Absent" : sub.marks_obtained === null ? "—" : `${sub.marks_obtained}/${sub.max_marks}`}
                                                </td>
                                                <td className="py-2">{sub.percentage ?? "—"}</td>
                                                <td className="py-2">{sub.grade ?? "—"}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}

            {(isOwner || can("view_exam_reports")) && (
                <div className="space-y-4 pt-4 border-t border-slate-200 dark:border-slate-800">
                    <h2 className="text-lg font-bold">Below-Passing Report</h2>
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
