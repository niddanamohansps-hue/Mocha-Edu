"use client";

import { useState } from "react";
import { Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useSections } from "@/hooks/useAcademics";
import { useAdmitCards } from "@/hooks/useExamAllocation";
import { useExaminations } from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import { AdmitCardSheet, AdmitPrintStyles, DateSheetSheet } from "@/components/dashboard/examinations/AdmitCardSheets";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function AdmitCardsPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_examinations")) return <Unauthorized />;
    return <AdmitCardsContent />;
}

function AdmitCardsContent() {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const { data: sections = [] } = useSections();
    const [examination, setExamination] = useState("");
    const [section, setSection] = useState("");
    const { data, isLoading } = useAdmitCards(examination || undefined, section || undefined);

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <AdmitPrintStyles />
            <div className="space-y-2 no-print">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Admit cards and date sheet</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    Print an admit card for every student of a class, with the room and seat from the seating plan, or the
                    date sheet for the class.
                </p>
            </div>
            <div className="flex flex-wrap items-center gap-3 no-print">
                <select className={selectClass} value={examination} onChange={(e) => setExamination(e.target.value)}>
                    <option value="">Choose an examination</option>
                    {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
                </select>
                <select className={selectClass} value={section} onChange={(e) => setSection(e.target.value)}>
                    <option value="">Choose a class and section</option>
                    {sections.map((s) => <option key={s.id} value={s.id}>{s.level_name} - {s.name}</option>)}
                </select>
                <Button variant="outline" disabled={!data} onClick={() => window.print()}>
                    <Printer className="mr-2 h-4 w-4" /> Print
                </Button>
            </div>

            {!examination || !section ? (
                <EmptyState title="Choose an examination and a class" description="The cards will be shown here." />
            ) : isLoading || !data ? (
                <LoadingState />
            ) : data.cards.length === 0 ? (
                <EmptyState title="No students" description="This class has no enrolled students." />
            ) : (
                <Tabs defaultValue="cards">
                    <TabsList className="no-print">
                        <TabsTrigger value="cards">Admit cards ({data.cards.length})</TabsTrigger>
                        <TabsTrigger value="datesheet">Date sheet</TabsTrigger>
                    </TabsList>
                    <TabsContent value="cards" className="space-y-4">
                        {data.cards.map((card) => <AdmitCardSheet key={card.student_id} card={card} data={data} />)}
                    </TabsContent>
                    <TabsContent value="datesheet">
                        <DateSheetSheet data={data} />
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
}
