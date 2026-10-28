import { useMutation, useQuery } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";

export type BillingCycle = "monthly" | "yearly" | "one_time";

export interface Plan {
    code: string;
    name: string;
    description: string;
    features: string[];
    student_limit: number | null;
    monthly_price: string | null;
    yearly_price: string | null;
    one_time_price: string | null;
    one_time_validity_days: number | null;
    trial_days: number;
    gst_percent: string;
}

export interface SignupCheckout {
    gateway: "razorpay";
    key: string;
    order_id: string;
    amount: number;
    currency: string;
    name: string;
    description: string;
    prefill: { name?: string; email?: string; contact?: string };
}

export type SignupResult =
    | { status: "ready"; login_url: string }
    | { status: "setting_up" | "checking" }
    | { status: "pay"; checkout: SignupCheckout; total: string };

export interface PlanSignupPayload {
    plan: string;
    cycle: BillingCycle;
    organization_name: string;
    subdomain: string;
    username: string;
    email: string;
    password: string;
    phone: string;
}

export const CYCLE_LABEL: Record<BillingCycle, string> = { monthly: "Monthly", yearly: "Yearly", one_time: "One-time" };

export function priceFor(plan: Plan, cycle: BillingCycle): string | null {
    return cycle === "monthly" ? plan.monthly_price : cycle === "yearly" ? plan.yearly_price : plan.one_time_price;
}

/** "₹4,999" (whole rupees shown without paise). */
export function rupees(value: string | number): string {
    const n = Number(value);
    return `₹${n.toLocaleString("en-IN", { minimumFractionDigits: Number.isInteger(n) ? 0 : 2, maximumFractionDigits: 2 })}`;
}

export function oneTimeTerm(plan: Plan): string {
    if (!plan.one_time_validity_days) return "for life";
    const years = plan.one_time_validity_days / 365;
    return Number.isInteger(years) ? `for ${years} year${years > 1 ? "s" : ""}` : `for ${plan.one_time_validity_days} days`;
}

export const usePlans = () =>
    useQuery({
        queryKey: ["billing", "plans"],
        queryFn: async () => (await axiosInstance.get<Plan[]>("/billing/plans/")).data,
        staleTime: 5 * 60 * 1000,
    });

export const usePlanSignup = () =>
    useMutation({
        mutationFn: async (payload: PlanSignupPayload) =>
            (await axiosInstance.post<SignupResult>("/billing/signup/", payload)).data,
    });

export const useConfirmSignup = () =>
    useMutation({
        mutationFn: async (payload: { razorpay_order_id: string; razorpay_payment_id: string; razorpay_signature: string }) =>
            (await axiosInstance.post<SignupResult>("/billing/signup/confirm/", payload)).data,
    });

interface RazorpayResponse {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
}

type RazorpayConstructor = new (options: Record<string, unknown>) => { open: () => void };

function loadCheckout(): Promise<RazorpayConstructor> {
    const existing = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
    if (existing) return Promise.resolve(existing);
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = "https://checkout.razorpay.com/v1/checkout.js";
        script.async = true;
        script.onload = () => {
            const loaded = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
            if (loaded) resolve(loaded);
            else reject(new Error("The payment window did not load."));
        };
        script.onerror = () => reject(new Error("The payment window could not be loaded. Check the internet connection."));
        document.body.appendChild(script);
    });
}

/** Opens Razorpay Checkout for the signup payment created by the server. */
export async function openSignupCheckout(
    checkout: SignupCheckout,
    handlers: { onPaid: (response: RazorpayResponse) => void; onDismiss: () => void }
) {
    const Razorpay = await loadCheckout();
    new Razorpay({
        key: checkout.key,
        order_id: checkout.order_id,
        amount: checkout.amount,
        currency: checkout.currency,
        name: checkout.name,
        description: checkout.description,
        prefill: checkout.prefill,
        handler: handlers.onPaid,
        modal: { ondismiss: handlers.onDismiss, confirm_close: true },
        theme: { color: "#2563eb" },
    }).open();
}
