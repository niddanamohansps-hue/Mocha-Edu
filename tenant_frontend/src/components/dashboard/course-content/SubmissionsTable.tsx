import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoaderCircle, FileText, Calendar } from "lucide-react";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow
} from "@/components/ui/table";
import { format } from "date-fns";
import { statusConfig } from "./constants";
import { AssignmentSubmission } from "@/types/CourseContent";

interface SubmissionsTableProps {
    submissions: AssignmentSubmission[];
    isLoading: boolean;
    onGradeClick: (submission: AssignmentSubmission) => void;
    selectedAssignment?: string;
}

export function SubmissionsTable({
    submissions,
    isLoading,
    onGradeClick,
    selectedAssignment
}: SubmissionsTableProps) {
    const submissionsToGrade = submissions?.filter(s => s.status === 'submitted' || s.status === 'graded') || [];

    return (
        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-950 overflow-hidden shadow-sm">
            <Table>
                <TableHeader className="bg-slate-50/50 dark:bg-slate-900/50">
                    <TableRow>
                        <TableHead>Student</TableHead>
                        <TableHead>Assignment</TableHead>
                        <TableHead>Submitted At</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {isLoading ? (
                        <TableRow>
                            <TableCell colSpan={6} className="h-32 text-center">
                                <LoaderCircle className="h-8 w-8 animate-spin text-indigo-600 mx-auto" />
                            </TableCell>
                        </TableRow>
                    ) : submissionsToGrade && submissionsToGrade.length > 0 ? (
                        submissionsToGrade.map((submission) => {
                            const StatusIcon = statusConfig[submission.status].icon;
                            const statusColor = statusConfig[submission.status].color;

                            return (
                                <TableRow key={submission.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/50 transition-colors">
                                    <TableCell className="font-medium">
                                        <div>
                                            <p>{submission.student_name}</p>
                                            <p className="text-xs text-slate-500">{submission.student_enrollment_id}</p>
                                        </div>
                                    </TableCell>
                                    <TableCell>{submission.assignment_title}</TableCell>
                                    <TableCell>
                                        {submission.submitted_at ? (
                                            <div className="flex items-center gap-1 text-sm">
                                                <Calendar className="h-3 w-3 text-slate-400" />
                                                {format(new Date(submission.submitted_at), "MMM d, h:mm a")}
                                            </div>
                                        ) : (
                                            <span className="text-slate-400 text-sm">Not submitted</span>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        <StatusBadge
                                            label={submission.status_display}
                                            icon={<StatusIcon className="h-3 w-3 mr-1" />}
                                            className={`border ${statusColor} text-xs`}
                                        />
                                        {submission.is_late && (
                                            <Badge variant="destructive" className="ml-2 text-xs">Late</Badge>
                                        )}
                                    </TableCell>
                                    <TableCell>
                                        {submission.score !== null ? (
                                            <span className="font-semibold text-green-600 dark:text-green-400">
                                                {submission.score}
                                            </span>
                                        ) : (
                                            <span className="text-slate-400 text-sm">-</span>
                                        )}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        <Button
                                            size="sm"
                                            onClick={() => onGradeClick(submission)}
                                            disabled={submission.status === 'pending'}
                                        >
                                            {submission.status === 'graded' ? 'Re-grade' : 'Grade'}
                                        </Button>
                                    </TableCell>
                                </TableRow>
                            );
                        })
                    ) : (
                        <TableRow>
                            <TableCell colSpan={6} className="h-32 text-center">
                                <div className="flex flex-col items-center justify-center text-slate-400">
                                    <FileText className="h-12 w-12 mb-2 opacity-20" />
                                    <p>No submissions to grade</p>
                                    <p className="text-xs mt-1">
                                        {selectedAssignment ? "Try selecting a different assignment" : "Select an assignment to view submissions"}
                                    </p>
                                </div>
                            </TableCell>
                        </TableRow>
                    )}
                </TableBody>
            </Table>
        </div>
    );
}
