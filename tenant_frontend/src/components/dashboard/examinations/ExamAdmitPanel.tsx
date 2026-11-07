"use client";

import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { AdmitCardSheet, AdmitPrintStyles, DateSheetSheet } from "@/components/dashboard/examinations/AdmitCardSheets";
import type { AdmitCardData, FamilyExam } from "@/types/ExamAllocation";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

/**
 * Lets a student, or a parent, pick one of the examinations the school has announced and open or print the admit card
 * and the date sheet. The page that owns this panel holds the choice and fetches the card for it; ``active`` is the
 * examination in use (with a single announced examination the page opens it without asking).
 */
export function ExamAdmitPanel({
    exams,
    loadingExams,
    active,
    card,
    loadingCard,
    onChoose,
}: {
    exams: FamilyExam[];
    loadingExams: boolean;
    active: string;
    card: AdmitCardData | undefined;
    loadingCard: boolean;
    onChoose: (examination: string) => void;
}) {
    if (loadingExams) return <LoadingState />;
    if (exams.length === 0) {
        return (
            <EmptyState
                title="No date sheet yet"
                description="When the school announces the date sheet for an examination, the admit card appears here."
            />
        );
    }
    return (
        <div className="space-y-4">
            <AdmitPrintStyles />
            <div className="flex flex-wrap items-center gap-3 no-print">
                {exams.length > 1 && (
                    <select className={selectClass} value={active} onChange={(e) => onChoose(e.target.value)}>
                        <option value="">Choose an examination</option>
                        {exams.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
                    </select>
                )}
                <Button variant="outline" disabled={!card} onClick={() => window.print()}>
                    <Printer className="mr-2 h-4 w-4" /> Print
                </Button>
            </div>
            {!active ? (
                <EmptyState title="Choose an examination" description="Its admit card will be shown here." />
            ) : loadingCard || !card ? (
                <LoadingState />
            ) : (
                <Tabs defaultValue="card">
                    <TabsList className="no-print">
                        <TabsTrigger value="card">Admit card</TabsTrigger>
                        <TabsTrigger value="datesheet">Date sheet</TabsTrigger>
                    </TabsList>
                    <TabsContent value="card">
                        {card.cards.map((c) => <AdmitCardSheet key={c.student_id} card={c} data={card} />)}
                    </TabsContent>
                    <TabsContent value="datesheet">
                        <DateSheetSheet data={card} />
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
}
