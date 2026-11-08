"use client";

import { useState } from "react";
import Link from "next/link";
import { Download } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useExamTypes, useExaminations } from "@/hooks/useExaminations";
import { useStartSupplementary, useSupplementaryFor } from "@/hooks/useExamAllocation";
import { downloadCsv } from "@/lib/csv";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function SupplementaryPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_examinations")) return <Unauthorized />;
    return <SupplementaryContent canManage={isOwner || can("manage_examinations")} />;
}

function SupplementaryContent({ canManage }: { canManage: boolean }) {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const { data: types = [] } = useExamTypes();
    const [originalId, setOriginalId] = useState("");
    const original = examinations.find((e) => e.id === originalId);
    const { data: found, isLoading } = useSupplementaryFor(originalId || undefined);
    const start = useStartSupplementary();

    const [name, setName] = useState("");
    const [typeId, setTypeId] = useState("");
    const [from, setFrom] = useState("");
    const [to, setTo] = useState("");

    // Only published examinations that are not themselves re-sits can have a supplementary examination.
    const eligible = examinations.filter((e) => e.is_published && !e.supplementary_of);

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Supplementary exams</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    A re-sit for students who failed or missed a subject. Starting one lists, from the published results, who may
                    re-sit what. You then add the papers on the Examinations page and enter marks as usual; each re-sit paper
                    accepts marks only for the students entitled to it. The original result is never changed, and the re-sit
                    result appears beside it on the report card.
                </p>
            </div>

            <select className={selectClass} value={originalId} onChange={(e) => setOriginalId(e.target.value)}>
                <option value="">Choose a published examination</option>
                {eligible.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
            </select>

            {!originalId ? (
                <EmptyState title="Choose an examination" description="Only examinations whose results are published can have a re-sit." />
            ) : isLoading ? (
                <LoadingState />
            ) : !found ? (
                canManage ? (
                    <section className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
                        <h2 className="text-lg font-semibold">Start a supplementary examination for {original?.name}</h2>
                        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                            <div className="grid gap-1.5">
                                <Label>Name</Label>
                                <Input value={name} placeholder={`Supplementary ${original?.name ?? ""}`} onChange={(e) => setName(e.target.value)} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Exam type</Label>
                                <select className={selectClass} value={typeId} onChange={(e) => setTypeId(e.target.value)}>
                                    <option value="">Choose</option>
                                    {types.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                                </select>
                            </div>
                            <div className="grid gap-1.5">
                                <Label>From</Label>
                                <Input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
                            </div>
                            <div className="grid gap-1.5">
                                <Label>To</Label>
                                <Input type="date" value={to} onChange={(e) => setTo(e.target.value)} />
                            </div>
                        </div>
                        <Button
                            disabled={start.isPending || !typeId || !from || !to}
                            onClick={() => start.mutate({ original: originalId, name: name.trim() || `Supplementary ${original?.name ?? ""}`, exam_type: typeId, start_date: from, end_date: to })}
                        >
                            Start and list who re-sits
                        </Button>
                    </section>
                ) : (
                    <EmptyState title="No supplementary examination yet" description="Someone who manages examinations can start one." />
                )
            ) : (
                <section className="space-y-5">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                        <h2 className="text-xl font-semibold">{found.examination.name}</h2>
                        <div className="flex gap-2">
                            <Button asChild variant="outline" size="sm">
                                <Link href="/dashboard/examinations">Add papers on the Examinations page</Link>
                            </Button>
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={() => downloadCsv("supplementary-candidates.csv", [
                                    ["Student", "Enrollment no.", "Class", "Subject", "Why", "Original %", "Re-sit %", "Outcome"],
                                    ...found.rows.map((r) => [
                                        r.name, r.enrollment_id, r.class, r.subject, r.reason, r.original_percentage, r.resit_percentage,
                                        r.cleared === null ? "Waiting" : r.cleared ? "Cleared" : "Not cleared",
                                    ]),
                                ])}
                            >
                                <Download className="mr-2 h-4 w-4" /> Export CSV
                            </Button>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                        <Tile label="Papers to re-sit" value={found.summary.candidates} />
                        <Tile label="Students" value={found.summary.students} />
                        <Tile label="Cleared" value={found.summary.cleared} tone="good" />
                        <Tile label="Not cleared" value={found.summary.not_cleared} tone={found.summary.not_cleared ? "bad" : undefined} />
                        <Tile label="Waiting" value={found.summary.waiting} />
                    </div>
                    <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                        <table className="w-full text-sm">
                            <thead className="bg-slate-50 dark:bg-slate-900">
                                <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                                    <th className="px-4 py-3">Student</th>
                                    <th className="px-4 py-3">Class</th>
                                    <th className="px-4 py-3">Subject</th>
                                    <th className="px-4 py-3">Why</th>
                                    <th className="px-4 py-3">Original</th>
                                    <th className="px-4 py-3">Re-sit</th>
                                    <th className="px-4 py-3">Outcome</th>
                                </tr>
                            </thead>
                            <tbody>
                                {found.rows.map((row) => (
                                    <tr key={`${row.student_id}-${row.subject_id}`} className="border-t border-slate-100 dark:border-slate-800">
                                        <td className="px-4 py-2"><span className="font-medium">{row.name}</span> <span className="text-xs text-slate-400">{row.enrollment_id}</span></td>
                                        <td className="px-4 py-2">{row.class}</td>
                                        <td className="px-4 py-2">{row.subject}</td>
                                        <td className="px-4 py-2">{row.reason === "absent" ? "Absent" : "Failed"}</td>
                                        <td className="px-4 py-2">{row.original_percentage !== null ? `${Number(row.original_percentage)}%` : "-"}</td>
                                        <td className="px-4 py-2">{row.resit_percentage !== null ? `${row.resit_percentage}%` : "-"}</td>
                                        <td className="px-4 py-2">
                                            {row.cleared === null ? <Badge variant="outline">Waiting</Badge> : row.cleared ? <Badge variant="outline">Cleared</Badge> : <Badge variant="destructive">Not cleared</Badge>}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </section>
            )}
        </div>
    );
}

function Tile({ label, value, tone }: { label: string; value: number; tone?: "good" | "bad" }) {
    const color = tone === "good" ? "text-emerald-600" : tone === "bad" ? "text-red-600" : "text-slate-900 dark:text-white";
    return (
        <div className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-slate-500">{label}</div>
        </div>
    );
}
