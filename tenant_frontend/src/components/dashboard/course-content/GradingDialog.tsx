import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { FileText, Download, Loader2 } from "lucide-react";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { AssignmentSubmission } from "@/types/CourseContent";
import { downloadSubmissionFile } from "@/hooks/useCourseContent";

interface GradingDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    submission: AssignmentSubmission | null;
    onSubmit: (data: { score: number; feedback: string }) => void;
    isGrading?: boolean;
}

export function GradingDialog({
    open,
    onOpenChange,
    submission,
    onSubmit,
    isGrading = false
}: GradingDialogProps) {
    const [isDownloading, setIsDownloading] = useState(false);

    const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
        e.preventDefault();
        const formData = new FormData(e.currentTarget);
        const data = {
            score: parseFloat(formData.get("score") as string),
            feedback: formData.get("feedback") as string
        };
        onSubmit(data);
    };

    if (!submission) return null;

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>Grade Submission</DialogTitle>
                    <DialogDescription>
                        Provide a score and feedback for this student
                    </DialogDescription>
                </DialogHeader>
                <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded-lg">
                        <p className="text-sm font-medium text-slate-700 dark:text-slate-300">
                            {submission.student_name}
                        </p>
                        <p className="text-xs text-slate-500">
                            {submission.assignment_title}
                        </p>
                    </div>

                    {submission.submission_file && (
                        <div className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-900 rounded-lg border border-slate-200/60 dark:border-slate-800">
                            <div className="flex items-center gap-2 min-w-0">
                                <FileText className="h-4 w-4 text-slate-400 shrink-0" />
                                <span className="text-xs text-slate-600 dark:text-slate-400 truncate">Attached submission file</span>
                            </div>
                            <Button
                                type="button"
                                variant="outline"
                                size="sm"
                                disabled={isDownloading}
                                onClick={async () => {
                                    setIsDownloading(true);
                                    try {
                                        await downloadSubmissionFile(submission.id, `${submission.student_name}_submission`);
                                    } finally {
                                        setIsDownloading(false);
                                    }
                                }}
                                className="h-8 gap-1.5 text-xs font-medium"
                            >
                                {isDownloading ? (
                                    <>
                                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                        Downloading...
                                    </>
                                ) : (
                                    <>
                                        <Download className="h-3.5 w-3.5" />
                                        Download Submission
                                    </>
                                )}
                            </Button>
                        </div>
                    )}

                    {submission.submission_text && (
                        <div className="space-y-1">
                            <Label>Student's Answer:</Label>
                            <div className="p-3 bg-slate-50 dark:bg-slate-900 rounded border text-sm">
                                {submission.submission_text}
                            </div>
                        </div>
                    )}

                    <div className="space-y-2">
                        <Label htmlFor="score">Score *</Label>
                        <Input
                            id="score"
                            name="score"
                            type="number"
                            step="0.1"
                            placeholder="e.g., 85.5"
                            defaultValue={submission.score || ""}
                            required
                        />
                    </div>

                    <div className="space-y-2">
                        <Label htmlFor="feedback">Feedback</Label>
                        <Textarea
                            id="feedback"
                            name="feedback"
                            placeholder="Provide feedback to the student..."
                            rows={4}
                            defaultValue={submission.feedback || ""}
                        />
                    </div>

                    <div className="flex justify-end gap-2 pt-4">
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isGrading}>
                            {isGrading ? "Saving..." : "Save Grade"}
                        </Button>
                    </div>
                </form>
            </DialogContent>
        </Dialog>
    );
}
