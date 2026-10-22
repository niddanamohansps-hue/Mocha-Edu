"use client";

import { useState } from "react";
import { Loader2, Receipt, AlertCircle, RefreshCw, CheckCircle2, Clock, XCircle } from "lucide-react";
import { OnlinePaymentOrder } from "@/types/Fees";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { Button } from "@/components/ui/button";
import { ReceiptModal } from "@/components/dashboard/fees/ReceiptModal";

interface OnlineOrdersTableProps {
    orders: OnlinePaymentOrder[] | undefined;
    isLoading: boolean;
    onRefresh?: () => void;
}

export function OnlineOrdersTable({ orders, isLoading, onRefresh }: OnlineOrdersTableProps) {
    const [selectedPaymentId, setSelectedPaymentId] = useState<string | null>(null);

    const getStatusBadge = (status: string) => {
        switch (status) {
            case "success":
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                        <CheckCircle2 className="h-3 w-3" />
                        Completed
                    </span>
                );
            case "pending":
            case "initiated":
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
                        <Clock className="h-3 w-3" />
                        Pending
                    </span>
                );
            case "reconciliation_required":
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-200 border border-amber-300 dark:border-amber-700">
                        <AlertCircle className="h-3 w-3" />
                        Needs a check
                    </span>
                );
            case "failed":
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700 dark:bg-red-950/60 dark:text-red-300 border border-red-200 dark:border-red-800">
                        <XCircle className="h-3 w-3" />
                        Failed
                    </span>
                );
            case "expired":
                return (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400">
                        <Clock className="h-3 w-3" />
                        Expired
                    </span>
                );
            default:
                return <StatusBadge label={status} />;
        }
    };

    return (
        <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                    <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                        Online Payment Transactions
                    </h2>
                    <p className="text-xs text-slate-500">
                        History of gateway transaction attempts and their real-time settlement status.
                    </p>
                </div>
                {onRefresh && (
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={onRefresh}
                        disabled={isLoading}
                        className="gap-1.5 text-xs h-8"
                    >
                        <RefreshCw className={`h-3.5 w-3.5 ${isLoading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                )}
            </div>

            {isLoading ? (
                <div className="flex justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-indigo-600" />
                </div>
            ) : !orders || orders.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 p-8 text-center text-sm text-slate-500">
                    No online payment transactions initiated yet.
                </div>
            ) : (
                <ResponsiveList
                    rows={orders}
                    rowKey={(o) => o.id}
                    columns={[
                        {
                            key: "amount",
                            header: "Amount",
                            primary: true,
                            cell: (o) => <span className="font-mono font-bold">NPR {Number(o.amount).toFixed(2)}</span>,
                        },
                        {
                            key: "date",
                            header: "Date",
                            className: "text-slate-500 whitespace-nowrap",
                            cell: (o) => new Date(o.created_at).toLocaleString(),
                        },
                        {
                            key: "order",
                            header: "Order ID",
                            hideOnMobile: true,
                            className: "font-mono text-xs",
                            cell: (o) => (o.gateway_order_id ? o.gateway_order_id.slice(0, 12) + "..." : o.id.slice(0, 8)),
                        },
                        { key: "gateway", header: "Paid with", className: "capitalize", cell: (o) => o.gateway },
                        {
                            key: "status",
                            header: "Status",
                            cell: (o) => (
                                <div className="flex flex-col gap-1 items-start">
                                    {getStatusBadge(o.status)}
                                    {o.reconciliation_reason && (
                                        <span className="text-xs text-amber-600 dark:text-amber-400 max-w-xs" title={o.reconciliation_reason}>
                                            {o.reconciliation_reason}
                                        </span>
                                    )}
                                </div>
                            ),
                        },
                    ]}
                    actionsHeader="Receipt"
                    actions={(o) =>
                        o.status === "success" && o.payment ? (
                            <Button
                                size="sm"
                                variant="outline"
                                onClick={() => setSelectedPaymentId(o.payment)}
                                className="gap-1.5 border-indigo-200 text-indigo-700 hover:bg-indigo-50 dark:border-indigo-800 dark:text-indigo-300"
                            >
                                <Receipt className="h-3.5 w-3.5" />
                                Receipt
                            </Button>
                        ) : o.status === "reconciliation_required" ? (
                            <span className="text-xs text-slate-500 italic">Under school review</span>
                        ) : o.status === "pending" ? (
                            <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">Waiting for confirmation</span>
                        ) : null
                    }
                />
            )}

            <ReceiptModal
                isOpen={!!selectedPaymentId}
                paymentId={selectedPaymentId}
                onClose={() => setSelectedPaymentId(null)}
            />
        </div>
    );
}

