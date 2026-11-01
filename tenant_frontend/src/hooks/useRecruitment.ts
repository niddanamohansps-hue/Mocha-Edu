import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type {
    Applicant,
    ApplicantEvent,
    ApplicantStage,
    Interview,
    JobOpening,
    PanelOption,
    RecruitmentSummary,
} from "@/types/Recruitment";

const KEY = "recruitment";

/** The API answers business-rule failures with a list of messages or a field map; show the first readable one. */
export function recruitmentError(error: unknown, fallback: string): string {
    const data = (error as { response?: { data?: unknown } })?.response?.data;
    if (typeof data === "string") return data;
    if (Array.isArray(data) && data.length) return String(data[0]);
    if (data && typeof data === "object") {
        const first = Object.values(data as Record<string, unknown>)[0];
        if (Array.isArray(first) && first.length) return String(first[0]);
        if (typeof first === "string") return first;
    }
    return fallback;
}

function useRecruitmentMutation<TVars, TResult = unknown>(
    run: (vars: TVars) => Promise<TResult>,
    success: string,
    failure: string,
) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: run,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success(success);
        },
        onError: (error: unknown) => toast.error(recruitmentError(error, failure)),
    });
}

export const useRecruitmentSummary = () =>
    useQuery({
        queryKey: [KEY, "summary"],
        queryFn: async () => (await axiosInstance.get<RecruitmentSummary>("/recruitment/summary/")).data,
    });

export const useOpenings = (params?: { status?: string }) =>
    useQuery({
        queryKey: [KEY, "openings", params],
        queryFn: async () => (await axiosInstance.get<JobOpening[]>("/recruitment/openings/", { params })).data,
    });

export const useSaveOpening = () =>
    useRecruitmentMutation(
        async (vars: { id?: string; data: Partial<JobOpening> }) =>
            vars.id
                ? (await axiosInstance.patch(`/recruitment/openings/${vars.id}/`, vars.data)).data
                : (await axiosInstance.post("/recruitment/openings/", vars.data)).data,
        "Opening saved",
        "Could not save the opening",
    );

export const useOpeningAction = () =>
    useRecruitmentMutation(
        async (vars: { id: string; action: "publish" | "close" }) =>
            (await axiosInstance.post(`/recruitment/openings/${vars.id}/${vars.action}/`)).data,
        "Opening updated",
        "Could not update the opening",
    );

export const useApplicants = (params?: { opening?: string; stage?: string; search?: string }) =>
    useQuery({
        queryKey: [KEY, "applicants", params],
        queryFn: async () => (await axiosInstance.get<Applicant[]>("/recruitment/applicants/", { params })).data,
    });

export const useApplicantHistory = (id: string | null) =>
    useQuery({
        queryKey: [KEY, "history", id],
        enabled: !!id,
        queryFn: async () => (await axiosInstance.get<ApplicantEvent[]>(`/recruitment/applicants/${id}/history/`)).data,
    });

export const useCreateApplicant = () =>
    useRecruitmentMutation(
        async (form: FormData) =>
            (await axiosInstance.post("/recruitment/applicants/", form, { headers: { "Content-Type": "multipart/form-data" } })).data,
        "Applicant added",
        "Could not add the applicant",
    );

export const useMoveApplicant = () =>
    useRecruitmentMutation(
        async (vars: { id: string; stage: ApplicantStage; note?: string; rejection_reason?: string }) => {
            const { id, ...body } = vars;
            return (await axiosInstance.post(`/recruitment/applicants/${id}/move/`, body)).data;
        },
        "Applicant moved",
        "Could not move the applicant",
    );

export const useHireApplicant = () =>
    useRecruitmentMutation(
        async (vars: { id: string; joining_date?: string | null; gender?: string }) => {
            const { id, ...body } = vars;
            return (await axiosInstance.post(`/recruitment/applicants/${id}/hire/`, body)).data;
        },
        "Hired - the staff record has been created",
        "Could not hire the applicant",
    );

export const useInterviews = (applicant: string | null) =>
    useQuery({
        queryKey: [KEY, "interviews", applicant],
        enabled: !!applicant,
        queryFn: async () => (await axiosInstance.get<Interview[]>("/recruitment/interviews/", { params: { applicant } })).data,
    });

export const useScheduleInterview = () =>
    useRecruitmentMutation(
        async (data: Partial<Interview> & { panelist_ids?: string[] }) => (await axiosInstance.post("/recruitment/interviews/", data)).data,
        "Interview scheduled",
        "Could not schedule the interview",
    );

export const usePanelOptions = (enabled: boolean) =>
    useQuery({
        queryKey: [KEY, "panel-options"],
        enabled,
        queryFn: async () => (await axiosInstance.get<PanelOption[]>("/recruitment/panel-options/")).data,
    });

/** The interviews the logged-in person sits on (for the My Interviews page). */
export const useMyInterviews = () =>
    useQuery({
        queryKey: [KEY, "interviews", "mine"],
        queryFn: async () => (await axiosInstance.get<Interview[]>("/recruitment/interviews/", { params: { mine: "true" } })).data,
    });

export const useSubmitFeedback = () =>
    useRecruitmentMutation(
        async (vars: { id: string; score: string; feedback?: string }) => {
            const { id, ...body } = vars;
            return (await axiosInstance.post(`/recruitment/interviews/${id}/feedback/`, body)).data;
        },
        "Your feedback has been recorded",
        "Could not record your feedback",
    );

export const useInterviewAction = () =>
    useRecruitmentMutation(
        async (vars: { id: string; action: "complete" | "cancel"; score?: string; feedback?: string }) => {
            const { id, action, ...body } = vars;
            return (await axiosInstance.post(`/recruitment/interviews/${id}/${action}/`, body)).data;
        },
        "Interview updated",
        "Could not update the interview",
    );

/** Resumes are private, so they are fetched with the logged-in session and opened from a temporary local URL. */
export async function openResume(url: string) {
    try {
        const response = await axiosInstance.get(url.replace(/^\/api/, ""), { responseType: "blob" });
        const objectUrl = URL.createObjectURL(response.data as Blob);
        window.open(objectUrl, "_blank", "noopener");
        setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (error) {
        toast.error(recruitmentError(error, "Could not open the resume"));
    }
}
