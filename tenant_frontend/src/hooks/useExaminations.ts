import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type { PaginatedResponse } from "@/types/Pagination";
import {
    BelowPassingReport,
    CoScholasticActivity,
    CoScholasticGrade,
    ExamComponentMark,
    ExamScheduleComponent,
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
    MarkChange,
    MarksImportResult,
    RecheckRequest,
    RecheckStatus,
    SavedMark,
    ScheduleMarks,
    TermWeightage,
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
        // A bare true/false changes two-person publishing (as before); an object changes the settings it names.
        mutationFn: async (change: boolean | Partial<Pick<ExaminationSettings, "require_separate_publisher" | "show_rank_to_families" | "report_card_style" | "recheck_fee">>) =>
            (await axiosInstance.patch(
                "/examinations/settings/",
                typeof change === "boolean" ? { require_separate_publisher: change } : change,
            )).data as ExaminationSettings,
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

export const usePublishDateSheet = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            const response = await axiosInstance.post(`/examinations/examinations/${id}/publish-date-sheet/`);
            return response.data as Examination;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Date sheet announced to students and parents");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to announce the date sheet")),
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
        mutationFn: async ({ scheduleId, records, reason }: { scheduleId: string; records: ExamMarkRecordInput[]; reason?: string }) => {
            const response = await axiosInstance.post(`/examinations/schedules/${scheduleId}/marks/`, { records, reason: reason ?? "" });
            return response.data as ExamSchedule;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Marks saved");
        },
        onError: (error: any) => {
            if (error.response?.status === 423) {
                toast.error(errorMessage(error, "This exam schedule is locked and cannot be edited."));
            } else {
                toast.error(errorMessage(error, "Failed to save marks"));
            }
        },
    });
};

export const useScheduleMarks = (scheduleId: string | undefined) =>
    useQuery({
        queryKey: ["examinations", "marks", scheduleId],
        queryFn: async () => (await axiosInstance.get(`/examinations/schedules/${scheduleId}/marks/`)).data as ScheduleMarks,
        enabled: !!scheduleId,
    });

export const useMarksHistory = (scheduleId: string | undefined, enabled: boolean) =>
    useQuery({
        queryKey: ["examinations", "marks-history", scheduleId],
        queryFn: async () => (await axiosInstance.get(`/examinations/schedules/${scheduleId}/history/`)).data as MarkChange[],
        enabled: !!scheduleId && enabled,
    });

/** Sends a CSV of marks. With dryRun the server only checks it and returns a preview. Errors come back as a list. */
export const useImportMarks = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ scheduleId, file, dryRun, reason }: { scheduleId: string; file: File; dryRun: boolean; reason?: string }) => {
            const form = new FormData();
            form.append("file", file);
            form.append("dry_run", dryRun ? "true" : "false");
            form.append("reason", reason ?? "");
            return (await axiosInstance.post(`/examinations/schedules/${scheduleId}/marks-import/`, form, {
                headers: { "Content-Type": "multipart/form-data" },
            })).data as MarksImportResult;
        },
        onSuccess: (data) => {
            if (!data.dry_run) {
                queryClient.invalidateQueries({ queryKey: ["examinations"] });
                toast.success(`Imported: ${data.created ?? 0} new, ${data.changed ?? 0} changed`);
            }
        },
    });
};

export const importErrors = (error: unknown): string[] => {
    const errors = (error as { response?: { data?: { errors?: unknown } } })?.response?.data?.errors;
    return Array.isArray(errors) ? errors.map(String) : [errorMessage(error, "Could not read the file")];
};

export const useSetGrace = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ markId, grace_marks, reason }: { markId: string; grace_marks: string; reason: string }) =>
            (await axiosInstance.post(`/examinations/marks/${markId}/grace/`, { grace_marks, reason })).data as SavedMark,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Grace marks saved");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not save grace marks")),
    });
};

export const useRechecks = (status: RecheckStatus | "", page: number) =>
    useQuery({
        queryKey: ["examinations", "rechecks", status, page],
        queryFn: async () =>
            (await axiosInstance.get("/examinations/rechecks/", { params: { ...(status ? { status } : {}), page } })).data as PaginatedResponse<RecheckRequest>,
    });

