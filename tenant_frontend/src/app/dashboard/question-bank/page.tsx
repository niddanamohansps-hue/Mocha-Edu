"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/feedback/ErrorState";
import { QuestionEditor } from "@/components/dashboard/question-bank/QuestionEditor";
import { QuestionList } from "@/components/dashboard/question-bank/QuestionList";
import { PageHeader, useCanUseBank } from "@/components/dashboard/question-bank/shared";
import { useMyScope } from "@/hooks/useQuestionBank";
import { Question } from "@/types/QuestionBank";

export default function QuestionBankPage() {
    const canUse = useCanUseBank();
    const scope = useMyScope();
    const [editing, setEditing] = useState<Question | null | undefined>(undefined);
    const canWrite = (scope.data?.can_write ?? []).length > 0;

    if (!canUse) return <ErrorState message="You do not have permission to use the question bank." />;

    return (
        <div className="space-y-6">
            <PageHeader
                title="Question bank"
                description="Reusable questions for your subjects. A teacher writes a draft and submits it; a reviewer for the subject approves it before it can be used in a paper."
                actions={canWrite && <Button onClick={() => setEditing(null)}>New question</Button>}
            />
            <QuestionList
                emptyTitle="No questions yet."
                emptyHint={canWrite ? "Write the first question for a subject you teach." : "Approved questions of your subjects will appear here."}
                action={canWrite ? <Button onClick={() => setEditing(null)}>Write the first question</Button> : undefined}
            />
            <QuestionEditor question={editing} onClose={() => setEditing(undefined)} />
        </div>
    );
}
