"use client";

import React, { useState, useRef } from "react";
import { Loader2, Printer, CheckCircle2, AlertTriangle, School, Receipt, FileText } from "lucide-react";
import { usePaymentReceipt } from "@/hooks/useFees";
import { useInstitutionProfile } from "@/hooks/useProfile";
import { CURRENCY } from "@/lib/currency";
import {
    Dialog,
    DialogBody,
    DialogContent,
    DialogFooter,
} from "@/components/ui/dialog";
import { ModalHeader } from "@/components/ui/modal-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface ReceiptModalProps {
    paymentId: string | null;
    isOpen: boolean;
    onClose: () => void;
}

type ReceiptFormat = "executive" | "thermal";

function formatIndianCurrency(val: number | string | undefined | null): string {
    const num = Number(val || 0);
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 2,
    }).format(num);
}

function formatDateTime(isoStr?: string | null): string {
    if (!isoStr) return "—";
    try {
        const d = new Date(isoStr);
        return d.toLocaleString("en-IN", {
            day: "numeric",
            month: "short",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        });
    } catch {
        return isoStr;
    }
}

export function ReceiptModal({ paymentId, isOpen, onClose }: ReceiptModalProps) {
    const { data: payment, isLoading, isError } = usePaymentReceipt(paymentId || undefined);
    const { data: institution } = useInstitutionProfile();
    const [format, setFormat] = useState<ReceiptFormat>("executive");
    const receiptRef = useRef<HTMLDivElement>(null);

    const schoolName = institution?.name || "Sunrise Valley Senior Secondary School";
    const schoolAddress = (institution as any)?.address || institution?.tagline || "Affiliated to CBSE, New Delhi";
    const schoolPhone = institution?.phone || "+91 (011) 2345-6789";
    const schoolEmail = institution?.email || "accounts@school.edu";

    const handlePrint = () => {
        window.print();
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
            <DialogContent
                className="max-w-2xl max-h-[92vh] p-0 flex flex-col overflow-hidden rounded-2xl"
                showCloseButton={false}
            >
                <ModalHeader
                    title="Payment Receipt"
                    subtitle="Official school fee acknowledgement"
                    metadata={
                        payment ? (
                            <span className="font-mono text-indigo-600 font-bold">
                                #{payment.receipt_number || payment.id.slice(0, 8)}
                            </span>
                        ) : undefined
                    }
                    actions={
                        payment ? (
                            <Button
                                size="sm"
                                onClick={handlePrint}
                                className="bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg h-9 font-semibold text-xs gap-1.5 print:hidden"
                            >
                                <Printer className="h-3.5 w-3.5" />
                                <span>Print Receipt</span>
                            </Button>
                        ) : undefined
                    }
                    onClose={onClose}
                />

                <DialogBody className="flex-1 overflow-y-auto px-6 py-5 [scrollbar-width:thin] space-y-5 bg-slate-50/50 dark:bg-slate-950/50">
                    {/* Format Switcher Toolbar (Hidden during print) */}
                    {payment && (
                        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 print:hidden shadow-xs">
                            <div className="flex items-center gap-1.5">
                                <span className="text-xs font-semibold text-slate-500 mr-1">Receipt Style:</span>
                                <button
                                    type="button"
                                    onClick={() => setFormat("executive")}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition ${
                                        format === "executive"
                                            ? "bg-indigo-600 text-white border-indigo-600"
                                            : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                                    }`}
                                >
                                    <FileText className="h-3.5 w-3.5" />
                                    <span>Executive Slip (A4 / A5)</span>
                                </button>
                                <button
                                    type="button"
                                    onClick={() => setFormat("thermal")}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg border transition ${
                                        format === "thermal"
                                            ? "bg-indigo-600 text-white border-indigo-600"
                                            : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-300 border-slate-200 dark:border-slate-700"
                                    }`}
                                >
                                    <Receipt className="h-3.5 w-3.5" />
                                    <span>80mm Thermal POS Slip</span>
                                </button>
                            </div>

                            <span className="text-[11px] text-slate-400 font-medium">
                                {format === "executive" ? "Standard Office & Parent Copy" : "Compact Cash Register Roll"}
                            </span>
                        </div>
                    )}

                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
                            <Loader2 className="h-8 w-8 animate-spin text-indigo-600 mb-3" />
                            <p className="text-sm font-medium">Loading receipt details...</p>
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
                    ) : format === "executive" ? (
                        /* EXECUTIVE SLIP (A4 / A5 FORMAT) */
                        <div
                            ref={receiptRef}
                            className="bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 rounded-2xl border border-slate-200 dark:border-slate-800 p-6 sm:p-8 shadow-xs space-y-6 print-avoid-break print:p-6 print:m-0 print:border-none print:shadow-none"
                        >
                            {/* Header */}
                            <div className="flex flex-col sm:flex-row sm:items-start justify-between border-b border-slate-200 dark:border-slate-800 pb-5 gap-4">
                                <div className="space-y-1">
                                    <div className="flex items-center gap-2">
                                        <div className="h-9 w-9 rounded-xl bg-indigo-50 dark:bg-indigo-950/60 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-indigo-600">
                                            <School className="h-5 w-5" />
                                        </div>
                                        <div>
                                            <h3 className="text-base font-black tracking-tight text-slate-900 dark:text-white uppercase">
                                                {schoolName}
                                            </h3>
                                            <p className="text-[11px] text-slate-500 dark:text-slate-400">
                                                {schoolAddress}
                                            </p>
                                        </div>
                                    </div>
                                    <p className="text-[10px] text-slate-400 pt-1">
                                        Tel: {schoolPhone} • Email: {schoolEmail}
                                    </p>
                                </div>

                                <div className="sm:text-right bg-slate-50 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-100 dark:border-slate-800 shrink-0">
                                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                                        Receipt Voucher
                                    </p>
                                    <p className="text-base font-mono font-black text-indigo-600 dark:text-indigo-400">
                                        #{payment.receipt_number}
                                    </p>
                                    <p className="text-xs text-slate-500 font-medium mt-0.5">
                                        {formatDateTime(payment.created_at)}
                                    </p>
                                </div>
                            </div>

                            {/* Student & Payment Metadata Grid */}
                            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 bg-slate-50/70 dark:bg-slate-800/30 p-4 rounded-xl border border-slate-100 dark:border-slate-800 text-xs">
                                <div>
                                    <span className="text-slate-400 uppercase text-[10px] font-bold tracking-wider block">
                                        Student Name
                                    </span>
                                    <span className="font-bold text-slate-900 dark:text-white text-sm truncate block mt-0.5">
                                        {payment.student_name || "—"}
                                    </span>
                                </div>

                                <div>
                                    <span className="text-slate-400 uppercase text-[10px] font-bold tracking-wider block">
                                        Payment Method
                                    </span>
                                    <span className="font-semibold capitalize text-slate-800 dark:text-slate-200 mt-0.5 block">
                                        {payment.method.replace("_", " ")}
                                    </span>
                                </div>

                                <div>
                                    <span className="text-slate-400 uppercase text-[10px] font-bold tracking-wider block">
                                        Collected By
                                    </span>
                                    <span className="font-medium text-slate-700 dark:text-slate-300 mt-0.5 block">
                                        {payment.recorded_by || "Accounts Desk"}
                                    </span>
                                </div>

                                <div>
                                    <span className="text-slate-400 uppercase text-[10px] font-bold tracking-wider block">
                                        Status
                                    </span>
                                    <span
                                        className={`inline-flex items-center gap-1 text-[11px] font-bold px-2 py-0.5 rounded-full mt-0.5 ${
                                            payment.status === "completed" && !payment.is_reversed
                                                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/70 dark:text-emerald-300 border border-emerald-200"
                                                : "bg-rose-50 text-rose-700 dark:bg-rose-950/70 dark:text-rose-300 border border-rose-200"
                                        }`}
                                    >
                                        {payment.status === "completed" && !payment.is_reversed ? (
                                            <>
                                                <CheckCircle2 className="h-3 w-3" />
                                                <span>Settled</span>
                                            </>
                                        ) : (
                                            <>
                                                <AlertTriangle className="h-3 w-3" />
                                                <span>Reversed</span>
                                            </>
                                        )}
                                    </span>
                                </div>
                            </div>

                            {/* Itemized Fee Breakdown Table */}
                            <div className="space-y-2">
                                <div className="flex items-center justify-between">
                                    <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                                        Fee Head Allocation Details
                                    </span>
                                    <span className="text-[11px] font-semibold text-slate-400">
                                        {payment.allocations?.length || 0} Head(s) Settled
                                    </span>
                                </div>

                                <div className="rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                                    <table className="w-full text-xs">
                                        <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                                            <tr className="text-left text-slate-500 uppercase tracking-wider font-semibold">
                                                <th className="px-4 py-2.5">S.No</th>
                                                <th className="px-4 py-2.5">Fee Particulars</th>
                                                <th className="px-4 py-2.5 text-right">Settled Amount</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                            {payment.allocations && payment.allocations.length > 0 ? (
                                                payment.allocations.map((alloc, idx) => (
                                                    <tr key={alloc.id} className="hover:bg-slate-50/50">
                                                        <td className="px-4 py-2.5 text-slate-400 font-mono w-12">
                                                            {idx + 1}
                                                        </td>
                                                        <td className="px-4 py-2.5 font-semibold text-slate-800 dark:text-slate-200">
                                                            {alloc.fee_head_name}
                                                        </td>
                                                        <td className="px-4 py-2.5 text-right font-mono font-bold text-slate-900 dark:text-slate-100">
                                                            {formatIndianCurrency(alloc.amount)}
                                                        </td>
                                                    </tr>
                                                ))
                                            ) : (
                                                <tr>
                                                    <td colSpan={3} className="px-4 py-3 text-center text-slate-400">
                                                        Consolidated Fee Collection
                                                    </td>
                                                </tr>
                                            )}
                                        </tbody>
                                        <tfoot className="bg-slate-50/80 dark:bg-slate-800/80 border-t border-slate-200 dark:border-slate-800">
                                            <tr>
                                                <th colSpan={2} className="px-4 py-3 text-left font-bold text-slate-900 dark:text-white uppercase text-xs">
                                                    Total Paid Amount
                                                </th>
                                                <th className="px-4 py-3 text-right font-mono font-black text-indigo-600 dark:text-indigo-400 text-sm">
                                                    {formatIndianCurrency(payment.amount)}
                                                </th>
                                            </tr>
                                        </tfoot>
                                    </table>
                                </div>
                            </div>

                            {payment.reference_note ? (
                                <div className="text-xs text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/40 p-3 rounded-xl border border-slate-100 dark:border-slate-800">
                                    <span className="font-semibold text-slate-900 dark:text-slate-200">
                                        Notes / Reference:{" "}
                                    </span>
                                    {payment.reference_note}
                                </div>
                            ) : null}

                            {/* Signatures & Footer Acknowledgement */}
                            <div className="pt-10 border-t border-slate-200 dark:border-slate-800 flex items-end justify-between px-2">
                                <div className="text-center">
                                    <div className="w-28 sm:w-36 border-b border-slate-400 mb-1 mx-auto" />
                                    <span className="text-[10px] uppercase font-bold text-slate-500">
                                        Parent / Depositor Sign
                                    </span>
                                </div>

                                <div className="text-center">
                                    <div className="w-32 sm:w-40 border-b border-slate-900 dark:border-slate-100 mb-1 mx-auto" />
                                    <span className="text-[10px] uppercase font-bold text-slate-700 dark:text-slate-300">
                                        Cashier / Accounts Officer
                                    </span>
                                </div>
                            </div>

                            <p className="text-[10px] text-center text-slate-400 pt-2">
                                Computerized acknowledgement voucher. Fees once paid are subject to institutional policies.
                            </p>
                        </div>
                    ) : (
                        /* 80mm THERMAL POS SLIP (COMPACT RECEIPT PRINTER) */
                        <div className="flex justify-center py-2 print:p-0 print:m-0">
                            <div
                                ref={receiptRef}
                                className="w-[300px] bg-white text-slate-900 p-5 rounded-xl border border-dashed border-slate-400 shadow-md font-mono text-xs space-y-3 print-avoid-break print:shadow-none print:border-none print:w-[76mm] print:p-2"
                            >
                                {/* Header */}
                                <div className="text-center space-y-0.5 border-b border-dashed border-slate-400 pb-3">
                                    <h4 className="font-bold text-sm uppercase tracking-tight">{schoolName}</h4>
                                    <p className="text-[10px] text-slate-600">{schoolAddress}</p>
                                    <p className="text-[10px] text-slate-500">Tel: {schoolPhone}</p>
                                    <div className="pt-1.5">
                                        <span className="inline-block text-[10px] font-bold uppercase border border-slate-900 px-2 py-0.5">
                                            FEE RECEIPT
                                        </span>
                                    </div>
                                </div>

                                {/* Metadata */}
                                <div className="space-y-1 text-[11px] border-b border-dashed border-slate-400 pb-2">
                                    <div className="flex justify-between">
                                        <span>Receipt #:</span>
                                        <span className="font-bold">{payment.receipt_number}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>Date:</span>
                                        <span>{formatDateTime(payment.created_at)}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>Student:</span>
                                        <span className="font-bold truncate max-w-[150px]">{payment.student_name}</span>
                                    </div>
                                    <div className="flex justify-between">
                                        <span>Method:</span>
                                        <span className="capitalize">{payment.method.replace("_", " ")}</span>
                                    </div>
                                </div>

                                {/* Items Breakdown */}
                                <div className="space-y-1 text-[11px] border-b border-dashed border-slate-400 pb-2">
                                    <div className="flex justify-between font-bold border-b border-slate-200 pb-0.5 mb-1 text-[10px]">
                                        <span>PARTICULAR</span>
                                        <span>AMOUNT</span>
                                    </div>
                                    {payment.allocations && payment.allocations.length > 0 ? (
                                        payment.allocations.map((alloc) => (
                                            <div key={alloc.id} className="flex justify-between">
                                                <span className="truncate max-w-[170px]">{alloc.fee_head_name}</span>
                                                <span className="font-bold">{formatIndianCurrency(alloc.amount)}</span>
                                            </div>
                                        ))
                                    ) : (
                                        <div className="flex justify-between">
                                            <span>Fee Payment</span>
                                            <span className="font-bold">{formatIndianCurrency(payment.amount)}</span>
                                        </div>
                                    )}
                                </div>

                                {/* Total */}
                                <div className="border-b border-dashed border-slate-400 pb-2">
                                    <div className="flex justify-between items-center text-sm font-black">
                                        <span>TOTAL PAID:</span>
                                        <span>{formatIndianCurrency(payment.amount)}</span>
                                    </div>
                                </div>

                                {/* Barcode & Footer */}
                                <div className="text-center pt-1 space-y-1.5">
                                    <div className="h-6 w-44 mx-auto flex items-center justify-center gap-[2px] opacity-80">
                                        {[2, 3, 1, 4, 1, 5, 2, 6, 3, 5, 1, 4, 2, 3, 6, 4, 2, 5, 1, 3, 2, 4, 3, 2].map((w, idx) => (
                                            <div key={idx} style={{ width: `${(w % 2.5) + 1.2}px` }} className="h-full bg-slate-900" />
                                        ))}
                                    </div>
                                    <p className="text-[9px] text-slate-500 font-semibold tracking-wider">
                                        *{payment.receipt_number}*
                                    </p>
                                    <p className="text-[9px] text-slate-400 uppercase pt-0.5">
                                        Thank You! Please Retain This Slip.
                                    </p>
                                </div>
                            </div>
                        </div>
                    )}
                </DialogBody>

                <DialogFooter className="px-6 py-3.5 bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 flex justify-between items-center print:hidden shrink-0">
                    <span className="text-xs text-slate-500 font-medium">
                        {format === "executive" ? "Standard A4 / A5 Document Format" : "80mm POS Thermal Slip (76mm Roll)"}
                    </span>
                    <div className="flex items-center gap-2">
                        <Button variant="outline" size="sm" onClick={onClose} className="rounded-lg h-9">
                            Close
                        </Button>
                        {payment && (
                            <Button
                                size="sm"
                                onClick={handlePrint}
                                className="bg-indigo-600 hover:bg-indigo-500 text-white gap-1.5 rounded-lg h-9 font-semibold text-xs"
                            >
                                <Printer className="h-3.5 w-3.5" />
                                <span>Print Receipt</span>
                            </Button>
                        )}
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
