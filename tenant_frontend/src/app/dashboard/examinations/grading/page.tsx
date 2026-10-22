"use client";

import { ResponsiveList } from "@/components/common/ResponsiveList";
import { useState } from "react";
import { LoaderCircle, Plus, Trash2 } from "lucide-react";
import { useCreateGradeBoundary, useDeleteGradeBoundary, useGradeBoundaries } from "@/hooks/useExaminations";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Unauthorized from "@/components/Unauthorized";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";


export default function GradingPage() {
    const { can, isOwner } = usePermissions();
    const canManage = isOwner || can("manage_grading");

    const [academicYear, setAcademicYear] = useState("");
    const { data: boundaries, isLoading, isError, refetch } = useGradeBoundaries(academicYear);
    const { mutate: createBoundary, isPending } = useCreateGradeBoundary();
    const { mutate: deleteBoundary } = useDeleteGradeBoundary();

    const [form, setForm] = useState({ min_percentage: "", max_percentage: "", grade_label: "", grade_point: "" });

    const handleCreate = () => {
        createBoundary(
            {
                academic_year: academicYear,
                min_percentage: form.min_percentage,
                max_percentage: form.max_percentage,
                grade_label: form.grade_label,
                grade_point: form.grade_point || null,
            } as any,
            { onSuccess: () => setForm({ min_percentage: "", max_percentage: "", grade_label: "", grade_point: "" }) }
        );
    };

    if (!canManage) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6 max-w-2xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Grading Configuration</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Define grade boundaries per academic year. Ranges may not overlap.
                </p>
            </div>

            <div className="w-40">
                <label htmlFor="f-academic-year" className="text-xs font-medium text-slate-500 mb-1 block">Academic Year</label>
                <Input id="f-academic-year" value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} />
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
                <div>
                    <label htmlFor="f-min" className="text-xs font-medium text-slate-500 mb-1 block">Min %</label>
                    <Input id="f-min" type="number" value={form.min_percentage} onChange={(e) => setForm((f) => ({ ...f, min_percentage: e.target.value }))} />
                </div>
                <div>
                    <label htmlFor="f-max" className="text-xs font-medium text-slate-500 mb-1 block">Max %</label>
                    <Input id="f-max" type="number" value={form.max_percentage} onChange={(e) => setForm((f) => ({ ...f, max_percentage: e.target.value }))} />
                </div>
                <div>
                    <label htmlFor="f-grade" className="text-xs font-medium text-slate-500 mb-1 block">Grade</label>
                    <Input id="f-grade" value={form.grade_label} onChange={(e) => setForm((f) => ({ ...f, grade_label: e.target.value }))} placeholder="A+" />
                </div>
                <div>
                    <label htmlFor="f-grade-point-optional" className="text-xs font-medium text-slate-500 mb-1 block">Grade Point (optional)</label>
                    <Input id="f-grade-point-optional" type="number" value={form.grade_point} onChange={(e) => setForm((f) => ({ ...f, grade_point: e.target.value }))} />
                </div>
            </div>
            <Button onClick={handleCreate} disabled={isPending || !form.min_percentage || !form.max_percentage || !form.grade_label} className="gap-2">
                {isPending && <LoaderCircle className="h-4 w-4 animate-spin" />}
                <Plus className="h-4 w-4" /> Add Boundary
            </Button>

            {isLoading ? (
                <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
            ) : !boundaries || boundaries.length === 0 ? (
                <EmptyState title={`No grade boundaries defined for ${academicYear} yet.`} className="py-6 text-slate-500 text-sm" />
            ) : (
                    <ResponsiveList
                        rows={boundaries}
                        rowKey={(b) => String(b.id)}
                        columns={[
                            { key: "c0", header: "Range", primary: true, cell: (b) => (<>{b.min_percentage}% - {b.max_percentage}%</>), },
                            { key: "c1", header: "Grade", className: "font-bold", cell: (b) => (<>{b.grade_label}</>), },
                            { key: "c2", header: "Point", className: "text-slate-500", cell: (b) => (<>{b.grade_point ?? "—"}</>), },
                        ]}
                        actionsHeader="Remove"
                        actions={(b) => (
                            <Button size="sm" variant="ghost" aria-label={`Remove ${b.grade_label}`} onClick={() => deleteBoundary(b.id)}>
                                <Trash2 className="h-4 w-4 text-red-500" />
                            </Button>
                        )}
                    />
            )}
        </div>
    );
}
