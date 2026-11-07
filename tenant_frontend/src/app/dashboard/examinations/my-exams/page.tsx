"use client";

import { useState } from "react";
import Unauthorized from "@/components/Unauthorized";
import { ExamAdmitPanel } from "@/components/dashboard/examinations/ExamAdmitPanel";
import { useMyAdmitCard, useMyExams } from "@/hooks/useExamAllocation";
import { usePermissions } from "@/providers/PermissionProvider";

export default function MyExamsPage() {
    const { activeRole, isOwner } = usePermissions();
    if (activeRole !== "student" && !isOwner) return <Unauthorized />;
    return <MyExamsContent />;
}

function MyExamsContent() {
    const { data: exams = [], isLoading } = useMyExams();
    const [chosen, setChosen] = useState("");
    const active = chosen || (exams.length === 1 ? exams[0].id : "");
    const { data: card, isLoading: loadingCard } = useMyAdmitCard(active || undefined);

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="space-y-2 no-print">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">My exams</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Your admit card and date sheet, once the school has announced them. Print the admit card and bring it to every paper.
                </p>
            </div>
            <ExamAdmitPanel exams={exams} loadingExams={isLoading} active={active} card={card} loadingCard={loadingCard} onChoose={setChosen} />
        </div>
    );
}
