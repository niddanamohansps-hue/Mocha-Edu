import { useMutation } from "@tanstack/react-query";
import { toast } from "sonner";
import { RegisterOrganizationPayload, RegisterOrganizationResponse, InitPaymentPayload, InitPaymentResponse } from "@/types/payment";
import axiosInstance from "@/lib/axios";

async function registerOrganization(payload: RegisterOrganizationPayload): Promise<RegisterOrganizationResponse> {
    const { data } = await axiosInstance.post<RegisterOrganizationResponse>("/auth/register-organization/", payload);
    return data;
}

async function initPayment(payload: InitPaymentPayload): Promise<InitPaymentResponse> {
    const { data } = await axiosInstance.post<InitPaymentResponse>("/payments/init/", payload);
    return data;
}

export function useRegisterOrganization() {
    return useMutation({
        mutationFn: registerOrganization,
        onError: (error: Error) => {
            toast.error(error.message || "Registration failed. Please try again.");
        },
        onSuccess: (data) => {
            toast.success("Registration Successful!");
        },
    });
}

export function useInitPayment() {
    return useMutation({
        mutationFn: initPayment,
        onError: (error: Error) => {
            toast.error(error.message || "Payment initialization failed. Please try again.");
        },
    });
}

// The backend answers 202 while the institution is still being created. Asking again is safe (the
// setup is claimed once), so wait and ask a limited number of times before giving up.
const VERIFY_POLL_INTERVAL_MS = 3000;
const VERIFY_POLL_MAX_ATTEMPTS = 20;

type VerifyPaymentResponse = { message?: string; domain_url?: string };

async function verifyPayment(dataString: string): Promise<VerifyPaymentResponse> {
    for (let attempt = 1; attempt <= VERIFY_POLL_MAX_ATTEMPTS; attempt++) {
        const response = await axiosInstance.get(`/payments/verify/?data=${encodeURIComponent(dataString)}`);
        if (response.status !== 202) {
            return response.data;
        }
        await new Promise((resolve) => setTimeout(resolve, VERIFY_POLL_INTERVAL_MS));
    }
    throw new Error(
        "Your payment was received and your institution is still being set up. Please reload this page in a minute or contact support."
    );
}

export function useVerifyPayment() {
    return useMutation({
        mutationFn: verifyPayment,
        onError: (error: Error) => {
            toast.error(error.message || "Payment verification failed.");
        },
    });
}

async function verifyAccount(payload: { email?: string; username?: string; password?: string }): Promise<{ exists: boolean; email_exists: boolean; username_exists: boolean; valid_password: boolean }> {
    const { data } = await axiosInstance.post<{ exists: boolean; email_exists: boolean; username_exists: boolean; valid_password: boolean }>("/auth/verify-account/", payload);
    return data;
}

export function useVerifyAccount() {
    return useMutation({
        mutationFn: verifyAccount,
    });
}

async function checkDomain(subdomain: string): Promise<{ exists: boolean }> {
    const { data } = await axiosInstance.get<{ exists: boolean }>(`/organizations/check-domain/?domain=${subdomain}`);
    return data;
}

export function useCheckDomain() {
    return useMutation({
        mutationFn: checkDomain,
    });
}
