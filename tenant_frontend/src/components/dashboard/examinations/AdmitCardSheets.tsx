"use client";

import { useInstitutionProfile } from "@/hooks/useProfile";
import type { AdmitCard, AdmitCardData } from "@/types/ExamAllocation";

const time = (t: string) => t.slice(0, 5);
const weekday = (date: string) => new Date(`${date}T00:00:00`).toLocaleDateString(undefined, { weekday: "long" });

/** Print rules shared by every page that prints admit cards or a date sheet. */
export function AdmitPrintStyles() {
    return (
        <style jsx global>{`
            @media print {
                @page { size: A4 portrait; margin: 10mm; }
                body { background: white !important; color: black !important; }
                nav, header, aside, .no-print { display: none !important; }
                .admit-card { break-inside: avoid; page-break-inside: avoid; border-color: #334155 !important; }
                .sheet { border: none !important; box-shadow: none !important; }
            }
        `}</style>
    );
}

function SheetHeader({ title }: { title: string }) {
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

export function AdmitCardSheet({ card, data }: { card: AdmitCard; data: AdmitCardData }) {
    return (
        <article className="admit-card rounded-xl border-2 border-slate-300 bg-white p-5 text-slate-900">
            <SheetHeader title={`ADMIT CARD - ${data.examination.name}`} />
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

export function DateSheetSheet({ data }: { data: AdmitCardData }) {
    // Every student of the class sits the same papers, so the first card carries the date sheet.
    const papers = data.cards[0]?.papers ?? [];
    return (
        <article className="sheet rounded-xl border border-slate-200 bg-white p-6 text-slate-900">
            <SheetHeader title={`DATE SHEET - ${data.examination.name} - ${data.class}`} />
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
