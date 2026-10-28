"use client";

import { CURRENCY } from "@/lib/currency";
import { useMemo, useState } from "react";
import {
    LoaderCircle,
    Receipt,
    CreditCard,
    AlertCircle,
    CheckCircle2,
    Clock,
    ShieldAlert,
} from "lucide-react";
import { useMe } from "@/hooks/useAuth";
import { useStudentFees, useStudentPayments, useOnlinePaymentOrders, usePayableGateways } from "@/hooks/useFees";
import { usePermissions } from "@/providers/PermissionProvider";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import Unauthorized from "@/components/Unauthorized";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { PaymentReviewModal } from "@/components/dashboard/fees/PaymentReviewModal";
import { ReceiptModal } from "@/components/dashboard/fees/ReceiptModal";
import { OnlineOrdersTable } from "@/components/dashboard/fees/OnlineOrdersTable";
import { StudentFee } from "@/types/Fees";

export default function MyFeesPage() {
    const { can, isOwner } = usePermissions();
    const { data: payableGateways = [] } = usePayableGateways();
    const canView = isOwner || can("view_own_fees");
    const canPay = isOwner || can("pay_own_fees");

    const { data: user } = useMe();
    const studentId = user?.profile?.student_id ?? undefined;
    const studentName = user?.profile
        ? `${user.profile.first_name || ""} ${user.profile.last_name || ""}`.trim()
        : "Student";

    const { data: feesData, isLoading: loadingFees } = useStudentFees(studentId);
    const { data: payments, isLoading: loadingPayments } = useStudentPayments(studentId);
    const {
        data: onlineOrdersData,
        isLoading: loadingOnlineOrders,
        refetch: refetchOnlineOrders,
    } = useOnlinePaymentOrders(studentId ? { student: studentId } : undefined);

    const [selectedFeeIds, setSelectedFeeIds] = useState<string[]>([]);
    const [isReviewModalOpen, setIsReviewModalOpen] = useState(false);
    const [selectedReceiptPaymentId, setSelectedReceiptPaymentId] = useState<string | null>(null);

    // Eligible fees for payment: active status and positive outstanding balance
    const eligibleFees = useMemo(() => {
        if (!feesData?.fees) return [];
        return feesData.fees.filter(
            (f) => f.status === "active" && parseFloat(f.outstanding_balance) > 0
        );
    }, [feesData]);

    const isAllSelected =
        eligibleFees.length > 0 &&
        eligibleFees.every((f) => selectedFeeIds.includes(f.id));

    const handleSelectAll = (checked: boolean) => {
        if (checked) {
            setSelectedFeeIds(eligibleFees.map((f) => f.id));
        } else {
            setSelectedFeeIds([]);
        }
    };

    const handleToggleFee = (feeId: string) => {
        setSelectedFeeIds((prev) =>
            prev.includes(feeId) ? prev.filter((id) => id !== feeId) : [...prev, feeId]
        );
    };

    const selectedFeesToPay: StudentFee[] = useMemo(() => {
        if (!feesData?.fees) return [];
        return feesData.fees.filter((f) => selectedFeeIds.includes(f.id));
    }, [feesData, selectedFeeIds]);

    const selectedTotal = useMemo(() => {
        return selectedFeesToPay.reduce((acc, curr) => acc + parseFloat(curr.outstanding_balance), 0);
    }, [selectedFeesToPay]);

    if (!canView) {
        return <Unauthorized />;
    }

    return (
        <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900 dark:text-white">My Fees</h1>
                    <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                        View outstanding balance, itemized fees breakdown, and pay securely online.
                    </p>
                </div>
                {canPay && eligibleFees.length > 0 && (
                    <Button
                        onClick={() => setIsReviewModalOpen(true)}
                        disabled={selectedFeeIds.length === 0}
                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-2 self-start sm:self-auto shadow-sm"
                    >
                        <CreditCard className="h-4 w-4" />
                        Pay Selected ({selectedFeeIds.length}) — {CURRENCY} {selectedTotal.toFixed(2)}
                    </Button>
                )}
            </div>

            {!studentId ? (
                <div className="p-8 text-center bg-slate-50 dark:bg-slate-900/50 rounded-2xl border border-slate-200 dark:border-slate-800 text-slate-500">
                    <ShieldAlert className="h-8 w-8 text-amber-500 mx-auto mb-2" />
                    <p className="font-semibold text-slate-700 dark:text-slate-300">
                        No Student Profile Linked
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                        No student record is linked to your current authenticated account.
                    </p>
                </div>
            ) : loadingFees ? (
                <div className="flex items-center justify-center py-16">
                    <LoaderCircle className="h-8 w-8 animate-spin text-indigo-600" />
                </div>
            ) : feesData ? (
                <div className="space-y-6">
                    {/* Top Overview Cards */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                        <Card className="border border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl">
                            <CardContent className="p-5">
                                <p className="text-xs text-slate-500 uppercase font-bold tracking-wider">
                                    Total still to pay
                                </p>
                                <p className="text-3xl font-black font-mono text-slate-900 dark:text-white mt-1">
                                    {CURRENCY} {Number(feesData.total_outstanding).toFixed(2)}
                                </p>
                                <p className="text-xs text-slate-400 mt-1">
                                    {eligibleFees.length} fee{eligibleFees.length !== 1 ? "s" : ""} pending settlement
                                </p>
                            </CardContent>
                        </Card>

                        <Card className="border border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl">
                            <CardContent className="p-5">
                                <p className="text-xs text-slate-500 uppercase font-bold tracking-wider">
                                    Online Payment Status
                                </p>
                                <div className="mt-1 flex items-center gap-2">
                                    {canPay && payableGateways.length > 0 ? (
                                        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-emerald-600 dark:text-emerald-400">
                                            <CheckCircle2 className="h-4 w-4" />
                                            Enabled
                                        </span>
                                    ) : canPay ? (
                                        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-amber-600 dark:text-amber-400">
                                            <AlertCircle className="h-4 w-4" />
                                            Not set up by the school yet
                                        </span>
                                    ) : (
                                        <span className="inline-flex items-center gap-1.5 text-sm font-bold text-amber-600 dark:text-amber-400">
                                            <AlertCircle className="h-4 w-4" />
                                            Counter Only (No Online Access)
                                        </span>
                                    )}
                                </div>
                                <p className="text-xs text-slate-400 mt-1">
                                    {payableGateways.length > 0 ? payableGateways.map((g) => g.label).join(", ") : "Pay at the school office"}
                                </p>
                            </CardContent>
                        </Card>

                        <Card className="border border-slate-200 dark:border-slate-800 shadow-sm rounded-2xl">
                            <CardContent className="p-5">
                                <p className="text-xs text-slate-500 uppercase font-bold tracking-wider">
                                    Selected for Payment
                                </p>
                                <p className="text-3xl font-black font-mono text-indigo-600 dark:text-indigo-400 mt-1">
                                    {CURRENCY} {selectedTotal.toFixed(2)}
                                </p>
                                <p className="text-xs text-slate-400 mt-1">
                                    {selectedFeeIds.length} item{selectedFeeIds.length !== 1 ? "s" : ""} chosen
                                </p>
                            </CardContent>
                        </Card>
                    </div>

                    {!canPay && (
                        <div className="bg-amber-50 dark:bg-amber-950/40 p-4 rounded-xl border border-amber-200 dark:border-amber-900 flex items-start gap-3 text-xs text-amber-800 dark:text-amber-300">
                            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                            <p>
                                Online payment initiation is not active on your role. Please contact school
                                administration to enable online fee payment or pay via counter cash / bank deposit.
                            </p>
                        </div>
                    )}

                    {/* Main Tabs */}
                    <Tabs defaultValue="breakdown" className="space-y-4">
                        <TabsList className="bg-slate-100 dark:bg-slate-800/60 p-1 rounded-xl">
                            <TabsTrigger value="breakdown" className="rounded-lg text-xs font-semibold">
                                Fee Dues ({feesData.fees.length})
                            </TabsTrigger>
                            <TabsTrigger value="payments" className="rounded-lg text-xs font-semibold">
                                Official Receipts ({payments?.length || 0})
                            </TabsTrigger>
                            <TabsTrigger value="online" className="rounded-lg text-xs font-semibold">
                                Online Gateway Transactions
                            </TabsTrigger>
                        </TabsList>

                        {/* TAB 1: Fee Dues Breakdown */}
                        <TabsContent value="breakdown" className="space-y-4">
                            {feesData.fees.length === 0 ? (
                                <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 p-8 text-center text-sm text-slate-500">
                                    No fee dues assigned to your account.
                                </div>
                            ) : (
                                    <ResponsiveList
                                        rows={feesData.fees}
                                        rowKey={(f) => f.id}
                                        rowClassName={(f) => (selectedFeeIds.includes(f.id) ? "bg-indigo-50/40 dark:bg-indigo-950/20" : "")}
                                        leading={
                                            canPay
                                                ? {
                                                      header: (
                                                          <Checkbox
                                                              checked={isAllSelected}
                                                              onCheckedChange={handleSelectAll}
                                                              disabled={eligibleFees.length === 0}
                                                              aria-label="Select all eligible fees"
                                                          />
                                                      ),
                                                      cell: (f) => (
                                                          <Checkbox
                                                              checked={selectedFeeIds.includes(f.id)}
                                                              onCheckedChange={() => handleToggleFee(f.id)}
                                                              disabled={!(f.status === "active" && parseFloat(f.outstanding_balance) > 0)}
                                                              aria-label={`Select ${f.fee_head_name}`}
                                                          />
                                                      ),
                                                  }
                                                : undefined
                                        }
                                        columns={[
                                            { key: "head", header: "Fee", primary: true, cell: (f) => f.fee_head_name },
                                            { key: "outstanding", header: "Still to pay", className: "font-mono font-bold", cell: (f) => `${CURRENCY} ${Number(f.outstanding_balance).toFixed(2)}` },
                                            { key: "due", header: "Due date", className: "text-slate-500", cell: (f) => (f.due_date ? new Date(f.due_date).toLocaleDateString() : "—") },
                                            { key: "amount", header: "Amount due", className: "font-mono", cell: (f) => `${CURRENCY} ${Number(f.amount_due).toFixed(2)}` },
                                            {
                                                key: "discount",
                                                header: "Discount",
                                                className: "font-mono text-slate-400",
                                                cell: (f) => (parseFloat(f.discount_amount) > 0 ? `${CURRENCY} ${Number(f.discount_amount).toFixed(2)}` : "—"),
                                            },
                                            { key: "paid", header: "Paid", className: "font-mono text-emerald-600 font-medium", cell: (f) => `${CURRENCY} ${Number(f.amount_paid).toFixed(2)}` },
                                            { key: "year", header: "Academic year", className: "text-slate-500 font-mono", cell: (f) => f.academic_year || "—" },
                                            {
                                                key: "status",
                                                header: "Status",
                                                cell: (f) => (
                                                    <StatusBadge
                                                        label={f.status}
                                                        className={
                                                            f.status === "active"
                                                                ? "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300"
                                                                : "bg-red-50 text-red-500 dark:bg-red-950 dark:text-red-400"
                                                        }
                                                    />
                                                ),
                                            },
                                        ]}
                                    />
                            )}

                            {/* Floating / Bottom Pay Bar */}
                            {canPay && selectedFeeIds.length > 0 && (
                                <div className="p-4 bg-indigo-50/80 dark:bg-indigo-950/60 rounded-xl border border-indigo-200 dark:border-indigo-900 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xs">
                                    <div>
                                        <p className="text-sm font-bold text-indigo-950 dark:text-indigo-200">
                                            {selectedFeeIds.length} fee{selectedFeeIds.length > 1 ? "s" : ""} selected
                                        </p>
                                        <p className="text-xs text-indigo-700 dark:text-indigo-300">
                                            Ready to pay online.
                                        </p>
                                    </div>
                                    <Button
                                        onClick={() => setIsReviewModalOpen(true)}
                                        className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold gap-2 px-6"
                                    >
                                        <CreditCard className="h-4 w-4" />
                                        Pay {CURRENCY} {selectedTotal.toFixed(2)}
                                    </Button>
                                </div>
                            )}
                        </TabsContent>

                        {/* TAB 2: Official Receipts */}
                        <TabsContent value="payments" className="space-y-4">
                            {loadingPayments ? (
                                <div className="flex justify-center py-12">
                                    <LoaderCircle className="h-6 w-6 animate-spin text-indigo-600" />
                                </div>
                            ) : !payments || payments.length === 0 ? (
                                <div className="rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 p-8 text-center text-sm text-slate-500">
                                    No completed payments or official receipts recorded yet.
                                </div>
                            ) : (
                                    <ResponsiveList
                                        rows={payments}
                                        rowKey={(p) => p.id}
                                        columns={[
                                            { key: "receipt", header: "Receipt", primary: true, className: "font-mono text-xs font-bold text-indigo-600 dark:text-indigo-400", cell: (p) => p.receipt_number },
                                            { key: "amount", header: "Amount", className: "font-mono font-medium", cell: (p) => `${CURRENCY} ${Number(p.amount).toFixed(2)}` },
                                            { key: "method", header: "Paid by", className: "capitalize", cell: (p) => p.method.replace("_", " ") },
                                            { key: "date", header: "Date", className: "text-slate-500", cell: (p) => new Date(p.created_at).toLocaleDateString() },
                                            {
                                                key: "status",
                                                header: "Status",
                                                cell: (p) => {
                                                    const ok = p.status === "completed" && !p.is_reversed;
                                                    return (
                                                        <span
                                                            className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${
                                                                ok
                                                                    ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                                                                    : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
                                                            }`}
                                                        >
                                                            {ok ? <CheckCircle2 className="h-3 w-3" /> : <AlertCircle className="h-3 w-3" />}
                                                            {ok ? "Completed" : "Reversed"}
                                                        </span>
                                                    );
                                                },
                                            },
                                        ]}
                                        actionsHeader="Receipt"
                                        actions={(p) => (
                                            <Button
                                                size="sm"
                                                variant="outline"
                                                onClick={() => setSelectedReceiptPaymentId(p.id)}
                                                className="gap-1.5 border-indigo-200 text-indigo-700 hover:bg-indigo-50 dark:border-indigo-800 dark:text-indigo-300"
                                            >
                                                <Receipt className="h-3.5 w-3.5" />
                                                View receipt
                                            </Button>
                                        )}
                                    />
                            )}
                        </TabsContent>

                        {/* TAB 3: Online Gateway Transactions */}
                        <TabsContent value="online" className="space-y-4">
                            <OnlineOrdersTable
                                orders={onlineOrdersData?.results}
                                isLoading={loadingOnlineOrders}
                                onRefresh={refetchOnlineOrders}
                            />
                        </TabsContent>
                    </Tabs>
                </div>
            ) : null}

            {/* Payment Review & Checkout Modal */}
            <PaymentReviewModal
                isOpen={isReviewModalOpen}
                onClose={() => setIsReviewModalOpen(false)}
                studentId={studentId || ""}
                studentName={studentName}
                isParent={false}
                selectedFees={selectedFeesToPay}
            />

            {/* Receipt Modal */}
            <ReceiptModal
                isOpen={!!selectedReceiptPaymentId}
                paymentId={selectedReceiptPaymentId}
                onClose={() => setSelectedReceiptPaymentId(null)}
            />
        </div>
    );
}
