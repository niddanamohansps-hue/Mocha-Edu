"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
    useAssignments,
    useCreateAssignment,
    useMySubmissions,
    useSubmitAssignment
} from "@/hooks/useCourseContent";
import { useSections } from "@/hooks/useAcademics";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Plus,
    FileText,
    Search,
    X,
    Calendar,
    Trophy,
    CheckCircle2,
    Clock,
    Upload,
    LayoutGrid,
    List,
    AlertCircle,
    Users,
    ChevronRight,
    ArrowUpRight,
} from "lucide-react";
import { CreateAssignmentDialog } from "@/components/dashboard/course-content/CreateAssignmentDialog";
import { SubmitAssignmentDialog } from "@/components/dashboard/course-content/SubmitAssignmentDialog";
import { AssignmentCard } from "@/components/dashboard/course-content/AssignmentCard";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { format } from "date-fns";

export default function AssignmentsPage() {
    const { can, isOwner, activeRole } = usePermissions();
    const canCreate = isOwner || can("create_assignment");
    const isStudent = activeRole === "student";

    const { data: assignments = [], isLoading: loadingAssignments, isError: assignmentsError, refetch: refetchAssignments } = useAssignments();
    const { data: mySubmissions = [], isLoading: loadingSubmissions } = useMySubmissions();
    const { mutate: createAssignment, isPending: isCreating } = useCreateAssignment();
    const { mutate: submitAssignment, isPending: isSubmitting } = useSubmitAssignment();

    const { data: sections } = useSections();

    const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
    const [isSubmitDialogOpen, setIsSubmitDialogOpen] = useState(false);
    const [selectedAssignment, setSelectedAssignment] = useState<string | null>(null);

    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "active" | "overdue" | "submitted">("all");
    const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

    const handleCreateAssignment = (data: any) => {
        createAssignment(data, {
            onSuccess: () => {
                setIsCreateDialogOpen(false);
                refetchAssignments();
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
                refetchAssignments();
            }
        });
    };

    const handleSubmitClick = (submissionId: string) => {
        setSelectedAssignment(submissionId);
        setIsSubmitDialogOpen(true);
    };

    // Map submissions to assignments for students
    const assignmentsWithSubmissions = useMemo(() => {
        return assignments.map((assignment) => {
            const submission = mySubmissions.find((s) => s.assignment === assignment.id);
            return { ...assignment, submission };
        });
    }, [assignments, mySubmissions]);

    // Filter assignments
    const filteredAssignments = useMemo(() => {
        return assignmentsWithSubmissions.filter((a) => {
            const matchesSearch =
                !search.trim() ||
                a.content_details.title.toLowerCase().includes(search.toLowerCase()) ||
                (a.content_details.description && a.content_details.description.toLowerCase().includes(search.toLowerCase()));

            if (!matchesSearch) return false;

            if (statusFilter === "overdue") return a.is_overdue;
            if (statusFilter === "active") return !a.is_overdue;
            if (statusFilter === "submitted") return a.submission && a.submission.status !== "pending";

            return true;
        });
    }, [assignmentsWithSubmissions, search, statusFilter]);

    // Metrics
    const metrics = useMemo(() => {
        const total = assignments.length;
        const overdue = assignments.filter((a) => a.is_overdue).length;
        const totalPoints = assignments.reduce((acc, a) => acc + (a.total_points || 0), 0);
        const totalSubmissions = assignments.reduce((acc, a) => acc + (a.total_submissions || 0), 0);
        const gradedSubmissions = assignments.reduce((acc, a) => acc + (a.graded_submissions || 0), 0);
        return { total, overdue, totalPoints, totalSubmissions, gradedSubmissions };
    }, [assignments]);

    if (loadingAssignments || (isStudent && loadingSubmissions)) {
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
                        <FileText className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Course Content & Academic Assignments</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        {canCreate
                            ? "Course syllabus tasks, multi-subject project prompts, digital submission collection, and grading desk"
                            : "Track pending coursework, review deadlines, download reference materials, and upload your submissions"}
                    </p>
                </div>

                {canCreate && (
                    <Button
                        onClick={() => setIsCreateDialogOpen(true)}
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Create Assignment</span>
                    </Button>
                )}
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Assignments */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Assignments</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <FileText className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.total}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">course tasks</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Active syllabus modules
                    </p>
                </div>

                {/* Overdue / Critical Deadlines */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Past Due Deadlines</span>
                        <div className="p-1.5 rounded-lg bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400">
                            <Clock className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.overdue}
                        </span>
                        <span className="text-[11px] text-rose-600 dark:text-rose-400 font-semibold">
                            expired tasks
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Requires grace period or closure
                    </p>
                </div>

                {/* Submissions Volume */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Submissions</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Users className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalSubmissions}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">student turn-ins</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Across all active sections
                    </p>
                </div>

                {/* Graded & Evaluated */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Evaluated Tasks</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.gradedSubmissions}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            graded
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Scored with faculty feedback
                    </p>
                </div>
            </div>

            {/* 3. Search and View Controls Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
                {/* Search */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search assignments by title or description..."
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

                <div className="flex items-center gap-2 self-start sm:self-auto shrink-0">
                    {/* Status Funnel Pills */}
                    <div className="flex items-center gap-1">
                        {[
                            { value: "all", label: "All Tasks" },
                            { value: "active", label: "Active" },
                            { value: "overdue", label: "Past Due" },
                            ...(isStudent ? [{ value: "submitted", label: "Turned In" }] : []),
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

                    {/* View Switcher Toggle */}
                    <div className="flex items-center border border-slate-200 dark:border-slate-800 rounded-lg p-0.5 bg-slate-50/50 dark:bg-slate-900">
                        <button
                            type="button"
                            onClick={() => setViewMode("grid")}
                            className={`p-1.5 rounded-md text-xs transition cursor-pointer ${
                                viewMode === "grid"
                                    ? "bg-white dark:bg-slate-800 text-sky-600 shadow-2xs font-bold"
                                    : "text-slate-400 hover:text-slate-600"
                            }`}
                            title="Grid View"
                        >
                            <LayoutGrid className="w-3.5 h-3.5" />
                        </button>
                        <button
                            type="button"
                            onClick={() => setViewMode("table")}
                            className={`p-1.5 rounded-md text-xs transition cursor-pointer ${
                                viewMode === "table"
                                    ? "bg-white dark:bg-slate-800 text-sky-600 shadow-2xs font-bold"
                                    : "text-slate-400 hover:text-slate-600"
                            }`}
                            title="Table View"
                        >
                            <List className="w-3.5 h-3.5" />
                        </button>
                    </div>
                </div>
            </div>

            {/* 4. Assignments Content */}
            {filteredAssignments.length === 0 ? (
                <EmptyState
                    icon={<FileText className="h-14 w-14 text-slate-200 dark:text-slate-700 mb-3" />}
                    title={search ? "No assignments matched your search" : "No assignments found"}
                    titleAs="h3"
                    description={
                        search
                            ? "Try searching for a different keyword or clearing your status filter."
                            : canCreate
                            ? "Click Create Assignment above to publish homework tasks and project briefs for your cohorts."
                            : "You have no active assignments due at this time. Check back later."
                    }
                    action={
                        !search && canCreate ? (
                            <Button
                                onClick={() => setIsCreateDialogOpen(true)}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Create First Assignment</span>
                            </Button>
                        ) : undefined
                    }
                />
            ) : viewMode === "grid" ? (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                    {filteredAssignments.map((assignment) => (
                        <AssignmentCard
                            key={assignment.id}
                            assignment={assignment as any}
                            isStudent={isStudent}
                            canCreate={canCreate}
                            onSubmitClick={handleSubmitClick}
                        />
                    ))}
                </div>
            ) : (
                <TableShell>
                    <Table>
                        <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                            <TableRow className="hover:bg-transparent">
                                <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Assignment Title & Scope
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Due Date
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Total Points
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Submissions
                                </TableHead>
                                <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Status
                                </TableHead>
                                <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                    Actions
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filteredAssignments.map((a) => (
                                <TableRow
                                    key={a.id}
                                    className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                >
                                    {/* Title & Scope */}
                                    <TableCell className="py-3.5 pl-4">
                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                            {a.content_details.title}
                                        </div>
                                        <div className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                                            {a.content_details.description || "No description provided."}
                                        </div>
                                    </TableCell>

                                    {/* Due Date */}
                                    <TableCell className="py-3.5 text-xs">
                                        <span className={`font-semibold ${a.is_overdue ? "text-rose-600 dark:text-rose-400" : "text-slate-700 dark:text-slate-300"}`}>
                                            {format(new Date(a.due_date), "MMM d, yyyy h:mm a")}
                                        </span>
                                    </TableCell>

                                    {/* Points */}
                                    <TableCell className="py-3.5 text-xs font-bold text-slate-900 dark:text-white">
                                        {a.total_points} pts
                                    </TableCell>

                                    {/* Submissions */}
                                    <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-400">
                                        <span className="font-semibold text-slate-800 dark:text-slate-200">
                                            {a.total_submissions || 0}
                                        </span>{" "}
                                        turned in ({a.graded_submissions || 0} graded)
                                    </TableCell>

                                    {/* Status */}
                                    <TableCell className="py-3.5">
                                        {a.is_overdue ? (
                                            <Badge variant="outline" className="border-rose-300 text-rose-700 bg-rose-50 dark:bg-rose-950/40 text-[10px] font-semibold">
                                                Past Due
                                            </Badge>
                                        ) : (
                                            <Badge className="bg-emerald-50 text-emerald-700 border border-emerald-300/80 text-[10px] font-semibold">
                                                Active
                                            </Badge>
                                        )}
                                    </TableCell>

                                    {/* Actions */}
                                    <TableCell className="py-3.5 pr-4 text-right">
                                        {isStudent ? (
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => {
                                                    if (!a.submission) {
                                                        alert("This assignment is not available for submission yet.");
                                                        return;
                                                    }
                                                    handleSubmitClick(a.submission.id);
                                                }}
                                                className="h-8 px-2.5 text-xs font-semibold text-sky-600"
                                            >
                                                <Upload className="w-3.5 h-3.5 mr-1" />
                                                <span>Submit</span>
                                            </Button>
                                        ) : (
                                            <Link href="/dashboard/course-content/grading">
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="h-8 px-2.5 text-xs text-sky-600 hover:text-sky-700 hover:bg-sky-50 dark:hover:bg-sky-950/40 rounded-lg cursor-pointer"
                                                >
                                                    <span>Grade Submissions</span>
                                                    <ChevronRight className="w-3.5 h-3.5 ml-1" />
                                                </Button>
                                            </Link>
                                        )}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Dialogs */}
            {canCreate && (
                <CreateAssignmentDialog
                    open={isCreateDialogOpen}
                    onOpenChange={setIsCreateDialogOpen}
                    onSubmit={handleCreateAssignment}
                    sections={sections}
                    isCreating={isCreating}
                />
            )}

            <SubmitAssignmentDialog
                open={isSubmitDialogOpen}
                onOpenChange={setIsSubmitDialogOpen}
                onSubmit={handleSubmit}
                isSubmitting={isSubmitting}
            />
        </div>
    );
}
