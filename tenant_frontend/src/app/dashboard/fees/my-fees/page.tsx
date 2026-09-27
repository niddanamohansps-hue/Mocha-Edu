"use client";

import { LoaderCircle } from "lucide-react";
import { useMe } from "@/hooks/useAuth";
import { useStudentFees, useStudentPayments } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";

export default function MyFeesPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_own_fees");

    const { data: user } = useMe();
    const studentId = user?.profile?.student_id ?? undefined;

    const { data: feesData, isLoading: loadingFees } = useStudentFees(studentId);
    const { data: payments, isLoading: loadingPayments } = useStudentPayments(studentId);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">My Fees</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Your fees, balance, and payment history.
                </p>
            </div>

            {!studentId ? (
                <p className="text-sm text-slate-500 py-6">No student record linked to your account yet.</p>
            ) : loadingFees ? (
                <div className="flex items-center justify-center py-16"><LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" /></div>
            ) : feesData ? (
                <div className="space-y-8">
                    <Card className="border-none shadow-md">
                        <CardContent className="p-6">
                            <p className="text-xs text-slate-500 uppercase font-bold">Total Outstanding</p>
                            <p className="text-3xl font-black">{feesData.total_outstanding}</p>
                        </CardContent>
                    </Card>

                    <div className="space-y-3">
                        <h2 className="text-lg font-bold">Fees</h2>
                        {feesData.fees.length === 0 ? (
                            <p className="text-sm text-slate-500 py-4">No fees assigned yet.</p>
                        ) : (
                            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 dark:bg-slate-900">
                                        <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                            <th className="px-4 py-3">Fee Head</th>
                                            <th className="px-4 py-3">Due</th>
                                            <th className="px-4 py-3">Paid</th>
                                            <th className="px-4 py-3">Outstanding</th>
                                            <th className="px-4 py-3">Due Date</th>
                                            <th className="px-4 py-3">Status</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {feesData.fees.map((f) => (
                                            <tr key={f.id} className="border-t border-slate-100 dark:border-slate-800">
                                                <td className="px-4 py-2 font-medium">{f.fee_head_name}</td>
                                                <td className="px-4 py-2">{f.amount_due}</td>
                                                <td className="px-4 py-2 text-emerald-600">{f.amount_paid}</td>
                                                <td className="px-4 py-2 font-bold">{f.outstanding_balance}</td>
                                                <td className="px-4 py-2 text-slate-500">{f.due_date || "—"}</td>
                                                <td className="px-4 py-2">
                                                    <span className={`text-xs font-semibold px-2 py-1 rounded-full ${f.status === "active" ? "bg-slate-100 text-slate-700" : "bg-red-50 text-red-500"}`}>
                                                        {f.status}
                                                    </span>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>

                    <div className="space-y-3">
                        <h2 className="text-lg font-bold">Payment History</h2>
                        {loadingPayments ? (
                            <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                        ) : !payments || payments.length === 0 ? (
                            <p className="text-sm text-slate-500 py-4">No payments recorded yet.</p>
                        ) : (
                            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                                <table className="w-full text-sm">
                                    <thead className="bg-slate-50 dark:bg-slate-900">
                                        <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                            <th className="px-4 py-3">Receipt</th>
                                            <th className="px-4 py-3">Amount</th>
                                            <th className="px-4 py-3">Method</th>
                                            <th className="px-4 py-3">Date</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {payments.map((p) => (
                                            <tr key={p.id} className="border-t border-slate-100 dark:border-slate-800">
                                                <td className="px-4 py-2 font-mono text-xs">{p.receipt_number}</td>
                                                <td className="px-4 py-2 font-medium">{p.amount}</td>
                                                <td className="px-4 py-2 capitalize">{p.method.replace("_", " ")}</td>
                                                <td className="px-4 py-2 text-slate-500">{new Date(p.created_at).toLocaleDateString()}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                    </div>
                </div>
            ) : null}
        </div>
    );
}
