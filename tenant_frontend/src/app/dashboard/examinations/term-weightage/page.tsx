"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { useAcademicLevels } from "@/hooks/useAcademics";
import {
    useCreateTermWeightage,
    useDeleteTermWeightage,
    useExaminations,
    useTermWeightages,
} from "@/hooks/useExaminations";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { usePermissions } from "@/providers/PermissionProvider";

const selectClass =
    "h-10 rounded-md border border-slate-200 bg-white px-3 text-sm dark:border-slate-800 dark:bg-slate-950";

export default function TermWeightagePage() {
    const { can, isOwner } = usePermissions();
    if (!isOwner && !can("view_examinations")) return <Unauthorized />;
    return <TermWeightageContent canEdit={isOwner || can("manage_examinations")} />;
}

function TermWeightageContent({ canEdit }: { canEdit: boolean }) {
    const { selectedYear } = useAcademicYear();
    const year = selectedYear?.name || "";
    const { data: levels = [] } = useAcademicLevels();
    const { data: examinations = [] } = useExaminations(year || undefined);
    const [level, setLevel] = useState("");
    const { data: rows = [], isLoading } = useTermWeightages(year || undefined, level || undefined);
    const create = useCreateTermWeightage();
    const remove = useDeleteTermWeightage();

    const [examination, setExamination] = useState("");
    const [percent, setPercent] = useState("");

    const total = rows.reduce((sum, row) => sum + Number(row.weightage_percentage), 0);
    const used = new Set(rows.map((row) => row.examination));
    const available = examinations.filter((exam) => !used.has(exam.id));

    return (
        <div className="max-w-3xl mx-auto space-y-6">
            <div className="space-y-2">
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">Term weightage</h1>
                <p className="text-slate-500 dark:text-slate-400">
                    How much each examination counts towards a student&apos;s final result for {year || "the year"}, for example
                    Periodic Test 10%, Mid-Term 30%, Final 60%. Set it per class. The weights should add up to 100%.
                </p>
            </div>

            <select className={selectClass} value={level} onChange={(e) => setLevel(e.target.value)}>
                <option value="">Choose a class</option>
                {levels.map((l) => (
                    <option key={l.id} value={l.id}>{l.name}</option>
                ))}
            </select>

            {!level ? (
                <EmptyState title="Choose a class" description="Its examination weights will be shown here." />
            ) : isLoading ? (
                <LoadingState />
            ) : (
                <section className="space-y-4">
                    {rows.length === 0 ? (
                        <p className="text-sm text-slate-500">No weights set for this class yet.</p>
                    ) : (
                        <div className="space-y-2">
                            {rows.map((row) => (
                                <div key={row.id} className="flex items-center justify-between rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
                                    <span className="font-medium">{row.examination_name ?? row.examination}</span>
                                    <span className="flex items-center gap-3">
                                        {Number(row.weightage_percentage)}%
                                        {canEdit && (
                                            <Button size="icon" variant="ghost" disabled={remove.isPending} onClick={() => remove.mutate(row.id)}>
                                                <Trash2 className="h-4 w-4 text-red-500" />
                                            </Button>
                                        )}
                                    </span>
                                </div>
                            ))}
                            <p className={`text-sm font-medium ${total === 100 ? "text-emerald-600" : "text-amber-600"}`}>
                                Total: {total}%
                                {total === 100 ? "" : " (the combined result in the report card needs this to be 100%)"}
                            </p>
                        </div>
                    )}

                    {canEdit && (
                        <div className="flex flex-wrap items-end gap-3 border-t border-slate-200 pt-4 dark:border-slate-800">
                            <div className="grid gap-1.5">
                                <Label>Examination</Label>
                                <select className={selectClass} value={examination} onChange={(e) => setExamination(e.target.value)}>
                                    <option value="">Choose</option>
                                    {available.map((exam) => (
                                        <option key={exam.id} value={exam.id}>{exam.name}</option>
                                    ))}
                                </select>
                            </div>
                            <div className="grid gap-1.5">
                                <Label>Weight (%)</Label>
                                <Input className="w-28" type="number" min={1} max={100} value={percent} onChange={(e) => setPercent(e.target.value)} />
                            </div>
                            <Button
                                disabled={create.isPending || !examination || !percent}
                                onClick={() =>
                                    create.mutate(
                                        { academic_year: year, level, examination, weightage_percentage: percent },
                                        { onSuccess: () => { setExamination(""); setPercent(""); } },
                                    )
                                }
                            >
                                Add
                            </Button>
                        </div>
                    )}
                </section>
            )}
        </div>
    );
}
