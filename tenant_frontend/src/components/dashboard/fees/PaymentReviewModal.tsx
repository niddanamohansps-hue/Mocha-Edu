"use client";

import { CURRENCY } from "@/lib/currency";
import { useEffect, useState } from "react";
import { Loader2, ShieldCheck, ExternalLink, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import {
    useInitiateOnlinePayment,
    useInitiateParentChildPayment,
} from "@/hooks/useFees";
import { submitGatewayForm } from "@/lib/payments";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export interface FeeItemToPay {
    id: string;
    fee_head_name?: string;
    fee_head?: string;
    outstanding_balance: string;
    amount_due?: string;
}

interface PaymentReviewModalProps {
    isOpen: boolean;
    onClose: () => void;
    studentId: string;
    studentName?: string;
    isParent?: boolean;
    selectedFees: FeeItemToPay[];
}

export function PaymentReviewModal({
    isOpen,
    onClose,
    studentId,
    studentName,
    isParent = false,
    selectedFees,
}: PaymentReviewModalProps) {
    const [allocations, setAllocations] = useState<Record<string, string>>({});
    const [isRedirecting, setIsRedirecting] = useState(false);

    const initiateOnlinePayment = useInitiateOnlinePayment();
    const initiateParentPayment = useInitiateParentChildPayment();

    // Initialize allocations with outstanding amounts
    useEffect(() => {
        if (isOpen && selectedFees.length > 0) {
            const initial: Record<string, string> = {};
            selectedFees.forEach((fee) => {
                initial[fee.id] = Number(fee.outstanding_balance).toFixed(2);
            });
            setAllocations(initial);
            setIsRedirecting(false);
        }
    }, [isOpen, selectedFees]);

    const handleAmountChange = (feeId: string, val: string) => {
        setAllocations((prev) => ({
            ...prev,
            [feeId]: val,
        }));
    };

    // Calculate total and validation errors
    let totalAmount = 0;
    const errors: Record<string, string> = {};

    selectedFees.forEach((fee) => {
        const valStr = allocations[fee.id] || "0";
        const val = parseFloat(valStr);
        const max = parseFloat(fee.outstanding_balance);

        if (isNaN(val) || val <= 0) {
            errors[fee.id] = "Must be greater than 0";
        } else if (val > max) {
            errors[fee.id] = `Cannot exceed outstanding ${CURRENCY} ${max.toFixed(2)}`;
        } else {
            totalAmount += val;
        }
    });

    const hasErrors = Object.keys(errors).length > 0 || totalAmount <= 0;
    const isSubmitting =
        initiateOnlinePayment.isPending || initiateParentPayment.isPending || isRedirecting;

    const handleProceedToPayment = async () => {
        if (hasErrors || selectedFees.length === 0) return;

        const allocationPayload = selectedFees.map((fee) => ({
            student_fee: fee.id,
            amount: parseFloat(allocations[fee.id]).toFixed(2),
        }));

        const totalFormatted = totalAmount.toFixed(2);
        const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
        const callbackPath = isParent
            ? "/dashboard/parent-portal/fees/callback"
            : "/dashboard/fees/callback";

        const returnUrl = `${baseUrl}${callbackPath}`;
        const failureUrl = `${baseUrl}${callbackPath}?status=failed`;

        try {
            if (isParent) {
                const res = await initiateParentPayment.mutateAsync({
                    student_id: studentId,
                    amount: totalFormatted,
                    allocations: allocationPayload,
                    gateway: "esewa",
                    return_url: returnUrl,
                    failure_url: failureUrl,
                });

                setIsRedirecting(true);
                toast.info("Order initiated. Redirecting to eSewa payment portal...");
                submitGatewayForm(res.gateway_payload);
            } else {
                const res = await initiateOnlinePayment.mutateAsync({
                    student: studentId,
                    amount: totalFormatted,
                    allocations: allocationPayload,
                    gateway: "esewa",
                    return_url: returnUrl,
                    failure_url: failureUrl,
                });

                setIsRedirecting(true);
                toast.info("Order initiated. Redirecting to eSewa payment portal...");
                submitGatewayForm(res.gateway_payload);
            }
        } catch (err: any) {
            setIsRedirecting(false);
            // Error is toasted automatically by the mutation hooks
        }
    };

    return (
        <Dialog open={isOpen} onOpenChange={(open) => !open && !isSubmitting && onClose()}>
            <DialogContent className="max-w-xl p-0 overflow-hidden sm:rounded-2xl">
                <DialogHeader className="p-6 pb-2 border-b border-slate-100 dark:border-slate-800">
                    <DialogTitle className="text-xl font-bold flex items-center gap-2">
                        <ShieldCheck className="h-5 w-5 text-emerald-600" />
                        Review Online Fee Payment
                    </DialogTitle>
                    <DialogDescription className="text-xs text-slate-500">
                        {studentName ? `Paying fees for ${studentName}. ` : ""}
                        Confirm fee allocations and proceed to the payment gateway.
                    </DialogDescription>
                </DialogHeader>

                {isRedirecting ? (
                    <div className="py-20 flex flex-col items-center justify-center text-center p-6 space-y-4">
                        <div className="relative">
                            <Loader2 className="h-12 w-12 animate-spin text-emerald-600" />
                            <div className="absolute inset-0 flex items-center justify-center">
                                <span className="h-3 w-3 bg-emerald-600 rounded-full" />
                            </div>
                        </div>
                        <h3 className="text-lg font-bold text-slate-900 dark:text-white">
                            Redirecting to eSewa Portal
                        </h3>
                        <p className="text-sm text-slate-500 max-w-sm">
                            Please do not refresh this page or click back. You will be redirected to complete
                            the payment securely.
                        </p>
                    </div>
                ) : (
                    <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
                        {/* Selected Fee Heads List */}
                        <div className="space-y-3">
                            <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">
                                Fee Allocations ({selectedFees.length} fee{selectedFees.length > 1 ? "s" : ""})
                            </Label>
                            <div className="divide-y divide-slate-100 dark:divide-slate-800 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
                                {selectedFees.map((fee) => {
                                    const headName = fee.fee_head_name || fee.fee_head || "Fee";
                                    const error = errors[fee.id];
                                    return (
                                        <div
                                            key={fee.id}
                                            className="p-3.5 bg-white dark:bg-slate-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                                        >
                                            <div className="flex-1">
                                                <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                                                    {headName}
                                                </p>
                                                <p className="text-xs text-slate-400 mt-0.5">
                                                    Outstanding Balance:{" "}
                                                    <span className="font-mono font-medium text-slate-700 dark:text-slate-300">
                                                        {CURRENCY} {Number(fee.outstanding_balance).toFixed(2)}
                                                    </span>
                                                </p>
                                            </div>
                                            <div className="w-full sm:w-44 flex flex-col items-end">
                                                <div className="relative w-full">
                                                    <span className="absolute left-3 top-2.5 text-xs text-slate-400">
                                                        {CURRENCY}
                                                    </span>
                                                    <Input
                                                        type="number"
                                                        step="0.01"
                                                        min="1"
                                                        max={fee.outstanding_balance}
                                                        value={allocations[fee.id] || ""}
                                                        onChange={(e) =>
                                                            handleAmountChange(fee.id, e.target.value)
                                                        }
                                                        disabled={isSubmitting}
                                                        className={`pl-12 text-right font-mono text-sm h-9 ${
                                                            error ? "border-red-500 focus-visible:ring-red-500" : ""
                                                        }`}
                                                    />
                                                </div>
                                                {error && (
                                                    <span className="text-[11px] text-red-500 mt-1 font-medium">
                                                        {error}
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Gateway selection info */}
                        <div className="bg-slate-50 dark:bg-slate-900/60 p-4 rounded-xl border border-slate-100 dark:border-slate-800 space-y-3">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                                <Label className="text-xs font-bold uppercase text-slate-500 tracking-wider">
                                    Payment Method
                                </Label>
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                                    eSewa ePay Gateway
                                </span>
                            </div>
                            <p className="text-xs text-slate-500">
                                Transactions are encrypted and authenticated via SHA-256 HMAC cryptographic signatures.
                            </p>
                        </div>

                        {/* Summary Total */}
                        <div className="bg-indigo-50/60 dark:bg-indigo-950/40 p-4 rounded-xl border border-indigo-100 dark:border-indigo-900/50 flex flex-wrap items-center justify-between gap-2">
                            <div>
                                <p className="text-xs font-semibold text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">
                                    Total Payable Amount
                                </p>
                                <p className="text-xs text-slate-500 mt-0.5">
                                    Sum of fee allocations
                                </p>
                            </div>
                            <div className="text-right">
                                <p className="text-2xl font-black font-mono text-indigo-700 dark:text-indigo-400">
                                    {CURRENCY} {totalAmount.toFixed(2)}
                                </p>
                            </div>
                        </div>

                        {/* Important notice */}
                        <div className="flex items-start gap-2.5 text-xs text-slate-500">
                            <AlertCircle className="h-4 w-4 text-amber-500 shrink-0 mt-0.5" />
                            <p>
                                If counter cash payment was processed concurrently, the gateway order will be flagged
                                for school reconciliation to prevent duplicate charges or accounting discrepancies.
                            </p>
                        </div>
                    </div>
                )}

                {!isRedirecting && (
                    <div className="p-4 bg-slate-50 dark:bg-slate-900 border-t border-slate-100 dark:border-slate-800 flex items-center justify-end gap-3">
                        <Button variant="outline" onClick={onClose} disabled={isSubmitting}>
                            Cancel
                        </Button>
                        <Button
                            onClick={handleProceedToPayment}
                            disabled={hasErrors || isSubmitting || selectedFees.length === 0}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white gap-2 font-bold px-6 shadow-sm"
                        >
                            {isSubmitting ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Initiating...
                                </>
                            ) : (
                                <>
                                    Proceed to Pay {CURRENCY} {totalAmount.toFixed(2)}
                                    <ExternalLink className="h-4 w-4" />
                                </>
                            )}
                        </Button>
                    </div>
                )}
            </DialogContent>
        </Dialog>
    );
}

