"use client";

import { useState } from "react";
import {
    LoaderCircle,
    FileText,
    Award,
    Printer,
    Search,
    User,
    X,
    TrendingDown,
    AlertTriangle,
    ShieldAlert,
    CheckCircle2,
    GraduationCap,
} from "lucide-react";
import { useMe } from "@/hooks/useAuth";
import {
    useBelowPassingReport,
    useExaminations,
    useStudentReportCard,
    useStudentTranscript,
} from "@/hooks/useExaminations";
import { useStudents } from "@/hooks/useStudents";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { PrintableReportCard } from "@/components/dashboard/examinations/PrintableReportCard";
import { PrintableTranscript } from "@/components/dashboard/examinations/PrintableTranscript";

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name?: string | null) {
    if (!name || typeof name !== "string") return AVATAR_PALETTES[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

function getInitials(name: string) {
    if (!name) return "ST";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    return name.slice(0, 2).toUpperCase();
}

export default function ExaminationResultsPage() {
    const { data: user } = useMe();
    const { can, isOwner, activeRole } = usePermissions();
    const isStudent = activeRole === "student";
    const canView = isOwner || can("view_results") || isStudent;

    const { selectedYear } = useAcademicYear();

    const [studentSearch, setStudentSearch] = useState("");
    const [selectedStudent, setSelectedStudent] = useState<any>(null);
    const [studentId, setStudentId] = useState(isStudent ? user?.profile?.student_id ?? "" : "");

    // Live student query for admin lookup
    const { data: studentList, isLoading: searchingStudents } = useStudents(
        studentSearch.trim().length >= 2 ? { search: studentSearch, pageSize: 6 } : { pageSize: 0 }
    );

    const effectiveStudentId = isStudent
        ? user?.profile?.student_id ?? undefined
        : selectedStudent?.id ?? (studentId ? studentId : undefined);

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
    const { data: belowPassing, isLoading: loadingBelow } = useBelowPassingReport(
        reportExamId || undefined
    );

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-7 max-w-7xl mx-auto pb-24 animate-in fade-in duration-500">
            {/* 1. Header */}
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800 print:hidden">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Award className="h-7 w-7 text-indigo-600 dark:text-indigo-400" />
                        <span>Academic Results &amp; Transcripts</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {isStudent
                            ? "Your official term report card, cumulative grade transcript, and published academic evaluation"
                            : "Inspect individual student report cards, cumulative transcripts, and below-passing performance audits"}
                    </p>
                </div>

                {/* Report Card vs Transcript Switcher */}
                {effectiveStudentId && (
                    <div className="flex items-center gap-1.5 p-1 bg-slate-100 dark:bg-slate-800/80 rounded-xl border border-slate-200 dark:border-slate-700">
                        <Button
                            variant={viewMode === "report-card" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setViewMode("report-card")}
                            className={`h-8 px-3 text-xs font-semibold gap-1.5 cursor-pointer ${
                                viewMode === "report-card"
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "text-slate-600 dark:text-slate-300"
                            }`}
                        >
                            <FileText className="h-3.5 w-3.5" />
                            <span>Report Card</span>
                        </Button>
                        <Button
                            variant={viewMode === "transcript" ? "default" : "ghost"}
                            size="sm"
                            onClick={() => setViewMode("transcript")}
                            className={`h-8 px-3 text-xs font-semibold gap-1.5 cursor-pointer ${
                                viewMode === "transcript"
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "text-slate-600 dark:text-slate-300"
                            }`}
                        >
                            <Award className="h-3.5 w-3.5" />
                            <span>Academic Transcript</span>
                        </Button>
                    </div>
                )}
            </div>

            {/* 2. Student Selector Card (for Staff/Admin) */}
            {!isStudent && (
                <div className="bg-white dark:bg-slate-900 rounded-2xl border border-slate-200/80 dark:border-slate-800 p-5 shadow-2xs space-y-4 print:hidden">
                    <div className="max-w-md relative space-y-1.5">
                        <label className="text-xs font-semibold text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                            <User className="h-3.5 w-3.5 text-slate-500" />
                            Select Student by Name or Enrollment ID
                        </label>

                        {selectedStudent ? (
                            <div className="flex items-center justify-between p-2.5 rounded-xl bg-indigo-50/70 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800">
                                <div className="flex items-center gap-2.5">
                                    <div className="h-8 w-8 rounded-full bg-indigo-600 text-white font-bold text-xs flex items-center justify-center">
                                        {selectedStudent.first_name?.[0]}
                                    </div>
                                    <div>
                                        <div className="text-xs font-bold text-slate-900 dark:text-white">
                                            {selectedStudent.first_name} {selectedStudent.last_name}
                                        </div>
                                        <div className="text-[10px] font-mono text-slate-500">
                                            {selectedStudent.enrollment_id}
                                        </div>
                                    </div>
                                </div>
                                <Button
                                    type="button"
                                    variant="ghost"
                                    size="sm"
                                    onClick={() => {
                                        setSelectedStudent(null);
                                        setStudentId("");
                                    }}
                                    className="h-7 px-2 text-xs text-slate-500 hover:text-rose-600"
                                >
                                    Change
                                </Button>
                            </div>
                        ) : (
                            <div className="relative">
                                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                                <Input
                                    placeholder="Type student name or ID (e.g. Rahul)..."
                                    value={studentSearch}
                                    onChange={(e) => setStudentSearch(e.target.value)}
                                    className="h-10 pl-8.5 pr-8 text-xs border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 font-medium"
                                />
                                {studentList && studentList.results && studentList.results.length > 0 && (
                                    <div className="absolute z-30 left-0 right-0 mt-1 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl shadow-lg overflow-hidden max-h-56 overflow-y-auto">
                                        {studentList.results.map((st: any) => (
                                            <button
                                                key={st.id}
                                                type="button"
                                                onClick={() => {
                                                    setSelectedStudent(st);
                                                    setStudentId(st.id);
                                                    setStudentSearch("");
                                                }}
                                                className="w-full text-left p-2.5 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 last:border-0 cursor-pointer"
                                            >
                                                <div>
                                                    <div className="text-xs font-semibold text-slate-900 dark:text-white">
                                                        {st.first_name} {st.last_name}
                                                    </div>
                                                    <div className="text-[10px] text-slate-400">
                                                        {st.current_section?.name || "Enrolled"}
                                                    </div>
                                                </div>
                                                <span className="font-mono text-[10px] bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded text-slate-600 dark:text-slate-400">
                                                    {st.enrollment_id}
                                                </span>
                                            </button>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                </div>
            )}

            {!effectiveStudentId && (
                <EmptyState
                    title={
                        isStudent
                            ? "No student profile is linked to your user account."
                            : "Search and select a student above to generate their report card and transcript."
                    }
                    description="Official grade transcripts and term reports require an active enrolled student profile."
                    className="py-16 text-slate-500 text-sm print:hidden"
                />
            )}

            {/* View Mode: Report Card */}
            {effectiveStudentId && viewMode === "report-card" && (
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
            )}

            {/* View Mode: Academic Transcript */}
            {effectiveStudentId && viewMode === "transcript" && (
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

            {/* Below-Passing Academic Diagnostic Report (For Staff/Faculty) */}
            {(isOwner || can("view_exam_reports")) && (
                <div className="space-y-4 pt-6 border-t border-slate-200 dark:border-slate-800 print:hidden">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                        <div>
                            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                                <TrendingDown className="w-5 h-5 text-rose-600" />
                                <span>Below-Passing Performance Audit</span>
                            </h2>
                            <p className="text-xs text-slate-500 mt-0.5">
                                Identifies students failing to meet term passing thresholds across published exams
                            </p>
                        </div>

                        <div className="w-full sm:w-72">
                            <Select value={reportExamId} onValueChange={setReportExamId}>
                                <SelectTrigger className="h-9 text-xs border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 font-medium">
                                    <SelectValue placeholder="Select published exam..." />
                                </SelectTrigger>
                                <SelectContent>
                                    {examinations
                                        ?.filter((e) => e.is_published)
                                        .map((e) => (
                                            <SelectItem key={e.id} value={e.id} className="text-xs">
                                                {e.name}
                                            </SelectItem>
                                        ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>

                    {loadingBelow ? (
                        <LoadingState className="py-12" />
                    ) : belowPassing && belowPassing.students.length > 0 ? (
                        <TableShell>
                            <Table>
                                <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                    <TableRow>
                                        <TableHead className="py-3 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Student Candidate
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Enrollment ID
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider pr-4 text-right">
                                            Score Percentage
                                        </TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {belowPassing.students.map((s) => {
                                        const avatarStyle = getAvatarStyle(s.full_name);
                                        const initials = getInitials(s.full_name);
                                        return (
                                            <TableRow
                                                key={String(s.student)}
                                                className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                            >
                                                <TableCell className="py-3 pl-4">
                                                    <div className="flex items-center gap-2.5">
                                                        <div
                                                            className={`h-7 w-7 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                        >
                                                            {initials}
                                                        </div>
                                                        <span className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {s.full_name}
                                                        </span>
                                                    </div>
                                                </TableCell>
                                                <TableCell className="py-3 font-mono text-xs text-slate-500">
                                                    {s.enrollment_id}
                                                </TableCell>
                                                <TableCell className="py-3 pr-4 text-right">
                                                    <Badge
                                                        variant="outline"
                                                        className="bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 font-mono font-bold text-xs"
                                                    >
                                                        {s.percentage}%
                                                    </Badge>
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableShell>
                    ) : reportExamId ? (
                        <div className="p-8 rounded-2xl border border-emerald-200/60 dark:border-emerald-900/40 bg-emerald-50/30 dark:bg-emerald-950/10 text-center space-y-1">
                            <CheckCircle2 className="h-6 w-6 text-emerald-600 mx-auto" />
                            <h3 className="text-xs font-bold text-slate-900 dark:text-white">
                                All students met passing benchmarks
                            </h3>
                            <p className="text-[11px] text-slate-500">
                                Zero candidates scored below the required passing percentage for this examination.
                            </p>
                        </div>
                    ) : null}
                </div>
            )}
        </div>
    );
}
