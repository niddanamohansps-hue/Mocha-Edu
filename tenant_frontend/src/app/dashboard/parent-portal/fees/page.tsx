"use client";

import { useState } from "react";
import { LoaderCircle } from "lucide-react";
import { useChildFees, useLinkedChildren } from "@/hooks/useParentPortal";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import Unauthorized from "@/components/Unauthorized";
import ChildSwitcher from "@/components/parent-portal/ChildSwitcher";
import { StatusBadge } from "@/components/common/StatusBadge";

export default function ParentPortalFeesPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_child_fees");

    const { data: children } = useLinkedChildren();
    const [selectedChildId, setSelectedChildId] = useState<string | undefined>(undefined);

    const { data, isLoading } = useChildFees(selectedChildId);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Child Fees</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Outstanding balance, fees, and payment history for your selected child
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
                        : "Select a child to view their fees."}
                </div>
            ) : isLoading ? (
                <div className="flex items-center justify-center py-20">
                    <LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" />
                </div>
            ) : data ? (
                <div className="space-y-8">
                    <Card className="border-none shadow-md">
                        <CardContent className="p-6">
                            <p className="text-xs text-slate-500 uppercase font-bold">Total Outstanding</p>
                            <p className="text-3xl font-black">{data.total_outstanding}</p>
                        </CardContent>
                    </Card>

                    <div className="space-y-3">
                        <h2 className="text-lg font-bold">Fees</h2>
                        {data.fees.length === 0 ? (
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
                                        {data.fees.map((f) => (
                                            <tr key={f.id} className="border-t border-slate-100 dark:border-slate-800">
                                                <td className="px-4 py-2 font-medium">{f.fee_head}</td>
                                                <td className="px-4 py-2">{f.amount_due}</td>
                                                <td className="px-4 py-2 text-emerald-600">{f.amount_paid}</td>
                                                <td className="px-4 py-2 font-bold">{f.outstanding_balance}</td>
                                                <td className="px-4 py-2 text-slate-500">{f.due_date || "—"}</td>
                                                <td className="px-4 py-2">
                                                    <StatusBadge
                                                        label={f.status}
                                                        className={f.status === "active" ? "bg-slate-100 text-slate-700" : "bg-red-50 text-red-500"}
                                                    />
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
                        {data.payments.length === 0 ? (
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
                                        {data.payments.map((p) => (
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
