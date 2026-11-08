import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import axiosInstance from "@/lib/axios";
import type { ChecklistRow, DocumentItem, DocumentStatus, DocumentType } from "@/types/StaffDocuments";

const KEY = "staff-documents";

function message(error: unknown, fallback: string): string {
    const data = (error as { response?: { data?: unknown } })?.response?.data;
    if (Array.isArray(data) && data.length) return String(data[0]);
    if (data && typeof data === "object") {
        const first = Object.values(data as Record<string, unknown>)[0];
        if (Array.isArray(first) && first.length) return String(first[0]);
        if (typeof first === "string") return first;
    }
    return fallback;
}

function useChange<TVars>(run: (vars: TVars) => Promise<unknown>, success: string, failure: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: run,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success(success);
        },
        onError: (error: unknown) => toast.error(message(error, failure)),
    });
}

export const useDocumentTypes = () =>
    useQuery({ queryKey: [KEY, "types"], queryFn: async () => (await axiosInstance.get<DocumentType[]>("/staff/document-types/")).data });

export const useChecklistOverview = (outstanding: boolean) =>
    useQuery({
        queryKey: [KEY, "overview", outstanding],
        queryFn: async () =>
            (await axiosInstance.get<ChecklistRow[]>("/staff/document-checklists/", { params: outstanding ? { outstanding: "true" } : {} })).data,
    });

export const useMemberDocuments = (staff: string | null) =>
    useQuery({
        queryKey: [KEY, "member", staff],
        enabled: !!staff,
        queryFn: async () => (await axiosInstance.get<DocumentItem[]>(`/staff/member-documents/${staff}/`)).data,
    });

export const useAddDocumentType = () =>
    useChange(async (name: string) => axiosInstance.post("/staff/document-types/", { name }), "Added to the standard list", "Could not add it");

export const useUpdateDocumentType = () =>
    useChange(
        async (vars: { id: string; is_active: boolean }) => axiosInstance.patch(`/staff/document-types/${vars.id}/`, { is_active: vars.is_active }),
        "Saved",
        "Could not save",
    );

/** Give a staff member the standard checklist (no name) or add a one-off item (a name). */
export const useAddMemberDocument = () =>
    useChange(
        async (vars: { staff: string; name?: string }) => axiosInstance.post(`/staff/member-documents/${vars.staff}/`, { name: vars.name ?? "" }),
        "Checklist updated",
        "Could not update the checklist",
    );

export const useUpdateDocumentItem = () =>
    useChange(
        async (vars: { id: string; status: DocumentStatus; note?: string; received_on?: string }) => {
            const { id, ...body } = vars;
            return axiosInstance.patch(`/staff/document-items/${id}/`, body);
        },
        "Saved",
        "Could not save",
    );

export const useUploadDocumentFile = () =>
    useChange(
        async (vars: { id: string; file: File }) => {
            const form = new FormData();
            form.append("file", vars.file);
            return axiosInstance.post(`/staff/document-items/${vars.id}/`, form);
        },
        "File attached and marked received",
        "Could not upload the file",
    );

/** Opens the scanned file in a new tab through the permission-checked endpoint. */
export async function openDocumentFile(id: string) {
    try {
        const response = await axiosInstance.get(`/staff/document-items/${id}/`, { responseType: "blob" });
        const url = URL.createObjectURL(response.data as Blob);
        window.open(url, "_blank");
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
        toast.error(message(error, "Could not open the file"));
    }
}
