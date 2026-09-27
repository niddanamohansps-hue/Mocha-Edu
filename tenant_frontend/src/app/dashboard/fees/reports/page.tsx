"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useOutstandingReport } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";

function currentYear() {
    return String(new Date().getFullYear());
}

export default function OutstandingReportPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_financial_reports");

    const [academicYear, setAcademicYear] = useState(currentYear());
    const { data, isLoading } = useOutstandingReport(academicYear);

    if (!canView) {
        return <Unauthorized />;
    }

    const totalOutstanding = data?.results.reduce((sum, r) => sum + parseFloat(r.outstanding), 0) ?? 0;

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Outstanding Balances</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Students with an active, unpaid balance.
                </p>
            </div>

            <div className="w-40">
                <label className="text-xs font-medium text-slate-500 mb-1 block">Academic Year</label>
                <Input value={academicYear} onChange={(e) => setAcademicYear(e.target.value)} />
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center py-16"><LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" /></div>
            ) : (
                <>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                        <Card className="border-none shadow-md">
                            <CardContent className="p-4">
                                <p className="text-xs text-slate-500 uppercase font-bold">Students with Dues</p>
                                <p className="text-2xl font-black">{data?.count ?? 0}</p>
                            </CardContent>
                        </Card>
                        <Card className="border-none shadow-md">
                            <CardContent className="p-4">
                                <p className="text-xs text-slate-500 uppercase font-bold">Total Outstanding</p>
                                <p className="text-2xl font-black">{totalOutstanding.toFixed(2)}</p>
                            </CardContent>
                        </Card>
                    </div>

                    {!data || data.results.length === 0 ? (
                        <p className="text-sm text-slate-500 py-6">No outstanding balances for {academicYear}.</p>
                    ) : (
                        <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                            <table className="w-full text-sm">
                                <thead className="bg-slate-50 dark:bg-slate-900">
                                    <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                        <th className="px-4 py-3">Student</th>
                                        <th className="px-4 py-3">Enrollment ID</th>
                                        <th className="px-4 py-3">Fee Head</th>
                                        <th className="px-4 py-3">Due Date</th>
                                        <th className="px-4 py-3">Outstanding</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {data.results.map((row, i) => (
                                        <tr key={i} className="border-t border-slate-100 dark:border-slate-800">
                                            <td className="px-4 py-2 font-medium">{row.full_name}</td>
                                            <td className="px-4 py-2 text-slate-500">{row.enrollment_id}</td>
                                            <td className="px-4 py-2">{row.fee_head}</td>
                                            <td className="px-4 py-2 text-slate-500">{row.due_date || "—"}</td>
                                            <td className="px-4 py-2 font-bold text-red-600">{row.outstanding}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </>
            )}
        </div>
    );
}
