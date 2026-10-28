import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import axiosInstance from "@/lib/axios";

export interface HomeworkAttachment {
    id: string;
    original_name: string;
    size: number;
}

export interface Homework {
    id: string;
    section: string;
    section_name: string;
    subject: string;
    subject_name: string;
    title: string;
    details: string;
    assigned_on: string;
    due_date: string;
    status: "active" | "cancelled";
    created_by_name: string;
    attachments: HomeworkAttachment[];
    seen_count?: number;
    done_count?: number;
    seen_at?: string | null;
    done_at?: string | null;
    overdue?: boolean;
}

export interface HomeworkOption {
    section: string;
    section_name: string;
    subject: string;
    subject_name: string;
}

export interface HomeworkProgress {
    students: { student: string; enrollment_id: string; name: string; seen_at: string | null; done_at: string | null }[];
    seen: number;
    done: number;
}

const errorText = (error: unknown, fallback: string) => {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data) return fallback;
    if (typeof data.error === "string") return data.error;
    const first = Object.values(data)[0];
    return Array.isArray(first) ? String(first[0]) : fallback;
};

export const useHomeworkList = (params: { section?: string; page: number }) =>
    useQuery({
        queryKey: ["homework", "list", params],
        queryFn: async () =>
            (await axiosInstance.get("/homework/", { params: { ...(params.section ? { section: params.section } : {}), page: params.page } })).data as
                { count: number; next: string | null; previous: string | null; results: Homework[] },
    });

export const useHomeworkOptions = (enabled: boolean) =>
    useQuery({
        queryKey: ["homework", "options"],
        queryFn: async () => (await axiosInstance.get("/homework/options/")).data as HomeworkOption[],
        enabled,
    });

export const useMyHomework = (studentId: string | undefined, enabled: boolean) =>
    useQuery({
        queryKey: ["homework", "my", studentId ?? "self"],
        queryFn: async () =>
            (await axiosInstance.get("/homework/my/", { params: studentId ? { student: studentId } : {} })).data as
                { student: string; homework: Homework[] },
        enabled,
    });

export const useHomeworkProgress = (id: string | null) =>
    useQuery({
        queryKey: ["homework", "progress", id],
        queryFn: async () => (await axiosInstance.get(`/homework/${id}/progress/`)).data as HomeworkProgress,
        enabled: !!id,
    });

export const useHomeworkOverview = (date: string, enabled: boolean) =>
    useQuery({
        queryKey: ["homework", "overview", date],
        queryFn: async () => (await axiosInstance.get("/homework/overview/", { params: { date } })).data as
            { sections: { section: string; name: string; homework: number }[]; without_homework: number },
        enabled,
    });

export const useSetHomework = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ files, ...body }: { section: string; subject: string; title: string; details: string; due_date: string; files: File[] }) => {
            const homework = (await axiosInstance.post("/homework/", body)).data as Homework;
            for (const file of files) {
                const form = new FormData();
                form.append("file", file);
                try {
                    await axiosInstance.post(`/homework/${homework.id}/attachments/`, form, { headers: { "Content-Type": "multipart/form-data" } });
                } catch (error) {
                    toast.error(`${file.name}: ${errorText(error, "could not be attached")}`);
                }
            }
            return homework;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["homework"] });
            toast.success("Homework set. Students and parents have been notified.");
        },
        onError: (error) => toast.error(errorText(error, "Could not set the homework.")),
    });
};

export const useCancelHomework = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => (await axiosInstance.post(`/homework/${id}/cancel/`)).data,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["homework"] });
            toast.success("Homework cancelled.");
        },
        onError: (error) => toast.error(errorText(error, "Could not cancel the homework.")),
    });
};

export const useMarkHomework = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, student, done }: { id: string; student?: string; done?: boolean }) =>
            (await axiosInstance.post(`/homework/${id}/mark/`, { ...(student ? { student } : {}), ...(done === undefined ? {} : { done }) })).data,
        onSuccess: () => queryClient.invalidateQueries({ queryKey: ["homework", "my"] }),
        onError: (error) => toast.error(errorText(error, "Could not update the homework.")),
    });
};

export async function downloadAttachment(homeworkId: string, attachment: HomeworkAttachment, studentId?: string) {
    const response = await axiosInstance.get(`/homework/${homeworkId}/attachments/${attachment.id}/`, {
        responseType: "blob", params: studentId ? { student: studentId } : {},
    });
    const url = URL.createObjectURL(response.data as Blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = attachment.original_name;
    link.click();
    URL.revokeObjectURL(url);
}
