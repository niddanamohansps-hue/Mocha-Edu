import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import axiosInstance from "@/lib/axios";

export type BillingCycle = "monthly" | "yearly" | "one_time";

export interface MyBilling {
    subscription: {
        plan: string;
        plan_code: string;
        cycle: BillingCycle;
        status: "pending" | "trial" | "active" | "past_due" | "read_only" | "cancelled";
        status_label: string;
        is_legacy: boolean;
        trial_ends_at: string | null;
        paid_until: string | null;
        grace_ends_at: string | null;
        can_write: boolean;
        student_limit: number | null;
        autopay: boolean;
        cancel_at_period_end: boolean;
        billing_state: string;
        billing_gstin: string;
    } | null;
    invoices: BillingInvoice[];
}

export interface BillingInvoice {
    id: string;
    number: string;
    status: string;
    plan_name: string;
    cycle: BillingCycle;
    period_start: string;
    period_end: string | null;
    amount: string;
    gst_amount: string;
    total: string;
    paid_at: string;
}

interface Checkout {
    key: string;
    order_id?: string;
    subscription_id?: string;
    amount?: number;
    currency?: string;
    name: string;
    description: string;
    prefill: Record<string, string>;
}

const errorText = (error: unknown, fallback: string) =>
    (error as { response?: { data?: { error?: string } } })?.response?.data?.error ?? fallback;

export const useMyBilling = () =>
    useQuery({
        queryKey: ["billing", "my"],
        queryFn: async () => (await axiosInstance.get<MyBilling>("/billing/my/")).data,
    });

type RazorpayConstructor = new (options: Record<string, unknown>) => { open: () => void };

async function loadCheckout(): Promise<RazorpayConstructor> {
    const existing = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
    if (existing) return existing;
    await new Promise<void>((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://checkout.razorpay.com/v1/checkout.js";
        script.onload = () => resolve();
        script.onerror = () => reject(new Error("The payment window could not be loaded."));
        document.body.appendChild(script);
    });
    const loaded = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
    if (!loaded) throw new Error("The payment window could not be loaded.");
    return loaded;
}

function openCheckout(checkout: Checkout, onPaid: (response: Record<string, string>) => void, onDismiss: () => void) {
    return loadCheckout().then((Razorpay) =>
        new Razorpay({ ...checkout, handler: onPaid, modal: { ondismiss: onDismiss }, theme: { color: "#059669" } }).open()
    );
}

/** Pay the next period now (or a one-time purchase), confirmed by the server with Razorpay. */
export const usePayNow = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (cycle?: BillingCycle) => {
            const start = (await axiosInstance.post<{ checkout: Checkout }>("/billing/my/pay/", cycle ? { cycle } : {})).data;
            return new Promise<string>((resolve, reject) => {
                openCheckout(
                    start.checkout,
                    async (response) => {
                        try {
                            const result = (await axiosInstance.post<{ status: string }>("/billing/my/pay/confirm/", response)).data;
                            resolve(result.status);
                        } catch (error) {
                            reject(error);
                        }
                    },
                    () => reject(new Error("cancelled"))
                ).catch(reject);
            });
        },
        onSuccess: (status) => {
            queryClient.invalidateQueries({ queryKey: ["billing"] });
            toast.success(status === "paid" ? "Payment received. Thank you!" : "Payment received; confirming it with the bank.");
        },
        onError: (error) => {
            if (error instanceof Error && error.message === "cancelled") toast.info("Payment cancelled. Nothing was charged.");
            else toast.error(errorText(error, "The payment could not be completed."));
        },
    });
};

/** Authorise automatic renewal (UPI AutoPay or card mandate). */
export const useStartAutopay = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async () => {
            const start = (await axiosInstance.post<{ checkout: Checkout }>("/billing/my/autopay/")).data;
            return new Promise<void>((resolve, reject) => {
                openCheckout(start.checkout, () => resolve(), () => reject(new Error("cancelled"))).catch(reject);
            });
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["billing"] });
            toast.success("Automatic renewal is set up.");
        },
        onError: (error) => {
            if (error instanceof Error && error.message === "cancelled") toast.info("Automatic renewal was not set up.");
            else toast.error(errorText(error, "Automatic renewal could not be set up."));
        },
    });
};

export const useCancelAutopay = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async () => (await axiosInstance.post("/billing/my/autopay/cancel/")).data,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["billing"] });
            toast.success("Automatic renewal stopped. Access continues until the end of the paid period.");
        },
        onError: (error) => toast.error(errorText(error, "Could not stop automatic renewal.")),
    });
};

export async function downloadInvoice(invoice: BillingInvoice) {
    const response = await axiosInstance.get(`/billing/my/invoices/${invoice.id}/pdf/`, { responseType: "blob" });
    const url = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `invoice-${invoice.number.replace(/\//g, "-")}.pdf`;
    link.click();
    URL.revokeObjectURL(url);
}
