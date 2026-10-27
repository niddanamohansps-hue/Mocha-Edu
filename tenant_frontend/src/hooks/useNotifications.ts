import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import {
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationListResponse,
    NotificationSettings,
    UnreadCountResponse,
    AlertLogItem,
    AlertLogFilters,
} from "@/types/Notifications";
import type { PaginatedResponse } from "@/types/Pagination";

function errorMessage(error: unknown, fallback: string) {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data) return fallback;
    if (typeof data.error === "string") return data.error;
    for (const key of Object.keys(data)) {
        const value = data[key];
        if (Array.isArray(value) && value.length) return String(value[0]);
        if (typeof value === "string") return value;
    }
    return fallback;
}

// Client-side polling only, per the V1 decision (no WebSockets/SSE/push).
const UNREAD_COUNT_POLL_INTERVAL_MS = 30_000;

export const useNotifications = (page: number = 1) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: ["notifications", "list", user?.id, page],
        queryFn: async () => {
            const response = await axiosInstance.get(`/notifications/?page=${page}`);
            return response.data as NotificationListResponse;
        },
        enabled: !!user,
    });
};

export const useUnreadCount = () => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: ["notifications", "unread-count", user?.id],
        queryFn: async () => {
            const response = await axiosInstance.get("/notifications/unread-count/");
            return response.data as UnreadCountResponse;
        },
        enabled: !!user,
        refetchInterval: UNREAD_COUNT_POLL_INTERVAL_MS,
    });
};

export const useMarkNotificationRead = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (notificationId: string) => {
            const response = await axiosInstance.post(`/notifications/${notificationId}/read/`);
            return response.data as MarkReadResponse;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["notifications", "list"] });
            queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Failed to mark notification as read")),
    });
};

export const useMarkAllNotificationsRead = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async () => {
            const response = await axiosInstance.post("/notifications/mark-all-read/");
            return response.data as MarkAllReadResponse;
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["notifications", "list"] });
            queryClient.invalidateQueries({ queryKey: ["notifications", "unread-count"] });
            if (data.updated_count > 0) {
                toast.success(`Marked ${data.updated_count} notification(s) as read`);
            }
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Failed to mark all as read")),
    });
};

export const useNotificationSettings = () => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: ["notifications", "settings", user?.id],
        queryFn: async () => (await axiosInstance.get("/notifications/settings/")).data as NotificationSettings,
        enabled: !!user,
    });
};

export const useUpdateNotificationSettings = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (input: Partial<NotificationSettings>) =>
            (await axiosInstance.patch("/notifications/settings/", input)).data as NotificationSettings,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["notifications", "settings"] });
            toast.success("Settings saved");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not save the settings")),
    });
};


export const useAlertLog = (filters: AlertLogFilters = {}) => {
    const { page = 1, pageSize = 20, kind, created_after, created_before, enrollment_id } = filters;
    return useQuery({
        queryKey: ["notifications", "alert-log", { page, pageSize, kind, created_after, created_before, enrollment_id }],
        queryFn: async () => {
            const response = await axiosInstance.get("/notifications/alert-log/", {
                params: {
                    page,
                    page_size: pageSize,
                    ...(kind ? { kind } : {}),
                    ...(created_after ? { created_after } : {}),
                    ...(created_before ? { created_before } : {}),
                    ...(enrollment_id ? { enrollment_id } : {}),
                },
            });
            return response.data as PaginatedResponse<AlertLogItem>;
        },



    });
};
