"use client";

import { useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useMarksProgress, useRemindTeachers, useSetMarksDueDate } from "@/hooks/useExamAllocation";
import { useExaminations } from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";
import type { MarksProgressRow } from "@/types/ExamAllocation";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

const STATE_LABEL: Record<MarksProgressRow["state"], string> = {
    complete: "Complete",
    in_progress: "In progress",
    not_started: "Not started",
};

export default function MarksProgressPage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_examinations")) return <Unauthorized />;
    return <MarksProgressContent canManage={isOwner || can("manage_examinations")} />;
}

function MarksProgressContent({ canManage }: { canManage: boolean }) {
    const { selectedYear } = useAcademicYear();
    const { data: examinations = [] } = useExaminations(selectedYear?.name || undefined);
    const [examinationId, setExaminationId] = useState("");
    const examination = examinations.find((e) => e.id === examinationId);
    const { data, isLoading } = useMarksProgress(examinationId || undefined);
    const remind = useRemindTeachers();
    const setDue = useSetMarksDueDate();
    const [dueEdit, setDueEdit] = useState<string | null>(null);
    const due = dueEdit ?? examination?.marks_due_date ?? "";

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Marks entry progress</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    See which papers have their marks entered, who is responsible, and which are late. Teachers are also
                    reminded automatically each morning once the due date is a day away.
                </p>
            </div>

            <select className={selectClass} value={examinationId} onChange={(e) => { setExaminationId(e.target.value); setDueEdit(null); }}>
                <option value="">Choose an examination</option>
                {examinations.map((exam) => <option key={exam.id} value={exam.id}>{exam.name}</option>)}
            </select>

            {!examinationId ? (
                <EmptyState title="Choose an examination" description="Its papers will be listed here." />
            ) : isLoading || !data || !examination ? (
                <LoadingState />
            ) : (
                <>
                    <div className="flex flex-wrap items-end gap-3">
                        <div className="grid gap-1.5">
                            <Label>Marks due by</Label>
                            <Input type="date" className="w-44" disabled={!canManage || examination.is_published} value={due} onChange={(e) => setDueEdit(e.target.value)} />
                        </div>
                        {canManage && !examination.is_published && (
                            <>
                                <Button
                                    variant="outline"
                                    disabled={setDue.isPending || dueEdit === null}
                                    onClick={() => setDue.mutate({ examination: examinationId, date: dueEdit || null }, { onSuccess: () => setDueEdit(null) })}
                                >
                                    Save due date
                                </Button>
                                <Button disabled={remind.isPending || data.summary.complete === data.summary.papers} onClick={() => remind.mutate(examinationId)}>
                                    Remind teachers now
                                </Button>
                            </>
                        )}
                    </div>

                    <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                        <Tile label="Papers" value={data.summary.papers} />
                        <Tile label="Complete" value={data.summary.complete} tone="good" />
                        <Tile label="In progress" value={data.summary.in_progress} />
                        <Tile label="Not started" value={data.summary.not_started} />
                        <Tile label="Late" value={data.summary.overdue} tone={data.summary.overdue ? "bad" : undefined} />
                    </div>

                    {data.rows.length === 0 ? (
                        <EmptyState title="No papers" description="Add papers to this examination first." />
                    ) : (
                        <div className="overflow-x-auto rounded-2xl border border-slate-200 dark:border-slate-800">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 dark:bg-slate-900">
                                    <tr className="text-left text-xs font-semibold uppercase text-slate-500">
                                        <th className="px-4 py-3">Paper</th>
                                        <th className="px-4 py-3">Teacher</th>
                                        <th className="px-4 py-3">Entered</th>
                                        <th className="px-4 py-3">Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.rows.map((row) => (
                                        <tr key={row.schedule} className="border-t border-slate-100 dark:border-slate-800">
                                            <td className="px-4 py-2">
                                                <span className="font-medium">{row.subject}</span>{" "}
                                                <span className="text-slate-500">{row.class}</span>
                                                <span className="block text-xs text-slate-400">{row.date}</span>
                                            </td>
                                            <td className="px-4 py-2">
                                                {row.teachers.length ? row.teachers.join(", ") : <span className="text-amber-600">Not assigned</span>}
                                            </td>
                                            <td className="px-4 py-2">
                                                <div className="flex items-center gap-2">
                                                    <div className="h-2 w-24 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                                                        <div
                                                            className="h-full bg-emerald-500"
                                                            style={{ width: `${row.expected ? Math.round((row.entered / row.expected) * 100) : 0}%` }}
                                                        />
                                                    </div>
                                                    {row.entered}/{row.expected}
                                                </div>
                                            </td>
                                            <td className="px-4 py-2">
                                                <span className="flex flex-wrap items-center gap-2">
                                                    <Badge variant="outline">{STATE_LABEL[row.state]}</Badge>
                                                    {row.locked && <Badge variant="outline">Locked</Badge>}
                                                    {row.overdue && <Badge variant="destructive">Late</Badge>}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                    <p className="text-xs text-slate-500">
                        A mark counts as entered once it has a score, or the student is recorded as absent, on medical leave,
                        in malpractice or exempt.{" "}
                        <Link href="/dashboard/examinations/marks" className="underline">Go to marks entry</Link>
                    </p>
                </>
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
