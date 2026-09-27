"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useChildReportCard, useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";

export default function ParentPortalResultsPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_child_results");

    const { data: children } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);

    const { data: reportCard, isLoading } = useChildReportCard(selectedChildId);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Examination Results</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Published results and report card for your selected child
                </p>
            </div>

            <ChildSwitcher
                childOptions={children || []}
                selectedId={selectedChildId}
                onChange={setSelectedChildId}
            />

            {!selectedChildId ? (
                <div className="py-16 text-center text-sm text-slate-500">
                    {children && children.length === 0
                        ? "No children are linked to your account yet."
                        : "Select a child to view their results."}
                </div>
            ) : isLoading ? (
                <div className="flex items-center justify-center py-20">
                    <LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" />
                </div>
            ) : !reportCard || reportCard.examinations.length === 0 ? (
                <div className="py-16 text-center text-sm text-slate-500">No published results yet.</div>
            ) : (
                <div className="space-y-6 print:space-y-4">
                    <div className="text-sm text-slate-500">
                        <span className="font-semibold text-slate-900 dark:text-white">
                            {reportCard.student.full_name}
                        </span>{" "}
                        · {reportCard.student.enrollment_id}
                    </div>
                    {reportCard.examinations.map((result) => (
                        <Card key={result.id} className="border-none shadow-md">
                            <CardContent className="p-6 space-y-4">
                                <div className="flex justify-between items-start">
                                    <div>
                                        <p className="text-xs text-slate-500 uppercase font-bold">
                                            {result.examination_name}
                                        </p>
                                        <p className="text-2xl font-black">
                                            {result.percentage}% - {result.overall_grade || "—"}
                                        </p>
                                    </div>
                                    <span
                                        className={`text-sm font-bold px-3 py-1 rounded-full ${
                                            result.is_pass
                                                ? "bg-emerald-100 text-emerald-700"
                                                : "bg-red-100 text-red-700"
                                        }`}
                                    >
                                        {result.is_pass ? "PASS" : "FAIL"}
                                    </span>
                                </div>
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                            <th className="py-2">Subject</th>
                                            <th className="py-2">Marks</th>
                                            <th className="py-2">%</th>
                                            <th className="py-2">Grade</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {result.subject_breakdown.map((sub) => (
                                            <tr key={sub.subject} className="border-t border-slate-100 dark:border-slate-800">
                                                <td className="py-2 font-medium">{sub.subject_name}</td>
                                                <td className="py-2">
                                                    {sub.is_absent
                                                        ? "Absent"
                                                        : sub.marks_obtained === null
                                                        ? "—"
                                                        : `${sub.marks_obtained}/${sub.max_marks}`}
                                                </td>
                                                <td className="py-2">{sub.percentage ?? "—"}</td>
                                                <td className="py-2">{sub.grade ?? "—"}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </CardContent>
                        </Card>
                    ))}
                </div>
            )}
        </div>
    );
}
