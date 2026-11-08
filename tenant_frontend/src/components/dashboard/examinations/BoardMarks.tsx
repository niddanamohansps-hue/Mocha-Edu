"use client";

import React from "react";
import type { ReportCard, ReportCardExamination } from "@/types/Examinations";

export type CardStyle = "standard" | "cbse" | "state";

/** The usual division bands used on state-board marksheets. */
export function division(percentage: number, isPass: boolean): string {
    if (!isPass) return "Not passed";
    if (percentage >= 75) return "Distinction";
    if (percentage >= 60) return "First division";
    if (percentage >= 50) return "Second division";
    return "Third division";
}

const marks = (value: number | null, absent: boolean) =>
    absent ? <span className="font-semibold text-red-600">Ab</span> : value === null ? "-" : value;

function Components({ sub }: { sub: ReportCardExamination["subject_breakdown"][number] }) {
    if (!sub.components || sub.components.length === 0) return null;
    return (
        <span className="ml-2 text-[11px] font-normal text-slate-600">
            {sub.components.map((c) => `${c.code} ${c.is_absent ? "Ab" : (c.marks_obtained ?? "-")}/${c.max_marks}`).join("  ")}
        </span>
    );
}

function Cbse({ exam, rank }: { exam: ReportCardExamination; rank?: { rank: number; of: number } }) {
    return (
        <div className="overflow-hidden rounded border border-slate-400">
            <div className="flex items-center justify-between border-b border-slate-400 bg-slate-100 px-3 py-1.5">
                <h3 className="text-sm font-bold uppercase tracking-wide">{exam.examination_name}</h3>
                <span className="text-xs font-semibold">
                    Part 1: Scholastic areas{rank ? `, rank ${rank.rank} of ${rank.of}` : ""}
                </span>
            </div>
            <table className="w-full text-xs">
                <thead className="border-b border-slate-300 text-left uppercase text-slate-600">
                    <tr>
                        <th className="px-3 py-1.5">Subject</th>
                        <th className="px-3 py-1.5 text-right">Max marks</th>
                        <th className="px-3 py-1.5 text-right">Marks obtained</th>
                        <th className="px-3 py-1.5 text-center">Grade</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                    {exam.subject_breakdown.map((s, i) => (
                        <tr key={s.subject || i}>
                            <td className="px-3 py-1.5 font-semibold">{s.subject_name}<Components sub={s} /></td>
                            <td className="px-3 py-1.5 text-right">{s.max_marks}</td>
                            <td className="px-3 py-1.5 text-right">{marks(s.marks_obtained, s.is_absent)}</td>
                            <td className="px-3 py-1.5 text-center font-bold">{s.grade || "-"}</td>
                        </tr>
                    ))}
                </tbody>
                <tfoot className="border-t-2 border-slate-400 bg-slate-50 font-bold">
                    <tr>
                        <td className="px-3 py-1.5 uppercase">Total</td>
                        <td className="px-3 py-1.5 text-right">{exam.total_max_marks}</td>
                        <td className="px-3 py-1.5 text-right">{exam.total_marks_obtained}</td>
                        <td className="px-3 py-1.5 text-center">{exam.overall_grade || "-"}</td>
                    </tr>
                    <tr>
                        <td colSpan={4} className="px-3 py-1.5 text-right font-semibold">
                            Percentage {exam.percentage}%. Result: {exam.is_pass ? "Pass" : "Needs improvement"}
                        </td>
                    </tr>
                </tfoot>
            </table>
        </div>
    );
}

function State({ exam, rank }: { exam: ReportCardExamination; rank?: { rank: number; of: number } }) {
    return (
        <div className="overflow-hidden rounded border border-slate-400">
            <div className="border-b border-slate-400 bg-slate-100 px-3 py-1.5">
                <h3 className="text-sm font-bold uppercase tracking-wide">{exam.examination_name}</h3>
            </div>
            <table className="w-full text-xs">
                <thead className="border-b border-slate-300 text-left uppercase text-slate-600">
                    <tr>
                        <th className="px-3 py-1.5">Sl.</th>
                        <th className="px-3 py-1.5">Subject</th>
                        <th className="px-3 py-1.5 text-right">Maximum</th>
                        <th className="px-3 py-1.5 text-right">Obtained</th>
                        <th className="px-3 py-1.5 text-center">Result</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                    {exam.subject_breakdown.map((s, i) => (
                        <tr key={s.subject || i}>
                            <td className="px-3 py-1.5 text-slate-500">{i + 1}</td>
                            <td className="px-3 py-1.5 font-semibold">{s.subject_name}<Components sub={s} /></td>
                            <td className="px-3 py-1.5 text-right">{s.max_marks}</td>
                            <td className="px-3 py-1.5 text-right">{marks(s.marks_obtained, s.is_absent)}</td>
                            <td className="px-3 py-1.5 text-center">{s.is_pass ? "P" : "F"}</td>
                        </tr>
                    ))}
                </tbody>
                <tfoot className="border-t-2 border-slate-400 bg-slate-50 font-bold">
                    <tr>
                        <td colSpan={2} className="px-3 py-1.5 uppercase">Total</td>
                        <td className="px-3 py-1.5 text-right">{exam.total_max_marks}</td>
                        <td className="px-3 py-1.5 text-right">{exam.total_marks_obtained}</td>
                        <td className="px-3 py-1.5 text-center">{exam.is_pass ? "Pass" : "Fail"}</td>
                    </tr>
                    <tr>
                        <td colSpan={5} className="px-3 py-1.5 text-right font-semibold">
                            Percentage {exam.percentage}%. {division(exam.percentage, exam.is_pass)}
                            {rank ? `. Rank ${rank.rank} of ${rank.of}` : ""}
                        </td>
                    </tr>
                </tfoot>
            </table>
        </div>
    );
}

export function BoardMarks({ reportCard, style }: { reportCard: ReportCard; style: Exclude<CardStyle, "standard"> }) {
    return (
        <div className="space-y-5">
            {reportCard.examinations.map((exam, i) => {
                const rank = reportCard.ranks?.[exam.examination];
                return style === "cbse"
                    ? <Cbse key={exam.id || i} exam={exam} rank={rank} />
                    : <State key={exam.id || i} exam={exam} rank={rank} />;
            })}
        </div>
    );
}
