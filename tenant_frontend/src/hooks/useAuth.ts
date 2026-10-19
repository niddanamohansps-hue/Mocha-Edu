import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { AuthResponse, User } from "@/types/auth";
import { toast } from "sonner";

async function login(credentials: any): Promise<AuthResponse> {
    const { data } = await axiosInstance.post<AuthResponse>("/auth/login/", credentials);
    return data;
}

async function logout(): Promise<void> {
    await axiosInstance.post("/auth/logout/");
}

async function getMe(active_role?: string | null): Promise<User> {
    const url = active_role ? `/auth/me/?active_role=${active_role}` : "/auth/me/";
    const { data } = await axiosInstance.get<User>(url);
    return data;
}

export function useLogin() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: login,
        onSuccess: () => {
            queryClient.clear();
            localStorage.removeItem("active_role");
            toast.success("Logged in successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.detail || "Login failed");
        }
    });
}

export function useLogout() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: logout,
        onSuccess: () => {
            queryClient.clear();
            localStorage.removeItem("active_role");
            toast.success("Logged out successfully");
            window.location.href = "/login";
        },
        onError: () => {
            // Even if the server logout endpoint fails (e.g. token expired/invalid),
            // purge local cache and redirect to login to prevent stale data retention.
            queryClient.clear();
            localStorage.removeItem("active_role");
            window.location.href = "/login";
        }
    });
}

export function useMe() {
    const active_role = typeof window !== 'undefined' ? localStorage.getItem("active_role") : null;

    return useQuery({
        queryKey: ["me", active_role],
        queryFn: () => getMe(active_role),
        retry: false,
        staleTime: 1000 * 60 * 5, // 5 minutes
    });
}

export function useChangePassword() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (newPassword: string) => {
            const { data } = await axiosInstance.post("/auth/change-password/", {
                new_password: newPassword
            });
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["me"] });
            toast.success("Password updated successfully!");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.error || "Failed to update password");
        }
    });
}

export function useForgotPassword() {
    return useMutation({
        mutationFn: async (email: string) => {
            const { data } = await axiosInstance.post("/auth/forgot-password/", { email });
            return data;
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.error || "Something went wrong. Please try again.");
        }
    });
}

export function useResetPasswordConfirm() {
    return useMutation({
        mutationFn: async (payload: { uid: string; token: string; new_password: string }) => {
            const { data } = await axiosInstance.post("/auth/reset-password-confirm/", payload);
            return data;
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.error || "Failed to reset password.");
        }
    });
}
