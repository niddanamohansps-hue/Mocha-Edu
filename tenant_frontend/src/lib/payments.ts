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

