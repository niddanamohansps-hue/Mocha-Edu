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
import { useInstitutionProfile } from "@/hooks/useProfile";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { AdmitCard, AdmitCardData } from "@/types/ExamAllocation";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";
const time = (t: string) => t.slice(0, 5);
const weekday = (date: string) => new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { weekday: "long" });

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
            <style jsx global>{`
                @media print {
                    @page { size: A4 portrait; margin: 10mm; }
                    body { background: white !important; color: black !important; }
                    nav, header, aside, .no-print { display: none !important; }
                    .admit-card { break-inside: avoid; page-break-inside: avoid; border-color: #334155 !important; }
                    .sheet { border: none !important; box-shadow: none !important; }
                }
            `}</style>
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
                        {data.cards.map((card) => <Card key={card.student_id} card={card} data={data} />)}
                    </TabsContent>
                    <TabsContent value="datesheet">
                        <DateSheet data={data} />
                    </TabsContent>
                </Tabs>
            )}
        </div>
    );
}

function Header({ title }: { title: string }) {
    const { data: institution } = useInstitutionProfile();
    return (
        <div className="mb-3 border-b-2 border-slate-900 pb-2 text-center">
            {institution?.logo && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={institution.logo} alt={institution.name} className="mx-auto mb-1 h-12 w-auto object-contain" />
            )}
            <h2 className="text-lg font-bold uppercase tracking-wide">{institution?.name || "School"}</h2>
            <p className="text-sm font-semibold">{title}</p>
        </div>
    );
}

function Card({ card, data }: { card: AdmitCard; data: AdmitCardData }) {
    return (
        <article className="admit-card rounded-xl border-2 border-slate-300 bg-white p-5 text-slate-900">
            <Header title={`ADMIT CARD - ${data.examination.name}`} />
            <div className="mb-3 grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
                <p><span className="text-slate-500">Name: </span><strong>{card.name}</strong></p>
                <p><span className="text-slate-500">Class: </span><strong>{card.class}</strong></p>
                <p><span className="text-slate-500">Enrollment no.: </span><strong>{card.enrollment_id}</strong></p>
            </div>
            <table className="w-full border-collapse text-sm">
                <thead>
                    <tr className="border-b-2 border-slate-900 text-left">
                        <th className="py-1 pr-2">Date</th>
                        <th className="py-1 pr-2">Time</th>
                        <th className="py-1 pr-2">Subject</th>
                        <th className="py-1 pr-2">Room</th>
                        <th className="py-1">Seat</th>
                    </tr>
                </thead>
                <tbody>
                    {card.papers.map((paper, i) => (
                        <tr key={i} className="border-b border-slate-300">
                            <td className="py-1 pr-2">{paper.date}</td>
                            <td className="py-1 pr-2">{time(paper.start_time)} - {time(paper.end_time)}</td>
                            <td className="py-1 pr-2">{paper.subject}</td>
                            <td className="py-1 pr-2">{paper.room || "-"}</td>
                            <td className="py-1">{paper.seat ?? "-"}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
            <div className="mt-6 flex justify-between text-xs">
                <span>Bring this card to every paper.</span>
                <span className="border-t border-slate-900 pt-1">Principal / Class teacher</span>
            </div>
        </article>
    );
}

function DateSheet({ data }: { data: AdmitCardData }) {
    // Every student of the class sits the same papers, so the first card carries the date sheet.
    const papers = data.cards[0]?.papers ?? [];
    return (
        <article className="sheet rounded-xl border border-slate-200 bg-white p-6 text-slate-900">
            <Header title={`DATE SHEET - ${data.examination.name} - ${data.class}`} />
            <table className="w-full border-collapse text-sm">
                <thead>
                    <tr className="border-b-2 border-slate-900 text-left">
                        <th className="py-1 pr-2">Date</th>
                        <th className="py-1 pr-2">Day</th>
                        <th className="py-1 pr-2">Time</th>
                        <th className="py-1">Subject</th>
                    </tr>
                </thead>
                <tbody>
                    {papers.map((paper, i) => (
                        <tr key={i} className="border-b border-slate-300">
                            <td className="py-1.5 pr-2">{paper.date}</td>
                            <td className="py-1.5 pr-2">{weekday(paper.date)}</td>
                            <td className="py-1.5 pr-2">{time(paper.start_time)} - {time(paper.end_time)}</td>
                            <td className="py-1.5">{paper.subject}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </article>
    );
}
