import { useQuery } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { useMe } from "@/hooks/useAuth";
import { PaginatedResponse } from "@/types/Pagination";
import { AuditLogItem, AuditLogFilters, AuditLogMetadata } from "@/types/AuditLog";

export function auditLogErrorMessage(error: unknown, fallback: string): string {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data || typeof data !== "object") return fallback;
    if (typeof data.detail === "string") return data.detail;
    for (const key of Object.keys(data)) {
        const value = data[key];
        const text = Array.isArray(value) ? value[0] : value;
        if (typeof text === "string") return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
    }
    return fallback;
}

const KEY = "audit-logs";

export const useAuditLogs = (filters: AuditLogFilters) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "list", user?.id, filters],
        queryFn: async () => {
            const params: Record<string, string | number> = { page: filters.page };
            if (filters.page_size) params.page_size = filters.page_size;
            if (filters.search) params.search = filters.search.trim();
            if (filters.actor_username) params.actor_username = filters.actor_username.trim();
            if (filters.action) params.action = filters.action;
            if (filters.model_name) params.model_name = filters.model_name;
            if (filters.object_id) params.object_id = filters.object_id.trim();
            if (filters.date_from) params.date_from = filters.date_from;
            if (filters.date_to) params.date_to = filters.date_to;
            if (filters.ordering) params.ordering = filters.ordering;

            const response = await axiosInstance.get("/audit-logs/", { params });
            return response.data as PaginatedResponse<AuditLogItem>;
        },
        enabled: !!user,
    });
};

export const useAuditLogDetail = (id: string | null) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "detail", user?.id, id],
        queryFn: async () => {
            if (!id) throw new Error("No audit log ID provided");
            const response = await axiosInstance.get(`/audit-logs/${id}/`);
            return response.data as AuditLogItem;
        },
        enabled: !!user && !!id,
    });
};

export const useAuditLogMetadata = () => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "metadata", user?.id],
        queryFn: async () => {
            const response = await axiosInstance.get("/audit-logs/metadata/");
            return response.data as AuditLogMetadata;
        },
        enabled: !!user,
        staleTime: 60 * 1000,
    });
};

