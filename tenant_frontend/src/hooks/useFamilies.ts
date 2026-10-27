import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type { PaginatedResponse } from "@/types/Pagination";
import type {
    Parent,
    ParentFormData,
    StudentParentRelation,
    LinkChildFormData,
    ParentPortalActivationData,
    ParentPendingCredential,
} from "@/types/Families";

function getErrorMessage(error: unknown, fallback: string): string {
    if (typeof error === "object" && error !== null && "response" in error) {
        const resp = (error as { response?: { data?: Record<string, unknown> | string } }).response;
        const data = resp?.data;
        if (typeof data === "string") return data;
        if (typeof data === "object" && data !== null) {
            if ("detail" in data && typeof data.detail === "string") return data.detail;
            if ("message" in data && typeof data.message === "string") return data.message;
            if ("non_field_errors" in data && Array.isArray(data.non_field_errors)) {
                return String(data.non_field_errors[0]);
            }
            const firstVal = Object.values(data)[0];
            if (Array.isArray(firstVal) && firstVal.length > 0) return String(firstVal[0]);
            if (typeof firstVal === "string") return firstVal;
        }
    }
    return fallback;
}

interface UseParentsOptions {
    page?: number;
    pageSize?: number;
    search?: string;
    student?: string;
}

export const useParents = (options: UseParentsOptions = {}) => {
    const { page = 1, pageSize = 20, search = "", student = "" } = options;
    return useQuery({
        queryKey: ["parents", { page, pageSize, search, student }],
        queryFn: async () => {
            const response = await axiosInstance.get("/families/parents/", {
                params: {
                    page,
                    page_size: pageSize,
                    ...(search ? { search } : {}),
                    ...(student ? { student } : {}),
                },
            });
            return response.data as PaginatedResponse<Parent>;
        },
    });
};

export const useParent = (id: string | null | undefined, enabled: boolean = true) => {
    return useQuery({
        queryKey: ["parent", id],
        queryFn: async () => {
            if (!id) return null;
            const response = await axiosInstance.get(`/families/parents/${id}/`);
            return response.data as Parent;
        },
        enabled: Boolean(id) && enabled,
    });
};

export const useCreateParent = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (data: ParentFormData) => {
            const response = await axiosInstance.post("/families/parents/", data);
            return response.data as Parent;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["parents"] });
            toast.success("Parent created successfully!");
        },
        onError: (error: unknown) => {
            toast.error(getErrorMessage(error, "Failed to create parent."));
        },
    });
};

export const useUpdateParent = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: Partial<ParentFormData> }) => {
            const response = await axiosInstance.patch(`/families/parents/${id}/`, data);
            return response.data as Parent;
        },
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["parents"] });
            queryClient.invalidateQueries({ queryKey: ["parent", variables.id] });
            toast.success("Parent details updated successfully!");
        },
        onError: (error: unknown) => {
            toast.error(getErrorMessage(error, "Failed to update parent details."));
        },
    });
};

export const useDeleteParent = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/families/parents/${id}/`);
            return id;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["parents"] });
            toast.success("Parent deleted successfully!");
        },
        onError: (error: unknown) => {
            toast.error(getErrorMessage(error, "Failed to delete parent."));
        },
    });
};

export const useStudentParentRelations = (options: { student?: string; parent?: string } = {}) => {
    const { student, parent } = options;
    return useQuery({
        queryKey: ["student-parent-relations", { student, parent }],
        queryFn: async () => {
            const response = await axiosInstance.get("/families/relations/", {
                params: {
                    ...(student ? { student } : {}),
                    ...(parent ? { parent } : {}),
                },
            });
            // StandardResultsPagination returns { count, results, ... }
            return (response.data?.results || response.data) as StudentParentRelation[];
        },
        enabled: Boolean(student || parent),
    });
};

export const useLinkChild = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (data: LinkChildFormData) => {
            const response = await axiosInstance.post("/families/relations/", data);
            return response.data as StudentParentRelation;
        },
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["parents"] });
            queryClient.invalidateQueries({ queryKey: ["parent", variables.parent] });
            queryClient.invalidateQueries({ queryKey: ["student-parent-relations"] });
            queryClient.invalidateQueries({ queryKey: ["student", variables.student] });
            toast.success("Child linked successfully!");
        },
        onError: (error: unknown) => {
            toast.error(getErrorMessage(error, "Failed to link child."));
        },
    });
};

export const useUpdateRelation = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({
            id,
            data,
        }: {
            id: number;
            data: Partial<LinkChildFormData>;
        }) => {
            const response = await axiosInstance.patch(`/families/relations/${id}/`, data);
            return response.data as StudentParentRelation;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["parents"] });
            queryClient.invalidateQueries({ queryKey: ["parent"] });
            queryClient.invalidateQueries({ queryKey: ["student-parent-relations"] });
            toast.success("Relationship updated successfully!");
        },
        onError: (error: unknown) => {
            toast.error(getErrorMessage(error, "Failed to update relationship."));
        },
    });
};

export const useUnlinkChild = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (relationId: number) => {
            await axiosInstance.delete(`/families/relations/${relationId}/`);
            return relationId;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["parents"] });
            queryClient.invalidateQueries({ queryKey: ["parent"] });
            queryClient.invalidateQueries({ queryKey: ["student-parent-relations"] });
            toast.success("Child unlinked successfully!");
        },
        onError: (error: unknown) => {
            toast.error(getErrorMessage(error, "Failed to unlink child."));
        },
    });
};

export const useActivateParent = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (data: ParentPortalActivationData) => {
            const response = await axiosInstance.post("/families/activate-parent/", data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["parents"] });
            queryClient.invalidateQueries({ queryKey: ["parent-credentials"] });
            toast.success("Parent portal account activated successfully!");
        },
        onError: (error: unknown) => {
            toast.error(getErrorMessage(error, "Failed to activate parent portal account."));
        },
    });
};

export const useParentCredentials = () => {
    return useQuery({
        queryKey: ["parent-credentials"],
        queryFn: async () => {
            const response = await axiosInstance.get("/families/credentials-parents/");
            return response.data as ParentPendingCredential[];
        },
    });
};
