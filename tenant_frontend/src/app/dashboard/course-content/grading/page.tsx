"use client";

import { useState, useMemo } from "react";
import {
    useSubmissions,
    useGradeSubmission,
    useAssignments
} from "@/hooks/useCourseContent";
import { GradingDialog } from "@/components/dashboard/course-content/GradingDialog";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import {
    CheckCircle2,
    Clock,
    FileText,
    Calendar,
    Users,
    Trophy,
    Search,
    X,
    Pencil,
    Download,
    ExternalLink,
    AlertCircle,
    Check,
} from "lucide-react";
import { format } from "date-fns";
import { AssignmentSubmission } from "@/types/CourseContent";

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name: string) {
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
    if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
}

export default function GradingPage() {
    const [selectedAssignment, setSelectedAssignment] = useState<string>("all");
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "submitted" | "graded">("all");

    const [isGradingDialogOpen, setIsGradingDialogOpen] = useState(false);
    const [currentSubmission, setCurrentSubmission] = useState<any>(null);

    const { data: assignments = [], isLoading: loadingAssignments, isError: assignmentsError, refetch: refetchAssignments } = useAssignments();
    const { data: submissions = [], isLoading: loadingSubmissions } = useSubmissions(
        selectedAssignment !== "all" ? selectedAssignment : undefined
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

    // Filter submissions to grade (exclude purely pending non-turnins)
    const submissionsToGrade = useMemo(() => {
        return submissions.filter((s) => s.status === "submitted" || s.status === "graded");
    }, [submissions]);

    // Apply client-side search & status filtering
    const filteredSubmissions = useMemo(() => {
        return submissionsToGrade.filter((s) => {
            const matchesSearch =
                !search.trim() ||
                s.student_name.toLowerCase().includes(search.toLowerCase()) ||
                s.student_enrollment_id.toLowerCase().includes(search.toLowerCase()) ||
                s.assignment_title.toLowerCase().includes(search.toLowerCase());

            if (!matchesSearch) return false;

            if (statusFilter === "submitted") return s.status === "submitted";
            if (statusFilter === "graded") return s.status === "graded";

            return true;
        });
    }, [submissionsToGrade, search, statusFilter]);

    // Metrics
    const metrics = useMemo(() => {
        const total = submissionsToGrade.length;
        const awaitingGrading = submissionsToGrade.filter((s) => s.status === "submitted").length;
        const graded = submissionsToGrade.filter((s) => s.status === "graded").length;
        const late = submissionsToGrade.filter((s) => s.is_late).length;
        return { total, awaitingGrading, graded, late };
    }, [submissionsToGrade]);

    if (loadingAssignments) {
        return <LoadingState className="py-20" />;
    }

    if (assignmentsError) {
        return <ErrorState onRetry={refetchAssignments} />;
    }

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <CheckCircle2 className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Submissions & Assessment Grading Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Evaluate student coursework submissions, record rubrics scores, provide constructive remarks, and audit submission timestamps
                    </p>
                </div>
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Turn-ins */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Turn-ins</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <FileText className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.total}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">submissions</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Ready for evaluation
                    </p>
                </div>

                {/* Awaiting Grading */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Needs Evaluation</span>
                        <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                            <Clock className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.awaitingGrading}
                        </span>
                        <span className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold">
                            pending review
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Requires score & feedback
                    </p>
                </div>

                {/* Graded */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Completed & Scored</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.graded}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            finalized
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Scores posted to student portal
                    </p>
                </div>

                {/* Late Turn-ins */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Late Turn-ins</span>
                        <div className="p-1.5 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">
                            <AlertCircle className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.late}
                        </span>
                        <span className="text-[11px] text-rose-600 dark:text-rose-400 font-semibold">
                            after deadline
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Subject to deduction policy
                    </p>
                </div>
            </div>

            {/* 3. Filter Controls Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col md:flex-row items-center justify-between gap-3">
                {/* Search */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search student by name, enrollment ID, or assignment..."
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                    {search && (
                        <button
                            onClick={() => setSearch("")}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                {/* Assignment & Status Controls */}
                <div className="flex items-center gap-2 w-full md:w-auto shrink-0 justify-between sm:justify-start">
                    {/* Assignment Selector */}
                    <div className="w-56">
                        <Select value={selectedAssignment} onValueChange={setSelectedAssignment}>
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Assignments" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Coursework Assignments</SelectItem>
                                {assignments.map((a) => (
                                    <SelectItem key={a.id} value={a.id} className="text-xs">
                                        {a.content_details.title}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Status Funnel Pills */}
                    <div className="flex items-center gap-1 shrink-0">
                        {[
                            { value: "all", label: "All Turn-ins" },
                            { value: "submitted", label: "Needs Grading" },
                            { value: "graded", label: "Graded" },
                        ].map((opt) => (
                            <button
                                key={opt.value}
                                type="button"
                                onClick={() => setStatusFilter(opt.value as any)}
                                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                                    statusFilter === opt.value
                                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                        : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                                }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* 4. Submissions Table */}
            {loadingSubmissions ? (
                <LoadingState className="py-20" />
            ) : filteredSubmissions.length === 0 ? (
                <EmptyState
                    icon={<CheckCircle2 className="h-14 w-14 text-slate-200 dark:text-slate-700 mb-3" />}
                    title={search ? "No submissions matched your search" : "No student submissions pending evaluation"}
                    titleAs="h3"
                    description={
                        search
                            ? "Try adjusting your search query or selecting a different assignment from the dropdown."
                            : "As enrolled students submit their project files and solutions, they will automatically appear here for evaluation."
                    }
                />
            ) : (
                <TableShell>
                    <Table>
                        <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                            <TableRow className="hover:bg-transparent">
                                <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Student
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Assignment
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Submission Date
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Status & Punctuality
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Score
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Faculty Feedback
                                </TableHead>
                                <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Actions
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredSubmissions.map((sub) => {
                                const avatarStyle = getAvatarStyle(sub.student_name);
                                const initials = getInitials(sub.student_name);

                                return (
                                    <TableRow
                                        key={sub.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        {/* Student with Avatar */}
                                        <TableCell className="py-3.5 pl-4">
                                            <div className="flex items-center gap-2.5">
                                                <div
                                                    className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                >
                                                    {initials}
                                                </div>
                                                <div>
                                                    <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                        {sub.student_name}
                                                    </div>
                                                    <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                        {sub.student_enrollment_id}
                                                    </code>
                                                </div>
                                            </div>
                                        </TableCell>

                                        {/* Assignment */}
                                        <TableCell className="py-3.5 text-xs font-semibold text-slate-800 dark:text-slate-200">
                                            {sub.assignment_title}
                                        </TableCell>

                                        {/* Submitted At */}
                                        <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-400">
                                            {sub.submitted_at ? (
                                                <div className="flex items-center gap-1.5 font-medium">
                                                    <Calendar className="w-3.5 h-3.5 text-slate-400" />
                                                    <span>{format(new Date(sub.submitted_at), "MMM d, h:mm a")}</span>
                                                </div>
                                            ) : (
                                                <span className="text-slate-400">Not submitted</span>
                                            )}
                                        </TableCell>

                                        {/* Status & Punctuality */}
                                        <TableCell className="py-3.5">
                                            <div className="flex items-center gap-1.5">
                                                {sub.status === "graded" ? (
                                                    <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                                                        Graded
                                                    </Badge>
                                                ) : (
                                                    <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 font-semibold text-[11px]">
                                                        Submitted
                                                    </Badge>
                                                )}
                                                {sub.is_late && (
                                                    <Badge variant="outline" className="border-rose-300 text-rose-700 bg-rose-50 dark:bg-rose-950/40 text-[10px] font-bold">
                                                        Late
                                                    </Badge>
                                                )}
                                            </div>
                                        </TableCell>

                                        {/* Score */}
                                        <TableCell className="py-3.5">
                                            {sub.score !== null ? (
                                                <span className="text-xs font-bold text-emerald-600 dark:text-emerald-400">
                                                    {sub.score} pts
                                                </span>
                                            ) : (
                                                <span className="text-xs text-slate-400 font-medium">Ungraded</span>
                                            )}
                                        </TableCell>

                                        {/* Feedback */}
                                        <TableCell className="py-3.5 text-xs text-slate-500 max-w-xs truncate">
                                            {sub.feedback || "—"}
                                        </TableCell>

                                        {/* Actions */}
                                        <TableCell className="py-3.5 pr-4 text-right">
                                            <div className="flex items-center justify-end gap-1.5">
                                                {sub.submission_file && (
                                                    <a
                                                        href={sub.submission_file}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="inline-flex items-center justify-center h-8 w-8 text-slate-500 hover:text-sky-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg cursor-pointer transition"
                                                        title="Download Student File"
                                                    >
                                                        <Download className="w-3.5 h-3.5" />
                                                    </a>
                                                )}
                                                <Button
                                                    size="sm"
                                                    onClick={() => openGradingDialog(sub)}
                                                    className="h-8 px-3 text-xs font-semibold bg-sky-600 hover:bg-sky-500 text-white rounded-lg shadow-sm cursor-pointer"
                                                >
                                                    <Pencil className="w-3 h-3 mr-1" />
                                                    <span>{sub.status === "graded" ? "Re-grade" : "Grade"}</span>
                                                </Button>
                                            </div>
                                        </TableCell>
                                    </TableRow>
                                );
                            })}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Grading Dialog */}
            <GradingDialog
                open={isGradingDialogOpen}
                onOpenChange={setIsGradingDialogOpen}
                submission={currentSubmission}
                onSubmit={handleGrade}
                isGrading={isGrading}
            />
        </div>
    );
}
