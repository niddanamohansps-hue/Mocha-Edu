"use client";

import { useState } from "react";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ExamAdmitPanel } from "@/components/dashboard/examinations/ExamAdmitPanel";
import { useChildAdmitCard, useChildExams, useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";

export default function ParentExamsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_child_results")) return <Unauthorized />;
    return <ParentExamsContent />;
}

function ParentExamsContent() {
    const { data: children } = useLinkedChildren();
    const [childId, setChildId] = useState<string | undefined>(undefined);
    const { data: exams = [], isLoading } = useChildExams(childId);
    const [chosen, setChosen] = useState("");
    const active = chosen || (exams.length === 1 ? exams[0].id : "");
    const { data: card, isLoading: loadingCard } = useChildAdmitCard(childId, active || undefined);

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="space-y-2 no-print">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Exams and admit card</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Your child&apos;s date sheet and admit card, once the school has announced them.
                </p>
            </div>
            <div className="no-print">
                <ChildSwitcher
                    childOptions={children || []}
                    selectedId={childId}
                    onChange={(id) => { setChildId(id); setChosen(""); }}
                />
            </div>
            {!childId ? (
                <EmptyState
                    title={children && children.length === 0 ? "No children are linked to your account yet." : "Select a child to see their exams."}
                    className="py-16 text-slate-500 text-sm"
                />
            ) : (
                <ExamAdmitPanel exams={exams} loadingExams={isLoading} active={active} card={card} loadingCard={loadingCard} onChoose={setChosen} />
            )}
        </div>
    );
}
