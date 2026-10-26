"use client";

import { ErrorState } from "@/components/feedback/ErrorState";
import { QuestionList } from "@/components/dashboard/question-bank/QuestionList";
import { PageHeader } from "@/components/dashboard/question-bank/shared";
import { usePermissions } from "@/providers/PermissionProvider";

export default function ReviewQueuePage() {
    const { can } = usePermissions();
    if (!can("review_questions")) return <ErrorState message="You do not have permission to review questions." />;
    return (
        <div className="space-y-6">
            <PageHeader
                title="Questions to review"
                description="Submitted questions for the subjects you review. Your own questions are never in this list: someone else reviews them."
            />
            <QuestionList
                reviewQueue
                emptyTitle="Nothing is waiting for your review."
                emptyHint="When a teacher submits a question for one of your subjects, it appears here."
            />
        </div>
    );
}
