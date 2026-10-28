import { GatewayPayload } from "@/types/Fees";

/**
 * Dynamically builds and submits an auto-submitting POST form to redirect
 * the browser to the payment gateway (e.g. eSewa v2) using exclusively
 * the server-validated and server-signed parameters.
 */
export function submitGatewayForm(payload: GatewayPayload) {
    if (typeof window === "undefined") return;

    const form = document.createElement("form");
    form.method = payload.method || "POST";
    form.action = payload.gateway_url;
    form.style.display = "none";

    for (const [key, value] of Object.entries(payload.form_parameters)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = key;
        input.value = String(value);
        form.appendChild(input);
    }

    document.body.appendChild(form);
    form.submit();
}


interface RazorpayResponse {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
}

interface RazorpayInstance {
    open: () => void;
}

type RazorpayConstructor = new (options: Record<string, unknown>) => RazorpayInstance;

const CHECKOUT_SCRIPT = "https://checkout.razorpay.com/v1/checkout.js";

function loadRazorpayCheckout(): Promise<RazorpayConstructor> {
    const existing = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
    if (existing) return Promise.resolve(existing);
    return new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = CHECKOUT_SCRIPT;
        script.async = true;
        script.onload = () => {
            const loaded = (window as unknown as { Razorpay?: RazorpayConstructor }).Razorpay;
            if (loaded) resolve(loaded);
            else reject(new Error("Razorpay Checkout did not load."));
        };
        script.onerror = () => reject(new Error("Razorpay Checkout could not be loaded. Check the internet connection."));
        document.body.appendChild(script);
    });
}

/**
 * Opens Razorpay Checkout over the page (UPI, cards, netbanking, wallets) using only the parameters the
 * server created. On success ``onPaid`` receives Razorpay's signed answer for the return page, where the
 * server checks it before anything is marked paid.
 */
export async function openRazorpayCheckout(
    payload: GatewayPayload,
    options: {
        description: string;
        prefill?: { name?: string; email?: string; contact?: string };
        /** Called with the query string for the return page (our order id plus Razorpay's signed answer). */
        onPaid: (query: string) => void;
        onDismiss: () => void;
    }
) {
    const Razorpay = await loadRazorpayCheckout();
    const p = payload.form_parameters;
    const checkout = new Razorpay({
        key: p.key,
        order_id: p.order_id,
        amount: p.amount,
        currency: p.currency,
        name: p.school_name || undefined,
        description: options.description,
        prefill: {
            name: p.prefill_name || undefined,
            email: p.prefill_email || undefined,
            contact: p.prefill_contact || undefined,
            ...options.prefill,
        },
        handler: (response: RazorpayResponse) => {
            const query = new URLSearchParams({
                order_id: payload.order_id,
                razorpay_order_id: response.razorpay_order_id,
                razorpay_payment_id: response.razorpay_payment_id,
                razorpay_signature: response.razorpay_signature,
            });
            options.onPaid(query.toString());
        },
        modal: { ondismiss: options.onDismiss, confirm_close: true },
        theme: { color: "#059669" },
    });
    checkout.open();
}
