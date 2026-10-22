"use client";

import { useRef } from "react";
import { Loader2, Printer, X, CheckCircle2, AlertTriangle } from "lucide-react";
import { usePaymentReceipt } from "@/hooks/useFees";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

interface ReceiptModalProps {
    paymentId: string | null;
    isOpen: boolean;
    onClose: () => void;
}

export function ReceiptModal({ paymentId, isOpen, onClose }: ReceiptModalProps) {
    const { data: payment, isLoading, isError } = usePaymentReceipt(paymentId || undefined);
    const receiptRef = useRef<HTMLDivElement>(null);

    const handlePrint = () => {
        window.print();
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-2xl p-0 overflow-hidden sm:rounded-2xl">
                <DialogHeader className="p-6 pb-2 border-b border-slate-100 dark:border-slate-800 flex flex-wrap flex-row items-center justify-between gap-2">
                    <div>
                        <DialogTitle className="text-xl font-bold">Payment Receipt</DialogTitle>
                        <p className="text-xs text-slate-500 mt-1">
                            Official school fee transaction receipt
                        </p>
                    </div>
                </DialogHeader>

                <div className="p-6 max-h-[75vh] overflow-y-auto">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
                            <Loader2 className="h-8 w-8 animate-spin text-indigo-600 mb-3" />
                            <p className="text-sm">Loading receipt details...</p>
                        </div>
                    ) : isError || !payment ? (
                        <div className="text-center py-12 text-slate-500">
                            <AlertTriangle className="h-10 w-10 text-amber-500 mx-auto mb-2" />
                            <p className="font-semibold text-slate-700 dark:text-slate-200">
                                Receipt Unavailable
                            </p>
                            <p className="text-xs text-slate-500 mt-1">
                                Unable to load receipt or you may not have permission to view it.
                            </p>
                        </div>
                    ) : (
                        <div ref={receiptRef} className="space-y-6 print:p-8 print:m-0">
                            {/* Receipt Header */}
                            <div className="flex flex-col sm:flex-row sm:items-center justify-between border-b border-slate-200 dark:border-slate-700 pb-4 gap-4">
                                <div>
                                    <h3 className="text-lg font-black tracking-tight text-slate-900 dark:text-white uppercase">
                                        EduSekai School System
                                    </h3>
                                    <p className="text-xs text-slate-500">Fee Payment Acknowledgement</p>
                                </div>
                                <div className="sm:text-right">
                                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">
                                        Receipt Number
                                    </p>
                                    <p className="text-base font-mono font-bold text-indigo-600 dark:text-indigo-400">
                                        {payment.receipt_number}
                                    </p>
                                    <p className="text-xs text-slate-400 mt-0.5">
                                        {new Date(payment.created_at).toLocaleString()}
                                    </p>
                                </div>
                            </div>

                            {/* Details Grid */}
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 bg-slate-50 dark:bg-slate-900/60 p-4 rounded-xl border border-slate-100 dark:border-slate-800 text-sm">
                                <div>
                                    <p className="text-xs text-slate-500 font-medium">Student</p>
                                    <p className="font-semibold text-slate-900 dark:text-white">
                                        {payment.student_name || "—"}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs text-slate-500 font-medium">Payment Method</p>
                                    <p className="font-semibold capitalize text-slate-900 dark:text-white">
                                        {payment.method.replace("_", " ")}
                                    </p>
                                </div>
                                <div>
                                    <p className="text-xs text-slate-500 font-medium">Status</p>
                                    <span
                                        className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full mt-0.5 ${
                                            payment.status === "completed" && !payment.is_reversed
                                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                                : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
                                        }`}
                                    >
                                        {payment.status === "completed" && !payment.is_reversed ? (
                                            <>
                                                <CheckCircle2 className="h-3 w-3" />
                                                Paid / Completed
                                            </>
                                        ) : (
                                            <>
                                                <AlertTriangle className="h-3 w-3" />
                                                Reversed
                                            </>
                                        )}
                                    </span>
                                </div>
                            </div>

                            {/* Allocations Table */}
                            <div className="space-y-2">
                                <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                                    Fee Allocation Breakdown
                                </p>
                                <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                                    <div className="w-full overflow-x-auto"><table className="w-full text-sm">
                                        <thead className="bg-slate-50 dark:bg-slate-900">
                                            <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                                                <th className="px-4 py-2.5">Fee type</th>
                                                <th className="px-4 py-2.5 text-right">Amount (NPR)</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                            {payment.allocations && payment.allocations.length > 0 ? (
                                                payment.allocations.map((alloc) => (
                                                    <tr key={alloc.id}>
                                                        <td className="px-4 py-2.5 font-medium text-slate-800 dark:text-slate-200">
                                                            {alloc.fee_head_name}
                                                        </td>
                                                        <td className="px-4 py-2.5 text-right font-mono font-medium">
                                                            {Number(alloc.amount).toFixed(2)}
                                                        </td>
                                                    </tr>
                                                ))
                                            ) : (
                                                <tr>
                                                    <td colSpan={2} className="px-4 py-3 text-center text-slate-400">
                                                        No itemized breakdown recorded
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                        <tfoot className="bg-slate-50/70 dark:bg-slate-900/70 border-t border-slate-200 dark:border-slate-800">
                                            <tr>
                                                <th className="px-4 py-3 text-left font-bold text-slate-900 dark:text-white">
                                                    Total Paid
                                                </th>
                                                <th className="px-4 py-3 text-right font-mono font-black text-indigo-600 dark:text-indigo-400 text-base">
                                                    NPR {Number(payment.amount).toFixed(2)}
                                                </th>
                                            </tr>
                                        </tfoot>
                                    </table></div>
                                </div>
                            </div>

                            {payment.reference_note ? (
                                <div className="text-xs text-slate-500 bg-slate-50 dark:bg-slate-900/40 p-3 rounded-lg border border-slate-100 dark:border-slate-800">
                                    <span className="font-semibold text-slate-700 dark:text-slate-300">
                                        Reference Note:{" "}
                                    </span>
                                    {payment.reference_note}
                                </div>
                            ) : null}

                            <div className="pt-4 border-t border-slate-100 dark:border-slate-800 text-[11px] text-slate-400 flex flex-col sm:flex-row items-center justify-between gap-2">
                                <p>This is a system-generated receipt and requires no physical signature.</p>
                                <p className="font-mono">EduSekai SaaS</p>
                            </div>
                        </div>
                    )}
                </div>

                <div className="p-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 flex justify-end gap-3 print:hidden">
                    <Button variant="outline" onClick={onClose}>
                        Close
                    </Button>
                    {payment && (
                        <Button
                            onClick={handlePrint}
                            className="bg-indigo-600 hover:bg-indigo-700 text-white gap-2"
                        >
                            <Printer className="h-4 w-4" />
                            Print Receipt
                        </Button>
                    )}
                </div>
            </DialogContent>
        </Dialog>
    );
}

