import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type { PaginatedResponse } from "@/types/Pagination";
import {
    BelowPassingReport,
    Examination,
    ExamMarkRecordInput,
    ExamResult,
    ExamSchedule,
    ExamScheduleInput,
    ExamType,
    GradeBoundary,
    OfficialTranscript,
    ReportCard,
    ExaminationSettings,
} from "@/types/Examinations";

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

// === EXAM TYPES ===

export const useExamTypes = () => {
    return useQuery({
        queryKey: ["examinations", "types"],
        queryFn: async () => {
            const response = await axiosInstance.get("/examinations/types/");
            return response.data as ExamType[];
        },
    });
};

export const useCreateExamType = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<ExamType>) => {
            const response = await axiosInstance.post("/examinations/types/", data);
            return response.data as ExamType;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "types"] });
            toast.success("Exam type created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create exam type")),
    });
};

// === EXAMINATIONS ===

export const useExaminations = (academicYear?: string) => {
    return useQuery({
        queryKey: ["examinations", "list", academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/examinations/examinations/${params}`);
            return response.data as Examination[];
        },
    });
};

export const useCreateExamination = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<Examination>) => {
            const response = await axiosInstance.post("/examinations/examinations/", data);
            return response.data as Examination;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "list"] });
            toast.success("Examination created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create examination")),
    });
};

export const useExaminationSettings = () =>
    useQuery({
        queryKey: ["examinations", "settings"],
        queryFn: async () => (await axiosInstance.get("/examinations/settings/")).data as ExaminationSettings,
    });

export const useUpdateExaminationSettings = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (require_separate_publisher: boolean) =>
            (await axiosInstance.patch("/examinations/settings/", { require_separate_publisher })).data as ExaminationSettings,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "settings"] });
            toast.success("Setting saved");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not save the setting")),
    });
};

export const useRequestPublication = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => (await axiosInstance.post(`/examinations/examinations/${id}/request-publication/`)).data as Examination,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Publication requested. Someone else can now publish the results.");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not request publication")),
    });
};

export const usePublishExamination = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            const response = await axiosInstance.post(`/examinations/examinations/${id}/publish/`);
            return response.data as Examination;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Examination published");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to publish examination")),
    });
};

// === SCHEDULES ===

export const useExamSchedules = (examinationId?: string) => {
    return useQuery({
        queryKey: ["examinations", "schedules", examinationId],
        queryFn: async () => {
            // Always scoped to one examination in practice (both current
            // consumers pass examinationId), which structurally bounds the
            // result to that exam's subject x section count - well under
            // the backend's max page_size, so a single page_size=100
            // request covers it without needing visible pagination UI here.
            const params: Record<string, string | number> = { page_size: 100 };
            if (examinationId) params.examination = examinationId;
            const response = await axiosInstance.get(`/examinations/schedules/`, { params });
            return (response.data as PaginatedResponse<ExamSchedule>).results;
        },
    });
};

export const useCreateExamSchedule = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: ExamScheduleInput) => {
            const response = await axiosInstance.post("/examinations/schedules/", data);
            return response.data as ExamSchedule;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "schedules"] });
            toast.success("Exam schedule created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create schedule")),
    });
};

export const useUpdateExamSchedule = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: Partial<ExamScheduleInput> }) => {
            const response = await axiosInstance.patch(`/examinations/schedules/${id}/`, data);
            return response.data as ExamSchedule;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "schedules"] });
            toast.success("Schedule updated");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to update schedule")),
    });
};

export const useDeleteExamSchedule = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/examinations/schedules/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "schedules"] });
            toast.success("Schedule deleted");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to delete schedule")),
    });
};

export const useLockExamSchedule = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, isLocked }: { id: string; isLocked: boolean }) => {
            const response = await axiosInstance.post(`/examinations/schedules/${id}/lock/`, { is_locked: isLocked });
            return response.data as ExamSchedule;
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "schedules"] });
            toast.success(data.is_locked ? "Schedule locked" : "Schedule unlocked");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to update lock status")),
    });
};

// === MARKS ===

export const useSubmitExamMarks = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ scheduleId, records }: { scheduleId: string; records: ExamMarkRecordInput[] }) => {
            const response = await axiosInstance.post(`/examinations/schedules/${scheduleId}/marks/`, { records });
            return response.data as ExamSchedule;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Marks saved");
        },
        onError: (error: any) => {
            if (error.response?.status === 423) {
                toast.error("This exam schedule is locked and cannot be edited.");
            } else {
                toast.error(errorMessage(error, "Failed to save marks"));
            }
        },
    });
};

// === RESULTS / REPORT CARD ===

export const useStudentResults = (studentId: string | undefined, academicYear?: string) => {
    return useQuery({
        queryKey: ["examinations", "results", studentId, academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/examinations/students/${studentId}/results/${params}`);
            return response.data as ExamResult[];
        },
        enabled: !!studentId,
    });
};

export const useStudentReportCard = (studentId: string | undefined, academicYear?: string) => {
    return useQuery({
        queryKey: ["examinations", "report-card", studentId, academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/examinations/students/${studentId}/report-card/${params}`);
            return response.data as ReportCard;
        },
        enabled: !!studentId,
    });
};

export const useStudentTranscript = (studentId: string | undefined) => {
    return useQuery({
        queryKey: ["examinations", "transcript", studentId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/examinations/students/${studentId}/transcript/`);
            return response.data as OfficialTranscript;
        },
        enabled: !!studentId,
    });
};

export const useBelowPassingReport = (examinationId: string | undefined) => {
    return useQuery({
        queryKey: ["examinations", "below-passing", examinationId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/examinations/reports/below-passing/?examination=${examinationId}`);
            return response.data as BelowPassingReport;
        },
        enabled: !!examinationId,
    });
};

// === GRADING ===

export const useGradeBoundaries = (academicYear?: string) => {
    return useQuery({
        queryKey: ["examinations", "grading", academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/examinations/grading/${params}`);
            return response.data as GradeBoundary[];
        },
    });
};

export const useCreateGradeBoundary = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<GradeBoundary>) => {
            const response = await axiosInstance.post("/examinations/grading/", data);
            return response.data as GradeBoundary;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "grading"] });
            toast.success("Grade boundary created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create grade boundary")),
    });
};

export const useDeleteGradeBoundary = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/examinations/grading/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "grading"] });
            toast.success("Grade boundary deleted");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to delete grade boundary")),
    });
};
