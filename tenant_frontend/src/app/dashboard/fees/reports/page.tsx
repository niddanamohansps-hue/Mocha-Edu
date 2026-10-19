"use client";

import { useRouter, usePathname, useSearchParams } from "next/navigation";
import { useOutstandingReport } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";


export default function OutstandingReportPage() {
    const { can, isOwner } = usePermissions();
    const { selectedYear } = useAcademicYear();
    const canView = isOwner || can("view_financial_reports");

    const router = useRouter();
    const pathname = usePathname();
    const searchParams = useSearchParams();

    // academicYear is URL state - defaults to global selectedYear
    const academicYear = searchParams.get("academicYear") || selectedYear?.name || "";

    const updateParams = (updates: Record<string, string | null>) => {
        const params = new URLSearchParams(searchParams.toString());
        for (const [key, value] of Object.entries(updates)) {
            if (value === null || value === "") {
                params.delete(key);
            } else {
                params.set(key, value);
            }
        }
        const query = params.toString();
        router.replace(query ? `${pathname}?${query}` : pathname);
    };

    const { data, isLoading, isError, refetch } = useOutstandingReport(academicYear);

    if (!canView) {
        return <Unauthorized />;
    }

    // Backend-computed total over the full filtered report (Phase 9C-F) -
    // NOT derived from `data.results`, which is only the current page.
    const totalOutstanding = parseFloat(data?.total_outstanding_amount ?? "0");

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Outstanding Balances</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Students with an active, unpaid balance.
                </p>
            </div>

            <div className="w-48">
                <label className="text-xs font-medium text-slate-500 mb-1 block">Academic Year</label>
                <div className="flex items-center gap-1.5 h-9 px-3 rounded-md border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 text-sm font-medium text-slate-700 dark:text-slate-300">
                    <span className="truncate">{academicYear || "No year selected"}</span>
                    {selectedYear?.is_current && (
                        <span className="text-[10px] bg-emerald-100 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-300 px-1 py-0.2 rounded font-medium ml-auto">Current</span>
                    )}
                </div>
            </div>

            {isLoading ? (
                <LoadingState className="py-16" />
            ) : isError ? (
                <ErrorState onRetry={refetch} />
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
                        <EmptyState title={`No outstanding balances for ${academicYear}.`} className="py-6 text-slate-500 text-sm" />
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