export const useRequestRecheck = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (input: { mark?: string; examination?: string; subject?: string; student?: string; reason: string }) =>
            (await axiosInstance.post("/examinations/rechecks/", input)).data as RecheckRequest,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "rechecks"] });
            toast.success("Recheck requested");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not request a recheck")),
    });
};

export const useCollectRecheckFee = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, reference }: { id: string; reference: string }) =>
            (await axiosInstance.post(`/examinations/rechecks/${id}/collect-fee/`, { reference })).data as RecheckRequest,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "rechecks"] });
            toast.success("Fee recorded as received");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not record the fee")),
    });
};

export const useDecideRecheck = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, ...body }: { id: string; decision: "accept" | "reject"; revised_marks?: string; decision_comment: string }) =>
            (await axiosInstance.post(`/examinations/rechecks/${id}/decide/`, body)).data as RecheckRequest,
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success(data.status === "accepted" ? "Recheck accepted" : "Recheck rejected");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not save the decision")),
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

// === STAGE C: SCHEDULE COMPONENTS ===

export const useExamScheduleComponents = (scheduleId?: string) => {
    return useQuery({
        queryKey: ["examinations", "components", scheduleId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/examinations/components/?exam_schedule=${scheduleId}`);
            return response.data as ExamScheduleComponent[];
        },
        enabled: !!scheduleId,
    });
};

export const useCreateExamScheduleComponent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<ExamScheduleComponent>) => {
            const response = await axiosInstance.post("/examinations/components/", data);
            return response.data as ExamScheduleComponent;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Component created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create component")),
    });
};

export const useDeleteExamScheduleComponent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/examinations/components/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Component deleted");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to delete component")),
    });
};

// === STAGE C: TERM WEIGHTAGES ===

export const useTermWeightages = (academicYear?: string, levelId?: string) => {
    return useQuery({
        queryKey: ["examinations", "term-weightages", academicYear, levelId],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (academicYear) params.append("academic_year", academicYear);
            if (levelId) params.append("level", levelId);
            const response = await axiosInstance.get(`/examinations/term-weightages/?${params.toString()}`);
            return response.data as TermWeightage[];
        },
        enabled: !!academicYear,
    });
};

export const useCreateTermWeightage = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<TermWeightage>) => {
            const response = await axiosInstance.post("/examinations/term-weightages/", data);
            return response.data as TermWeightage;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "term-weightages"] });
            toast.success("Term weightage saved");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to save term weightage")),
    });
};

export const useDeleteTermWeightage = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/examinations/term-weightages/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "term-weightages"] });
            toast.success("Term weightage deleted");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to delete term weightage")),
    });
};

// === STAGE C: CO-SCHOLASTIC ACTIVITIES & GRADES ===

export const useCoScholasticActivities = () => {
    return useQuery({
        queryKey: ["examinations", "co-scholastic", "activities"],
        queryFn: async () => {
            const response = await axiosInstance.get("/examinations/co-scholastic/activities/");
            return response.data as CoScholasticActivity[];
        },
    });
};

export const useCreateCoScholasticActivity = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<CoScholasticActivity>) => {
            const response = await axiosInstance.post("/examinations/co-scholastic/activities/", data);
            return response.data as CoScholasticActivity;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "co-scholastic", "activities"] });
            toast.success("Co-scholastic activity created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create activity")),
    });
};

export const useCoScholasticGrades = (examinationId?: string, studentId?: string) => {
    return useQuery({
        queryKey: ["examinations", "co-scholastic", "grades", examinationId, studentId],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (examinationId) params.append("examination", examinationId);
            if (studentId) params.append("student", studentId);
            const response = await axiosInstance.get(`/examinations/co-scholastic/grades/?${params.toString()}`);
            return response.data as CoScholasticGrade[];
        },
        enabled: !!examinationId,
    });
};

export const useBulkSubmitCoScholasticGrades = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: { examination: string; records: { student: string; activity: string; grade: string; remarks?: string }[] }) => {
            const response = await axiosInstance.post("/examinations/co-scholastic/grades/bulk/", data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["examinations", "co-scholastic"] });
            toast.success("Co-scholastic grades saved");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to save co-scholastic grades")),
    });
};
