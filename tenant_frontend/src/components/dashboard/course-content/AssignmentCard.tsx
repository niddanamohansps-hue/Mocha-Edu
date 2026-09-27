import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Calendar, Trophy, Upload } from "lucide-react";
import { format } from "date-fns";
import { statusConfig } from "./constants";

interface Assignment {
    id: string;
    content_details: {
        title: string;
        description: string;
    };
    due_date: string;
    total_points: number;
    is_overdue: boolean;
    total_submissions?: number;
    graded_submissions?: number;
    submission?: {
        id: string;
        status: "pending" | "submitted" | "graded";
        score?: number | null;
        feedback?: string;
    };
}

interface AssignmentCardProps {
    assignment: Assignment;
    isStudent: boolean;
    canCreate: boolean;
    onSubmitClick: (submissionId: string) => void;
}

export function AssignmentCard({ assignment, isStudent, canCreate, onSubmitClick }: AssignmentCardProps) {
    const isOverdue = assignment.is_overdue;
    const submission = assignment.submission;
    const statusInfo = submission ? statusConfig[submission.status] : statusConfig.pending;
    const StatusIcon = statusInfo.icon;

    return (
        <Card className="p-5 hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between mb-3">
                <h3 className="font-semibold text-slate-900 dark:text-white pr-2">
                    {assignment.content_details.title}
                </h3>
                <div className={`h-8 w-8 rounded-lg ${statusInfo.color} flex items-center justify-center flex-shrink-0`}>
                    <StatusIcon className="h-4 w-4" />
                </div>
            </div>

            <p className="text-sm text-slate-600 dark:text-slate-400 line-clamp-2 mb-4">
                {assignment.content_details.description}
            </p>

            <div className="space-y-2 mb-4">
                <div className="flex items-center gap-2 text-xs">
                    <Calendar className="h-3 w-3 text-slate-400" />
                    <span className={isOverdue ? "text-red-600 font-medium" : "text-slate-500"}>
                        Due: {format(new Date(assignment.due_date), "MMM d, yyyy h:mm a")}
                    </span>
                </div>
                <div className="flex items-center gap-2 text-xs text-slate-500">
                    <Trophy className="h-3 w-3 text-slate-400" />
                    Points: {assignment.total_points}
                </div>
            </div>

            {submission && submission.status === 'graded' && (
                <div className="mb-4 p-3 bg-green-50 dark:bg-green-900/10 rounded-lg border border-green-200 dark:border-green-900/20">
                    <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-green-700 dark:text-green-400">Score</span>
                        <span className="text-lg font-bold text-green-700 dark:text-green-400">
                            {submission.score}/{assignment.total_points}
                        </span>
                    </div>
                    {submission.feedback && (
                        <p className="text-xs text-green-600 dark:text-green-500 mt-1">
                            {submission.feedback}
                        </p>
                    )}
                </div>
            )}

            <div className="flex items-center justify-between pt-4 border-t border-slate-100 dark:border-slate-800">
                <Badge variant="outline" className="text-xs">
                    {statusInfo.label}
                </Badge>

                {isStudent && (!submission || submission.status === 'pending') && (
                    <Button
                        size="sm"
                        onClick={() => {
                            console.log("Submit button clicked for assignment:", assignment.id);
                            console.log("Submission:", submission);

                            if (!submission) {
                                alert("This assignment is not available for submission yet. Please contact your instructor.");
                                return;
                            }

                            onSubmitClick(submission.id);
                        }}
                    >
                        <Upload className="h-3 w-3 mr-1" />
                        Submit
                    </Button>
                )}

                {canCreate && (
                    <div className="text-xs text-slate-500">
                        {assignment.total_submissions}/{assignment.graded_submissions} graded
                    </div>
                )}
            </div>
        </Card>
    );
}
