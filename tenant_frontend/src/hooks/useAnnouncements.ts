import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { PaginatedResponse } from "@/types/Pagination";
import {
    Announcement,
    AnnouncementFilters,
    AnnouncementInput,
    AnnouncementRecipient,
    MyAnnouncement,
} from "@/types/Announcements";

export function announcementErrorMessage(error: unknown, fallback: string) {
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

const KEY = "announcements";

export const useAnnouncements = (filters: AnnouncementFilters) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "list", user?.id, filters],
        queryFn: async () => {
            const params: Record<string, string | number> = { page: filters.page };
            if (filters.status) params.status = filters.status;
            if (filters.audience_type) params.audience_type = filters.audience_type;
            if (filters.search) params.search = filters.search;
            const response = await axiosInstance.get("/announcements/", { params });
            return response.data as PaginatedResponse<Announcement>;
        },
        enabled: !!user,
    });
};

export const useAnnouncement = (id: string) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "detail", user?.id, id],
        queryFn: async () => (await axiosInstance.get(`/announcements/${id}/`)).data as Announcement,
        enabled: !!user && !!id,
    });
};

export const useAnnouncementRecipients = (id: string, page: number, enabled: boolean) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "recipients", user?.id, id, page],
        queryFn: async () =>
            (await axiosInstance.get(`/announcements/${id}/recipients/`, { params: { page } }))
                .data as PaginatedResponse<AnnouncementRecipient>,
        enabled: !!user && !!id && enabled,
    });
};

export const useMyAnnouncements = (page: number) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "mine", user?.id, page],
        queryFn: async () =>
            (await axiosInstance.get("/announcements/mine/", { params: { page } }))
                .data as PaginatedResponse<MyAnnouncement>,
        enabled: !!user,
    });
};

export const useMyAnnouncement = (id: string) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "mine-detail", user?.id, id],
        queryFn: async () => (await axiosInstance.get(`/announcements/mine/${id}/`)).data as MyAnnouncement,
        enabled: !!user && !!id,
        retry: false,
    });
};

function useInvalidate() {
    const queryClient = useQueryClient();
    return () => queryClient.invalidateQueries({ queryKey: [KEY] });
}

export const useCreateAnnouncement = () => {
    const invalidate = useInvalidate();
    return useMutation({
        mutationFn: async (input: AnnouncementInput) =>
            (await axiosInstance.post("/announcements/", input)).data as Announcement,
        onSuccess: () => {
            invalidate();
            toast.success("Draft saved");
        },
        onError: (error: unknown) => toast.error(announcementErrorMessage(error, "Failed to save announcement")),
    });
};

export const useUpdateAnnouncement = () => {
    const invalidate = useInvalidate();
    return useMutation({
        mutationFn: async ({ id, input }: { id: string; input: AnnouncementInput }) =>
            (await axiosInstance.patch(`/announcements/${id}/`, input)).data as Announcement,
        onSuccess: () => {
            invalidate();
            toast.success("Announcement updated");
        },
        onError: (error: unknown) => toast.error(announcementErrorMessage(error, "Failed to update announcement")),
    });
};

type Lifecycle = "publish" | "schedule" | "cancel" | "archive";

const LIFECYCLE_SUCCESS: Record<Lifecycle, string> = {
    publish: "Announcement published",
    schedule: "Announcement scheduled",
    cancel: "Schedule cancelled - the announcement is a draft again",
    archive: "Announcement archived",
};

export const useAnnouncementAction = () => {
    const invalidate = useInvalidate();
    return useMutation({
        mutationFn: async ({ id, action, scheduledAt }: { id: string; action: Lifecycle; scheduledAt?: string }) =>
            (
                await axiosInstance.post(
                    `/announcements/${id}/${action}/`,
                    action === "schedule" ? { scheduled_at: scheduledAt } : undefined
                )
            ).data as Announcement,
        onSuccess: (_data, variables) => {
            invalidate();
            toast.success(LIFECYCLE_SUCCESS[variables.action]);
        },
        onError: (error: unknown) => toast.error(announcementErrorMessage(error, "The action could not be completed")),
    });
};

export const useDeleteAnnouncement = () => {
    const invalidate = useInvalidate();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/announcements/${id}/`);
        },
        onSuccess: () => {
            invalidate();
            toast.success("Announcement removed");
        },
        onError: (error: unknown) => toast.error(announcementErrorMessage(error, "Failed to delete announcement")),
    });
};
