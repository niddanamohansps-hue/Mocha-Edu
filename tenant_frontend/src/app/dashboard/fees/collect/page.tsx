"use client";

import { CURRENCY } from "@/lib/currency";
import { useMemo, useState } from "react";
import { LoaderCircle, Plus, Receipt as ReceiptIcon, XCircle } from "lucide-react";
import {
    useAssignStudentFee,
    useCancelStudentFee,
    useFeeHeads,
    useRecordPayment,
    useStudentFees,
    useStudentPayments,
} from "@/hooks/useFees";
import { PAYMENT_METHOD_CHOICES } from "@/types/Fees";
import { usePermissions } from "@/providers/PermissionProvider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import Unauthorized from "@/components/Unauthorized";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ResponsiveList } from "@/components/common/ResponsiveList";


export default function CollectPaymentPage() {
    const { can, isOwner } = usePermissions();
    const canView = isOwner || can("view_fees");
    const canManage = isOwner || can("manage_fee_structures");
    const canCollect = isOwner || can("collect_payments");

    const [studentId, setStudentId] = useState("");
    const [academicYear] = useState("");

    const { data: feesData, isLoading: loadingFees } = useStudentFees(studentId || undefined);
    const { data: payments } = useStudentPayments(studentId || undefined);
    const { data: heads } = useFeeHeads();

    const { mutate: assignFee, isPending: assigning } = useAssignStudentFee();
    const { mutate: cancelFee } = useCancelStudentFee();
    const { mutate: recordPayment, isPending: recording } = useRecordPayment();

    const [assignForm, setAssignForm] = useState({ fee_head: "", amount_due: "", due_date: "" });
    const [selectedAllocations, setSelectedAllocations] = useState<Record<string, string>>({});
    const [method, setMethod] = useState("cash");
    const [cancelReason, setCancelReason] = useState<Record<string, string>>({});

    const activeFees = useMemo(
        () => feesData?.fees.filter((f) => f.status === "active") ?? [],
        [feesData]
    );

    const totalAllocated = useMemo(
        () =>
            Object.values(selectedAllocations).reduce((sum, v) => sum + (parseFloat(v) || 0), 0),
        [selectedAllocations]
    );

    const handleAssign = () => {
        if (!studentId) return;
        assignFee(
            {
                studentId,
                data: {
                    fee_head: assignForm.fee_head,
                    academic_year: academicYear,
                    amount_due: assignForm.amount_due,
                    due_date: assignForm.due_date || undefined,
                },
            },
            { onSuccess: () => setAssignForm({ fee_head: "", amount_due: "", due_date: "" }) }
        );
    };

    const handleCancel = (feeId: string) => {
        const reason = cancelReason[feeId];
        if (!studentId || !reason) return;
        cancelFee({ studentId, feeId, cancellationReason: reason });
    };

    const handleRecordPayment = () => {
        if (!studentId) return;
        const allocations = Object.entries(selectedAllocations)
            .filter(([, amount]) => parseFloat(amount) > 0)
            .map(([student_fee, amount]) => ({ student_fee, amount }));
        if (allocations.length === 0) return;

        recordPayment(
            {
                student: studentId,
                amount: totalAllocated.toFixed(2),
                method: method as any,
                allocations,
            },
            { onSuccess: () => setSelectedAllocations({}) }
        );
    };

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-8 max-w-4xl">
            <div>
                <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Student Fees &amp; Payments</h1>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Assign fees, collect payments, and view a student&apos;s balance.
                </p>
            </div>

            <div className="w-72">
                <label htmlFor="f-student-id" className="text-xs font-medium text-slate-500 mb-1 block">Student ID</label>
                <Input id="f-student-id" placeholder="Paste a student ID" value={studentId} onChange={(e) => setStudentId(e.target.value)} />
            </div>

            {!studentId ? (
                <p className="text-sm text-slate-500 py-6">Enter a student ID to view their fees.</p>
            ) : loadingFees ? (
                <div className="flex items-center justify-center py-16"><LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" /></div>
            ) : feesData ? (
                <div className="space-y-8">
                    <Card className="border-none shadow-md">
                        <CardContent className="p-6">
                            <p className="text-xs text-slate-500 uppercase font-bold">Total still to pay</p>
                            <p className="text-3xl font-black">{feesData.total_outstanding}</p>
                        </CardContent>
                    </Card>

                    {canManage && (
                        <div className="space-y-3 border-b border-slate-200 dark:border-slate-800 pb-6">
                            <h2 className="text-lg font-bold">Assign a Fee</h2>
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 items-end">
                                <div>
                                    <label className="text-xs font-medium text-slate-500 mb-1 block">Fee type</label>
                                    <Select value={assignForm.fee_head} onValueChange={(v) => setAssignForm((f) => ({ ...f, fee_head: v }))}>
                                        <SelectTrigger><SelectValue placeholder="Select" /></SelectTrigger>
                                        <SelectContent>
                                            {heads?.filter((h) => h.is_active).map((h) => (
                                                <SelectItem key={h.id} value={h.id}>{h.name}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <label htmlFor="f-amount-due" className="text-xs font-medium text-slate-500 mb-1 block">Amount Due</label>
                                    <Input id="f-amount-due" type="number" value={assignForm.amount_due} onChange={(e) => setAssignForm((f) => ({ ...f, amount_due: e.target.value }))} />
                                </div>
                                <div>
                                    <label htmlFor="f-due-date" className="text-xs font-medium text-slate-500 mb-1 block">Due Date</label>
                                    <Input id="f-due-date" type="date" value={assignForm.due_date} onChange={(e) => setAssignForm((f) => ({ ...f, due_date: e.target.value }))} />
                                </div>
                                <Button onClick={handleAssign} disabled={assigning || !assignForm.fee_head || !assignForm.amount_due} className="gap-2">
                                    {assigning && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                    <Plus className="h-4 w-4" /> Assign
                                </Button>
                            </div>
                        </div>
                    )}

                    <div className="space-y-3">
                        <h2 className="text-lg font-bold">Fees</h2>
                        {feesData.fees.length === 0 ? (
                            <p className="text-sm text-slate-500 py-4">No fees assigned yet.</p>
                        ) : (
                                <ResponsiveList
                                    rows={feesData.fees}
                                    rowKey={(f) => f.id}
                                    columns={[
                                        { key: "head", header: "Fee", primary: true, cell: (f) => f.fee_head_name },
                                        { key: "outstanding", header: "Still to pay", className: "font-bold", cell: (f) => f.outstanding_balance },
                                        { key: "due", header: "Amount due", cell: (f) => f.amount_due },
                                        { key: "paid", header: "Paid", className: "text-emerald-600", cell: (f) => f.amount_paid },
                                        {
                                            key: "status",
                                            header: "Status",
                                            cell: (f) => (
                                                <StatusBadge
                                                    label={f.status}
                                                    className={f.status === "active" ? "bg-slate-100 text-slate-700" : "bg-red-50 text-red-500"}
                                                />
                                            ),
                                        },
                                        ...(canCollect
                                            ? [
                                                  {
                                                      key: "allocate",
                                                      header: `Take payment (${CURRENCY})`,
                                                      cell: (f: (typeof feesData.fees)[number]) =>
                                                          f.status === "active" && parseFloat(f.outstanding_balance) > 0 ? (
                                                              <Input
                                                                  type="number"
                                                                  className="w-28"
                                                                  placeholder="0.00"
                                                                  aria-label={`Amount to take for ${f.fee_head_name}`}
                                                                  value={selectedAllocations[f.id] ?? ""}
                                                                  onChange={(e) => setSelectedAllocations((s) => ({ ...s, [f.id]: e.target.value }))}
                                                              />
                                                          ) : (
                                                              "—"
                                                          ),
                                                  },
                                              ]
                                            : []),
                                    ]}
                                    actionsHeader="Cancel this fee"
                                    actions={
                                        canManage
                                            ? (f) =>
                                                  f.status === "active" ? (
                                                      <div className="flex gap-2 items-center">
                                                          <Input
                                                              className="w-32"
                                                              placeholder="Reason"
                                                              aria-label={`Reason for cancelling ${f.fee_head_name}`}
                                                              value={cancelReason[f.id] ?? ""}
                                                              onChange={(e) => setCancelReason((s) => ({ ...s, [f.id]: e.target.value }))}
                                                          />
                                                          <Button size="sm" variant="ghost" aria-label={`Cancel ${f.fee_head_name}`} onClick={() => handleCancel(f.id)}>
                                                              <XCircle className="h-4 w-4 text-red-500" />
                                                          </Button>
                                                      </div>
                                                  ) : null
                                            : undefined
                                    }
                                />
                        )}
                    </div>

                    {canCollect && activeFees.length > 0 && (
                        <div className="space-y-3 pt-2 border-t border-slate-200 dark:border-slate-800">
                            <h2 className="text-lg font-bold">Record Payment</h2>
                            <div className="flex flex-wrap gap-4 items-end">
                                <div className="w-48">
                                    <label className="text-xs font-medium text-slate-500 mb-1 block">Method</label>
                                    <Select value={method} onValueChange={setMethod}>
                                        <SelectTrigger><SelectValue /></SelectTrigger>
                                        <SelectContent>
                                            {PAYMENT_METHOD_CHOICES.map((m) => (
                                                <SelectItem key={m} value={m}>{m.replace("_", " ")}</SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div>
                                    <p className="text-xs text-slate-500">Amount being paid now</p>
                                    <p className="text-xl font-black">{totalAllocated.toFixed(2)}</p>
                                </div>
                                <Button onClick={handleRecordPayment} disabled={recording || totalAllocated <= 0} className="gap-2">
                                    {recording && <LoaderCircle className="h-4 w-4 animate-spin" />}
                                    <ReceiptIcon className="h-4 w-4" /> Record Payment
                                </Button>
                            </div>
                        </div>
                    )}

                    <div className="space-y-3 pt-2">
                        <h2 className="text-lg font-bold">Payment History</h2>
                        {!payments || payments.length === 0 ? (
                            <p className="text-sm text-slate-500 py-4">No payments recorded yet.</p>
                        ) : (
                                <ResponsiveList
                                    rows={payments}
                                    rowKey={(p) => p.id}
                                    columns={[
                                        { key: "receipt", header: "Receipt", primary: true, className: "font-mono text-xs", cell: (p) => p.receipt_number },
                                        { key: "amount", header: "Amount", className: "font-medium", cell: (p) => p.amount },
                                        { key: "method", header: "Paid by", className: "capitalize", cell: (p) => p.method.replace("_", " ") },
                                        {
                                            key: "status",
                                            header: "Status",
                                            cell: (p) => (
                                                <StatusBadge
                                                    label={p.status}
                                                    className={p.status === "completed" ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"}
                                                />
                                            ),
                                        },
                                        { key: "date", header: "Date", className: "text-slate-500", cell: (p) => new Date(p.created_at).toLocaleDateString() },
                                    ]}
                                />
                        )}
                    </div>
                </div>
            ) : null}
        </div>
    );
}
