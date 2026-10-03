import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type { PaginatedResponse } from "@/types/Pagination";
import {
    PromotionBatchInput,
    PromotionCandidate,
    PromotionExecuteResponse,
    PromotionPreviewResult,
    PromotionRecord,
} from "@/types/Promotion";

function errorMessage(error: any, fallback: string) {
    const data = error.response?.data;
    if (!data) return fallback;
    if (typeof data.error === "string") return data.error;
    for (const key of Object.keys(data)) {
        const value = data[key];
        if (Array.isArray(value) && value.length) return String(value[0]);
        if (typeof value === "string") return value;
    }
    return fallback;
}

export const usePromotionCandidates = (academicYear: string, levelId: string, sectionId?: string) => {
    return useQuery({
        queryKey: ["promotion", "candidates", academicYear, levelId, sectionId],
        queryFn: async () => {
            const params = new URLSearchParams({ academic_year: academicYear, level: levelId });
            if (sectionId) params.set("section", sectionId);
            const response = await axiosInstance.get(`/students/promotion/candidates/?${params.toString()}`);
            return response.data as PromotionCandidate[];
        },
        enabled: !!academicYear && !!levelId,
    });
};

export const usePreviewPromotion = () => {
    return useMutation({
        mutationFn: async (data: PromotionBatchInput) => {
            const response = await axiosInstance.post("/students/promotion/preview/", data);
            return response.data as PromotionPreviewResult[];
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to preview promotion")),
    });
};

export const useExecutePromotion = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: PromotionBatchInput) => {
            const response = await axiosInstance.post("/students/promotion/execute/", data);
            return response.data as PromotionExecuteResponse;
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["promotion"] });
            queryClient.invalidateQueries({ queryKey: ["students"] });
            const successCount = data.results.filter((r) => r.status === "success").length;
            const skippedCount = data.results.filter((r) => r.status === "skipped").length;
            if (successCount > 0) {
                toast.success(`${successCount} student(s) processed successfully.`);
            }
            if (skippedCount > 0) {
                toast.error(`${skippedCount} student(s) skipped - see summary for details.`);
            }
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to execute promotion")),
    });
};

export const usePromotionHistory = (
    filters?: { student?: string; academic_year?: string; action?: string },
    page: number = 1,
    pageSize: number = 20
) => {
    return useQuery({
        queryKey: ["promotion", "history", filters, page, pageSize],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (filters?.student) params.set("student", filters.student);
            if (filters?.academic_year) params.set("academic_year", filters.academic_year);
            if (filters?.action) params.set("action", filters.action);
            params.set("page", String(page));
            params.set("page_size", String(pageSize));
            const response = await axiosInstance.get(`/students/promotion/history/?${params.toString()}`);
            return response.data as PaginatedResponse<PromotionRecord>;
        },
    });
};

export const useReversePromotion = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ recordId, reason }: { recordId: string; reason?: string }) => {
            const response = await axiosInstance.post(`/students/promotion/${recordId}/reverse/`, { reason });
            return response.data as PromotionRecord;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["promotion"] });
            queryClient.invalidateQueries({ queryKey: ["students"] });
            toast.success("Promotion reversed");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to reverse promotion")),
    });
};
