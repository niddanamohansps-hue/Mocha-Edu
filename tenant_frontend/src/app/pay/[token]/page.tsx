"use client";

import { use, useCallback, useEffect, useState } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import axiosInstance from "@/lib/axios";
import { openRazorpayCheckout } from "@/lib/payments";
import { Button } from "@/components/ui/button";
import type { GatewayPayload } from "@/types/Fees";

interface PayDetail {
    school: string;
    student: string;
    available: boolean;
    total: string | number;
    fees: { id: string; fee_head: string; due_date: string | null; outstanding: string }[];
}

type Stage = "loading" | "invalid" | "ready" | "starting" | "verifying" | "success" | "pending";

const rupees = (value: string | number) =>
    Number(value).toLocaleString("en-IN", { style: "currency", currency: "INR", minimumFractionDigits: 2 });

/** The page a fee reminder links to: shows what is owed and takes the payment, with no login. */
export default function PayPage({ params }: { params: Promise<{ token: string }> }) {
    const { token } = use(params);
    const [stage, setStage] = useState<Stage>("loading");
    const [detail, setDetail] = useState<PayDetail | null>(null);
    const [selected, setSelected] = useState<string[]>([]);
    const [message, setMessage] = useState("");
    const [receipt, setReceipt] = useState("");

    const load = useCallback(async () => {
        try {
            const response = await axiosInstance.get<PayDetail>(`/fees/pay-link/${token}/`);
            setDetail(response.data);
            setSelected(response.data.fees.map((f) => f.id));
            setStage("ready");
        } catch {
            setStage("invalid");
        }
    }, [token]);

    useEffect(() => {
        // Fetching on arrival: the state is set once the answer comes back.
        // eslint-disable-next-line react-hooks/set-state-in-effect
        void load();
    }, [load]);

    const total = (detail?.fees ?? []).filter((f) => selected.includes(f.id)).reduce((sum, f) => sum + Number(f.outstanding), 0);

    // Razorpay confirms to us first; the school's server then checks the signed answer before anything is marked paid.
    const verify = async (query: string, attempt = 0) => {
        setStage("verifying");
        try {
            const body = Object.fromEntries(new URLSearchParams(query));
            const response = await axiosInstance.post<{ status: string; receipt_number?: string }>("/fees/online/verify/", body);
            const status = response.data.status;
            if (status === "success" || status === "already_completed") {
                setReceipt(response.data.receipt_number ?? "");
                setStage("success");
            } else if (status === "reconciliation_required") {
                setMessage("Your payment was received. The school will confirm it and issue the receipt.");
                setStage("pending");
            } else if ((status === "pending" || status === "initiated") && attempt < 5) {
                setTimeout(() => void verify(query, attempt + 1), 4000);
            } else {
                setMessage("We are still confirming your payment. If money was deducted, the school will confirm it shortly.");
                setStage("pending");
            }
        } catch {
            setMessage("We could not confirm the payment yet. If money was deducted, the school will confirm it shortly.");
            setStage("pending");
        }
    };

    const pay = async () => {
        setStage("starting");
        setMessage("");
        try {
            const response = await axiosInstance.post<{ gateway_payload: GatewayPayload }>(`/fees/pay-link/${token}/start/`, { fees: selected });
            const payload = response.data.gateway_payload;
            if (payload.gateway !== "razorpay") throw new Error("unsupported");
            await openRazorpayCheckout(payload, {
                description: `Fees for ${detail?.student ?? "student"}`,
                onPaid: (query) => void verify(query),
                onDismiss: () => setStage("ready"),
            });
        } catch (error) {
            const apiMessage = (error as { response?: { data?: { error?: string } } })?.response?.data?.error;
            setMessage(apiMessage ?? "The payment could not be started. Please try again or pay at the school office.");
            setStage("ready");
        }
    };

    return (
        <main className="h-screen overflow-y-auto bg-slate-50 px-4 py-10 dark:bg-slate-950">
            <div className="mx-auto max-w-md space-y-6">
                {stage === "loading" && (
                    <div className="flex justify-center py-20"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>
                )}

                {stage === "invalid" && (
                    <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center dark:border-slate-800 dark:bg-slate-900">
                        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">This payment link is not valid</h1>
                        <p className="mt-2 text-sm text-slate-500">It may have expired. Please use the latest reminder from the school, or pay at the school office.</p>
                    </section>
                )}

                {detail && (stage === "ready" || stage === "starting") && (
                    <section className="space-y-5 rounded-2xl border border-slate-200 bg-white p-6 dark:border-slate-800 dark:bg-slate-900">
                        <header>
                            <p className="text-sm text-slate-500">{detail.school}</p>
                            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Fees for {detail.student}</h1>
                        </header>
                        {detail.fees.length === 0 ? (
                            <p className="text-sm text-slate-600 dark:text-slate-300">Nothing is due right now. Thank you.</p>
                        ) : (
                            <>
                                <ul className="space-y-2">
                                    {detail.fees.map((fee) => (
                                        <li key={fee.id}>
                                            <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg border border-slate-200 p-3 text-sm dark:border-slate-800">
                                                <span className="flex items-center gap-3">
                                                    <input
                                                        type="checkbox"
                                                        checked={selected.includes(fee.id)}
                                                        onChange={(e) =>
                                                            setSelected((current) => (e.target.checked ? [...current, fee.id] : current.filter((id) => id !== fee.id)))
                                                        }
                                                    />
                                                    <span>
                                                        <span className="font-medium">{fee.fee_head}</span>
                                                        {fee.due_date && <span className="block text-xs text-slate-500">Due {fee.due_date}</span>}
                                                    </span>
                                                </span>
                                                <span className="font-semibold">{rupees(fee.outstanding)}</span>
                                            </label>
                                        </li>
                                    ))}
                                </ul>
                                {message && <p className="text-sm text-red-600">{message}</p>}
                                {detail.available ? (
                                    <Button className="w-full" disabled={stage === "starting" || selected.length === 0} onClick={() => void pay()}>
                                        {stage === "starting" ? "Opening payment..." : `Pay ${rupees(total)}`}
                                    </Button>
                                ) : (
                                    <p className="text-sm text-amber-600">Online payment is not available right now. Please pay at the school office.</p>
                                )}
                                <p className="text-xs text-slate-500">Payments are made securely through Razorpay (UPI, cards, netbanking).</p>
                            </>
                        )}
                    </section>
                )}

                {stage === "verifying" && (
                    <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center dark:border-slate-800 dark:bg-slate-900">
                        <Loader2 className="mx-auto mb-3 h-8 w-8 animate-spin text-slate-400" />
                        <p className="text-sm text-slate-600 dark:text-slate-300">Confirming your payment. Please do not close this page.</p>
                    </section>
                )}

                {stage === "success" && (
                    <section className="rounded-2xl border border-emerald-200 bg-white p-8 text-center dark:border-emerald-900 dark:bg-slate-900">
                        <CheckCircle2 className="mx-auto mb-3 h-10 w-10 text-emerald-500" />
                        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Payment received</h1>
                        <p className="mt-1 text-sm text-slate-500">Thank you. {receipt ? `Your receipt number is ${receipt}.` : "The school has recorded your payment."}</p>
                    </section>
                )}

                {stage === "pending" && (
                    <section className="rounded-2xl border border-amber-200 bg-white p-8 text-center dark:border-amber-900 dark:bg-slate-900">
                        <h1 className="text-xl font-semibold text-slate-900 dark:text-white">Payment is being confirmed</h1>
                        <p className="mt-2 text-sm text-slate-500">{message}</p>
                    </section>
                )}
            </div>
        </main>
    );
}
