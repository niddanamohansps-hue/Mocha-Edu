"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
    CheckCircle2,
    AlertTriangle,
    XCircle,
    Clock,
    Loader2,
    ArrowLeft,
    Receipt,
    RefreshCw,
} from "lucide-react";
import { useVerifyOnlinePayment, useOnlinePaymentOrder } from "@/hooks/useFees";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ReceiptModal } from "@/components/dashboard/fees/ReceiptModal";
import { OnlinePaymentOrder } from "@/types/Fees";

interface PaymentCallbackHandlerProps {
    returnPath: string; // e.g. "/dashboard/fees/my-fees" or "/dashboard/parent-portal/fees"
    portalTitle: string; // e.g. "My Fees" or "Parent Portal Fees"
}

type CallbackUiState =
    | "verifying"
    | "pending"
    | "success"
    | "already_completed"
    | "reconciliation_required"
    | "failed";

export function PaymentCallbackHandler({ returnPath, portalTitle }: PaymentCallbackHandlerProps) {
    const router = useRouter();
    const searchParams = useSearchParams();

    const [uiState, setUiState] = useState<CallbackUiState>("verifying");
    const [statusMessage, setStatusMessage] = useState<string>("");
    const [orderData, setOrderData] = useState<OnlinePaymentOrder | null>(null);
    const [receiptNumber, setReceiptNumber] = useState<string>("");
    const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);

    const verifyMutation = useVerifyOnlinePayment();
    const hasInitiatedVerification = useRef(false);

    // Order polling state
    const [pollingOrderId, setPollingOrderId] = useState<string | undefined>(undefined);
    const pollCountRef = useRef(0);
    const MAX_POLLS = 10; // 10 attempts * 3s = 30s maximum

    const { data: polledOrder, refetch: refetchOrder } = useOnlinePaymentOrder(pollingOrderId, {
        refetchInterval: (query) => {
            const currentStatus = query.state.data?.status;
            if (
                !pollingOrderId ||
                pollCountRef.current >= MAX_POLLS ||
                currentStatus === "success" ||
                currentStatus === "reconciliation_required" ||
                currentStatus === "failed" ||
                currentStatus === "expired"
            ) {
                return false;
            }
            pollCountRef.current += 1;
            return 3000;
        },
    });

    // React to polled order updates
    useEffect(() => {
        if (!polledOrder) return;
        setOrderData(polledOrder);

        if (polledOrder.status === "success") {
            setUiState("success");
            setReceiptNumber(polledOrder.receipt_number || "");
            if (polledOrder.payment) setSelectedPaymentId(polledOrder.payment);
        } else if (polledOrder.status === "reconciliation_required") {
            setUiState("reconciliation_required");
            setStatusMessage(
                polledOrder.reconciliation_reason ||
                    "Payment was verified by the gateway but requires manual school reconciliation."
            );
        } else if (polledOrder.status === "failed" || polledOrder.status === "expired") {
            setUiState("failed");
            setStatusMessage(polledOrder.reconciliation_reason || "The payment order has failed or expired.");
        }
    }, [polledOrder]);

    useEffect(() => {
        if (hasInitiatedVerification.current) return;
        hasInitiatedVerification.current = true;

        const dataParam = searchParams.get("data");
        const statusParam = searchParams.get("status");
        const orderIdParam = searchParams.get("order_id");

        if (statusParam === "failed" || statusParam === "failure") {
            setUiState("failed");
            setStatusMessage("The payment was cancelled or declined at the payment gateway.");
            return;
        }

        if (!dataParam && !orderIdParam) {
            setUiState("failed");
            setStatusMessage("No payment transaction data found in the return request.");
            return;
        }

        const runVerification = async () => {
            try {
                const res = await verifyMutation.mutateAsync({
                    data: dataParam || undefined,
                    order_id: orderIdParam || undefined,
                });

                if (res.order) {
                    setOrderData(res.order);
                    if (res.order.payment) setSelectedPaymentId(res.order.payment);
                }
                if (res.receipt_number) {
                    setReceiptNumber(res.receipt_number);
                }

                if (res.status === "success" || res.status === "already_completed") {
                    setUiState("success");
                } else if (res.status === "reconciliation_required") {
                    setUiState("reconciliation_required");
                    setStatusMessage(
                        res.reason ||
                            "Payment was received by eSewa, but cannot be automatically settled due to a concurrent balance change. School administrators will reconcile it manually."
                    );
                } else if (res.status === "pending" || res.status === "initiated") {
                    setUiState("pending");
                    if (res.order?.id) {
                        setPollingOrderId(res.order.id);
                    }
                } else {
                    setUiState("failed");
                    setStatusMessage(res.reason || "Payment settlement could not be completed.");
                }
            } catch (err: any) {
                const errDetail =
                    err.response?.data?.error ||
                    err.response?.data?.detail ||
                    "Failed to verify payment with the school server.";
                setUiState("failed");
                setStatusMessage(errDetail);
            }
        };

        runVerification();
    }, [searchParams, verifyMutation]);

    return (
        <div className="max-w-2xl mx-auto py-12 px-4 sm:px-6">
            <Card className="border border-slate-200 dark:border-slate-800 shadow-lg rounded-2xl overflow-hidden">
                <CardContent className="p-8">
                    {/* VERIFYING STATE */}
                    {uiState === "verifying" && (
                        <div className="flex flex-col items-center text-center py-12 space-y-4">
                            <div className="relative">
                                <Loader2 className="h-16 w-16 animate-spin text-indigo-600" />
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className="h-4 w-4 bg-indigo-600 rounded-full" />
                                </div>
                            </div>
                            <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                                Verifying Payment...
                            </h2>
                            <p className="text-sm text-slate-500 max-w-md">
                                Please wait while we cryptographically verify your payment with the eSewa gateway
                                and settle your fees. Do not close or refresh this tab.
                            </p>
                        </div>
                    )}

                    {/* SUCCESS STATE */}
                    {uiState === "success" && (
                        <div className="flex flex-col items-center text-center py-6 space-y-6">
                            <div className="h-16 w-16 bg-emerald-100 dark:bg-emerald-950/80 rounded-full flex items-center justify-center text-emerald-600 dark:text-emerald-400">
                                <CheckCircle2 className="h-10 w-10" />
                            </div>

                            <div className="space-y-1">
                                <h2 className="text-2xl font-black text-slate-900 dark:text-white">
                                    Payment Successful!
                                </h2>
                                <p className="text-sm text-slate-500">
                                    Your fee payment has been confirmed and officially recorded.
                                </p>
                            </div>

                            {orderData && (
                                <div className="w-full bg-slate-50 dark:bg-slate-900/60 rounded-xl p-5 border border-slate-100 dark:border-slate-800 text-left space-y-3">
                                    <div className="flex justify-between items-center text-sm">
                                        <span className="text-slate-500">Amount Paid</span>
                                        <span className="font-mono font-bold text-base text-slate-900 dark:text-white">
                                            NPR {Number(orderData.amount).toFixed(2)}
                                        </span>
                                    </div>
                                    {receiptNumber && (
                                        <div className="flex justify-between items-center text-sm">
                                            <span className="text-slate-500">Official Receipt</span>
                                            <span className="font-mono font-semibold text-indigo-600 dark:text-indigo-400">
                                                {receiptNumber}
                                            </span>
                                        </div>
                                    )}
                                    <div className="flex justify-between items-center text-sm">
                                        <span className="text-slate-500">Gateway Transaction</span>
                                        <span className="font-mono text-xs text-slate-600 dark:text-slate-400">
                                            {orderData.gateway_order_id}
                                        </span>
                                    </div>
                                </div>
                            )}

                            <div className="flex flex-col sm:flex-row items-center gap-3 w-full pt-4">
                                {(orderData?.payment || selectedPaymentId) && (
                                    <Button
                                        onClick={() =>
                                            setSelectedPaymentId(orderData?.payment || selectedPaymentId)
                                        }
                                        className="w-full sm:w-1/2 bg-indigo-600 hover:bg-indigo-700 text-white gap-2 font-bold"
                                    >
                                        <Receipt className="h-4 w-4" />
                                        View Official Receipt
                                    </Button>
                                )}
                                <Button
                                    variant="outline"
                                    onClick={() => router.push(returnPath)}
                                    className={`w-full ${
                                        orderData?.payment || selectedPaymentId
                                            ? "sm:w-1/2"
                                            : "sm:w-full"
                                    } gap-2`}
                                >
                                    <ArrowLeft className="h-4 w-4" />
                                    Return to {portalTitle}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* RECONCILIATION REQUIRED (OPTION B) */}
                    {uiState === "reconciliation_required" && (
                        <div className="flex flex-col items-center text-center py-6 space-y-6">
                            <div className="h-16 w-16 bg-amber-100 dark:bg-amber-950/80 rounded-full flex items-center justify-center text-amber-600 dark:text-amber-400">
                                <AlertTriangle className="h-10 w-10" />
                            </div>

                            <div className="space-y-2">
                                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                                    Reconciliation Required
                                </h2>
                                <p className="text-sm text-slate-600 dark:text-slate-300 max-w-lg">
                                    Your funds were successfully received and verified by the eSewa gateway,
                                    but could not be automatically allocated to your fees because your balance
                                    changed concurrently (e.g. counter cash settlement).
                                </p>
                            </div>

                            <div className="w-full bg-amber-50/70 dark:bg-amber-950/40 rounded-xl p-5 border border-amber-200 dark:border-amber-900 text-left space-y-3">
                                <p className="text-xs font-bold uppercase tracking-wider text-amber-800 dark:text-amber-300">
                                    Status Details
                                </p>
                                <p className="text-xs text-amber-700 dark:text-amber-300 leading-relaxed">
                                    {statusMessage ||
                                        "School administrative staff have been notified to review this order and apply the credit manually. The displayed fee balance will be updated once reconciliation is complete."}
                                </p>
                                {orderData && (
                                    <div className="pt-2 border-t border-amber-200/60 dark:border-amber-900/60 text-xs font-mono text-amber-800 dark:text-amber-300 flex justify-between">
                                        <span>Order Amount: NPR {Number(orderData.amount).toFixed(2)}</span>
                                        <span>Reference: {orderData.gateway_order_id.slice(0, 12)}...</span>
                                    </div>
                                )}
                            </div>

                            <div className="w-full pt-4">
                                <Button
                                    onClick={() => router.push(returnPath)}
                                    className="w-full bg-slate-900 hover:bg-slate-800 text-white gap-2"
                                >
                                    <ArrowLeft className="h-4 w-4" />
                                    Return to {portalTitle}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* PENDING / POLLING STATE */}
                    {uiState === "pending" && (
                        <div className="flex flex-col items-center text-center py-6 space-y-6">
                            <div className="h-16 w-16 bg-blue-100 dark:bg-blue-950/80 rounded-full flex items-center justify-center text-blue-600 dark:text-blue-400">
                                <Clock className="h-10 w-10 animate-pulse" />
                            </div>

                            <div className="space-y-2">
                                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                                    Payment Pending Confirmation
                                </h2>
                                <p className="text-sm text-slate-500 max-w-md">
                                    The gateway has registered the transaction. Awaiting final confirmation from
                                    eSewa servers.
                                </p>
                            </div>

                            <div className="p-4 bg-slate-50 dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 text-xs text-slate-500 max-w-md text-left">
                                <p className="font-semibold text-slate-700 dark:text-slate-300 mb-1">
                                    Important:
                                </p>
                                <p>
                                    Please DO NOT initiate another payment. The automated reconciliation task runs
                                    continuously and will finalize this transaction once the gateway responds.
                                </p>
                            </div>

                            <div className="flex flex-col sm:flex-row items-center gap-3 w-full pt-4">
                                <Button
                                    variant="outline"
                                    onClick={() => refetchOrder()}
                                    className="w-full sm:w-1/2 gap-2"
                                >
                                    <RefreshCw className="h-4 w-4" />
                                    Check Now
                                </Button>
                                <Button
                                    onClick={() => router.push(returnPath)}
                                    className="w-full sm:w-1/2 bg-indigo-600 hover:bg-indigo-700 text-white gap-2"
                                >
                                    <ArrowLeft className="h-4 w-4" />
                                    Return to {portalTitle}
                                </Button>
                            </div>
                        </div>
                    )}

                    {/* FAILED / CANCELLED STATE */}
                    {uiState === "failed" && (
                        <div className="flex flex-col items-center text-center py-6 space-y-6">
                            <div className="h-16 w-16 bg-red-100 dark:bg-red-950/80 rounded-full flex items-center justify-center text-red-600 dark:text-red-400">
                                <XCircle className="h-10 w-10" />
                            </div>

                            <div className="space-y-2">
                                <h2 className="text-2xl font-bold text-slate-900 dark:text-white">
                                    Payment Unsuccessful
                                </h2>
                                <p className="text-sm text-slate-500 max-w-md">
                                    {statusMessage ||
                                        "The transaction was not completed. No money was deducted for fee settlement."}
                                </p>
                            </div>

                            <div className="w-full pt-4">
                                <Button
                                    onClick={() => router.push(returnPath)}
                                    className="w-full bg-slate-900 hover:bg-slate-800 text-white gap-2"
                                >
                                    <ArrowLeft className="h-4 w-4" />
                                    Return to {portalTitle} and Try Again
                                </Button>
                            </div>
                        </div>
                    )}
                </CardContent>
            </Card>

            <ReceiptModal
                isOpen={!!selectedPaymentId}
                paymentId={selectedPaymentId}
                onClose={() => setSelectedPaymentId(null)}
            />
        </div>
    );
}

