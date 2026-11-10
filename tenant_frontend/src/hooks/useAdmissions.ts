import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import {
    AdmissionEnquiry,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionsDashboardStats,
    ApplicationStatus,
    EnquiryStatus,
    PublicAdmissionsInfo,
    PublicEnquiryPayload,
    PublicApplicationPayload,
    PublicApplicationSubmissionResult,
    PublicApplicationStatus,
} from "@/types/Admissions";

export function admissionsErrorMessage(error: unknown, fallback: string): string {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data || typeof data !== "object") return fallback;
    if (typeof (data as any).error === "string") return (data as any).error;
    if (typeof (data as any).detail === "string") return (data as any).detail;
    for (const key of Object.keys(data)) {
        const value = data[key];
        const text = Array.isArray(value) ? value[0] : value;
        if (typeof text === "string") return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
    }
    return fallback;
}

const ADMISSIONS_KEY = "admissions";

export interface EnquiryFilters {
    status?: EnquiryStatus | "";
    academic_year?: string;
    level?: string;
    search?: string;
}

export interface ApplicationFilters {
    status?: ApplicationStatus | "";
    academic_year?: string;
    level?: string;
    reviewer?: string;
    search?: string;
    page?: number;
    page_size?: number;
}

export const useAdmissionsDashboard = () => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [ADMISSIONS_KEY, "dashboard", user?.id],
        queryFn: async () => {
            const res = await axiosInstance.get("/admissions/dashboard/");
            return res.data as AdmissionsDashboardStats;
        },
        enabled: !!user,
    });
};

export const useEnquiries = (filters?: EnquiryFilters) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [ADMISSIONS_KEY, "enquiries", user?.id, filters],
        queryFn: async () => {
            const params: Record<string, string> = {};
            if (filters?.status) params.status = filters.status;
            if (filters?.academic_year) params.academic_year = filters.academic_year;
            if (filters?.level) params.level = filters.level;
            if (filters?.search) params.search = filters.search;

            const res = await axiosInstance.get("/admissions/enquiries/", { params });
            const data = res.data;
            if (Array.isArray(data)) return data as AdmissionEnquiry[];
            if (data && Array.isArray(data.results)) return data.results as AdmissionEnquiry[];
            return [] as AdmissionEnquiry[];
        },
        enabled: !!user,
    });
};

export const useEnquiry = (id?: string) => {
    return useQuery({
        queryKey: [ADMISSIONS_KEY, "enquiry", id],
        queryFn: async () => {
            const res = await axiosInstance.get(`/admissions/enquiries/${id}/`);
            return res.data as AdmissionEnquiry;
        },
        enabled: !!id,
    });
};

export const useCreateEnquiry = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (payload: Partial<AdmissionEnquiry>) => {
            const res = await axiosInstance.post("/admissions/enquiries/", payload);
            return res.data as AdmissionEnquiry;
        },
        onSuccess: (data) => {
            toast.success(`Enquiry ${data.enquiry_number} created successfully`);
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to create enquiry"));
        },
    });
};

export const useUpdateEnquiry = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: Partial<AdmissionEnquiry> }) => {
            const res = await axiosInstance.patch(`/admissions/enquiries/${id}/`, data);
            return res.data as AdmissionEnquiry;
        },
        onSuccess: () => {
            toast.success("Enquiry updated successfully");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to update enquiry"));
        },
    });
};

export const useDeleteEnquiry = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/admissions/enquiries/${id}/`);
        },
        onSuccess: () => {
            toast.success("Enquiry deleted successfully");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to delete enquiry"));
        },
    });
};

export const useConvertEnquiry = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            const res = await axiosInstance.post(`/admissions/enquiries/${id}/convert/`);
            return res.data as AdmissionApplication;
        },
        onSuccess: (data) => {
            toast.success(`Enquiry converted to application ${data.application_number}`);
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to convert enquiry"));
        },
    });
};

export interface PaginatedApplications {
    results: AdmissionApplication[];
    count: number;
}

export const useApplications = (filters?: ApplicationFilters) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [ADMISSIONS_KEY, "applications", user?.id, filters],
        queryFn: async (): Promise<PaginatedApplications> => {
            const params: Record<string, string | number> = {};
            if (filters?.status) params.status = filters.status;
            if (filters?.academic_year) params.academic_year = filters.academic_year;
            if (filters?.level) params.level = filters.level;
            if (filters?.reviewer) params.reviewer = filters.reviewer;
            if (filters?.search) params.search = filters.search;
            if (filters?.page) params.page = filters.page;
            if (filters?.page_size) params.page_size = filters.page_size;

            const res = await axiosInstance.get("/admissions/applications/", { params });
            const data = res.data;
            if (Array.isArray(data)) return { results: data as AdmissionApplication[], count: data.length };
            if (data && Array.isArray(data.results)) return { results: data.results as AdmissionApplication[], count: data.count ?? data.results.length };
            return { results: [], count: 0 };
        },
        enabled: !!user,
    });
};

export const useApplication = (id?: string) => {
    return useQuery({
        queryKey: [ADMISSIONS_KEY, "application", id],
        queryFn: async () => {
            const res = await axiosInstance.get(`/admissions/applications/${id}/`);
            return res.data as AdmissionApplication;
        },
        enabled: !!id,
    });
};

export const useCreateApplication = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (payload: Partial<AdmissionApplication>) => {
            const res = await axiosInstance.post("/admissions/applications/", payload);
            return res.data as AdmissionApplication;
        },
        onSuccess: (data) => {
            toast.success(`Application ${data.application_number} submitted`);
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to create application"));
        },
    });
};

export const useUpdateApplication = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: Partial<AdmissionApplication> }) => {
            const res = await axiosInstance.patch(`/admissions/applications/${id}/`, data);
            return res.data as AdmissionApplication;
        },
        onSuccess: () => {
            toast.success("Application updated successfully");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to update application"));
        },
    });
};

export const useTransitionApplicationStatus = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            id,
            status,
            notes,
            reason,
        }: {
            id: string;
            status: ApplicationStatus;
            notes?: string;
            reason?: string;
        }) => {
            const res = await axiosInstance.post(`/admissions/applications/${id}/status/`, {
                status,
                notes,
                reason,
            });
            return res.data as AdmissionApplication;
        },
        onSuccess: (data) => {
            toast.success(`Application status transitioned to ${data.status.replace(/_/g, " ")}`);
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Status transition failed"));
        },
    });
};

export const useAssignReviewer = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, staff_id }: { id: string; staff_id: string | null }) => {
            const res = await axiosInstance.post(`/admissions/applications/${id}/assign/`, {
                staff_id,
            });
            return res.data as AdmissionApplication;
        },
        onSuccess: () => {
            toast.success("Reviewer assigned successfully");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to assign reviewer"));
        },
    });
};

export const useMakeAdmissionDecision = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            id,
            decision,
            reason,
            notes,
            confirm_over_limit,
        }: {
            id: string;
            decision: "approved" | "rejected" | "waitlisted";
            reason?: string;
            notes?: string;
            confirm_over_limit?: boolean;
        }) => {
            const res = await axiosInstance.post(`/admissions/applications/${id}/decide/`, {
                decision,
                reason,
                notes,
                confirm_over_limit,
            });
            return res.data as AdmissionApplication;
        },
        onSuccess: (data) => {
            toast.success(`Decision recorded: ${data.status.toUpperCase()}`);
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            // A full class is not an error to shout about: the dialog asks "approve anyway?" instead.
            if (seatLimitMessage(err)) return;
            toast.error(admissionsErrorMessage(err, "Failed to record decision"));
        },
    });
};

/** The "class is full" message from a refused approval, or null for any other error. */
export function seatLimitMessage(error: unknown): string | null {
    const data = (error as { response?: { data?: { seat_limit?: unknown } } })?.response?.data;
    const value = data?.seat_limit;
    return Array.isArray(value) && value.length ? String(value[0]) : null;
}

/** Email the family the outcome of a rejected application. Rejections are never emailed automatically. */
export const useSendDecisionNotice = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => (await axiosInstance.post(`/admissions/applications/${id}/decision-notice/`, {})).data as AdmissionApplication,
        onSuccess: () => {
            toast.success("The family has been emailed");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => toast.error(admissionsErrorMessage(err, "Could not send the email")),
    });
};

/**
 * Give the family a way to track an application online (needed for applications staff entered, which get no
 * access token). Issuing a new one cancels any earlier link. The token is shown once and never stored readable.
 */
export const useIssueTrackingLink = () => {
    return useMutation({
        mutationFn: async (id: string) =>
            (await axiosInstance.post(`/admissions/applications/${id}/rotate-token/`, {
                reason: "Tracking link issued by admissions staff.",
            })).data as { application_number: string; access_token: string; access_token_expires_at: string },
        onError: (err) => toast.error(admissionsErrorMessage(err, "Could not create the tracking link")),
    });
};

export const useEnrollApplication = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, section_id }: { id: string; section_id?: string | null }) => {
            const res = await axiosInstance.post(`/admissions/applications/${id}/enroll/`, {
                section_id,
            });
            return res.data as {
                message: string;
                student_id: string;
                enrollment_id: string;
                application: AdmissionApplication;
            };
        },
        onSuccess: (data) => {
            toast.success(`Student enrolled successfully! ID: ${data.enrollment_id}`);
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
            qc.invalidateQueries({ queryKey: ["students"] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Enrollment conversion failed"));
        },
    });
};

export const useUploadAdmissionDocument = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, formData }: { id: string; formData: FormData }) => {
            const res = await axiosInstance.post(`/admissions/applications/${id}/documents/`, formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            return res.data as AdmissionDocument;
        },
        onSuccess: () => {
            toast.success("Document uploaded successfully");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Document upload failed"));
        },
    });
};

export const useVerifyAdmissionDocument = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (documentId: string) => {
            const res = await axiosInstance.post(`/admissions/documents/${documentId}/verify/`);
            return res.data as AdmissionDocument;
        },
        onSuccess: () => {
            toast.success("Document marked as verified");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to verify document"));
        },
    });
};

export const useRejectAdmissionDocument = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ documentId, reason }: { documentId: string; reason: string }) => {
            const res = await axiosInstance.post(`/admissions/documents/${documentId}/reject/`, {
                reason,
            });
            return res.data as AdmissionDocument;
        },
        onSuccess: () => {
            toast.success("Document rejected with recorded reason");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to reject document"));
        },
    });
};

export const useScheduleInterview = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: Partial<AdmissionInterview> }) => {
            const res = await axiosInstance.post(`/admissions/applications/${id}/interviews/`, data);
            return res.data as AdmissionInterview;
        },
        onSuccess: () => {
            toast.success("Interview scheduled successfully");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to schedule interview"));
        },
    });
};

export const useUpdateInterview = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ interviewId, data }: { interviewId: string; data: Partial<AdmissionInterview> }) => {
            const res = await axiosInstance.patch(`/admissions/interviews/${interviewId}/`, data);
            return res.data as AdmissionInterview;
        },
        onSuccess: () => {
            toast.success("Interview assessment recorded");
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to update interview"));
        },
    });
};

// =====================================================================
// Public Admissions Self-Service Hooks (No Staff Login Required)
// =====================================================================

export const usePublicAdmissionsInfo = () => {
    return useQuery({
        queryKey: [ADMISSIONS_KEY, "public", "info"],
        queryFn: async () => {
            const res = await axiosInstance.get("/admissions/public/info/");
            return res.data as PublicAdmissionsInfo;
        },
        staleTime: 5 * 60 * 1000,
    });
};

export const useSubmitPublicEnquiry = () => {
    return useMutation({
        mutationFn: async (payload: PublicEnquiryPayload) => {
            const res = await axiosInstance.post("/admissions/public/enquiries/", payload);
            return res.data as { success: boolean; enquiry_number: string; message: string };
        },
        onSuccess: (data) => {
            toast.success(data.message || "Enquiry submitted successfully");
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to submit enquiry"));
        },
    });
};

export const useSubmitPublicApplication = () => {
    return useMutation({
        mutationFn: async (payload: PublicApplicationPayload) => {
            const res = await axiosInstance.post("/admissions/public/applications/", payload);
            return res.data as PublicApplicationSubmissionResult;
        },
        onSuccess: (data) => {
            toast.success(data.message || `Application ${data.application_number} submitted successfully!`);
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to submit application"));
        },
    });
};

export const usePublicApplicationStatus = (
    applicationNumber?: string,
    token?: string
) => {
    return useQuery({
        queryKey: [ADMISSIONS_KEY, "public", "status", applicationNumber, token],
        queryFn: async () => {
            if (!applicationNumber || !token) {
                throw new Error("Application number and access token are required.");
            }
            const res = await axiosInstance.get(
                `/admissions/public/applications/${encodeURIComponent(applicationNumber.trim())}/status/`,
                {
                    headers: {
                        "X-Application-Token": token.trim(),
                    },
                }
            );
            return res.data as PublicApplicationStatus;
        },
        enabled: Boolean(applicationNumber?.trim() && token?.trim()),
        retry: false,
    });
};

export const useUploadPublicDocument = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            applicationNumber,
            token,
            formData,
        }: {
            applicationNumber: string;
            token: string;
            formData: FormData;
        }) => {
            const res = await axiosInstance.post(
                `/admissions/public/applications/${encodeURIComponent(applicationNumber.trim())}/documents/`,
                formData,
                {
                    headers: {
                        "X-Application-Token": token.trim(),
                        "Content-Type": "multipart/form-data",
                    },
                }
            );
            return res.data as { success: boolean; message: string };
        },
        onSuccess: (data, variables) => {
            toast.success(data.message || "Document uploaded successfully!");
            qc.invalidateQueries({
                queryKey: [ADMISSIONS_KEY, "public", "status", variables.applicationNumber, variables.token],
            });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to upload document"));
        },
    });
};

export const useRotatePublicToken = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({
            applicationNumber,
            currentToken,
        }: {
            applicationNumber: string;
            currentToken: string;
        }) => {
            const res = await axiosInstance.post(
                `/admissions/public/applications/${encodeURIComponent(applicationNumber.trim())}/rotate-token/`,
                {},
                {
                    headers: {
                        "X-Application-Token": currentToken.trim(),
                    },
                }
            );
            return res.data as {
                success: boolean;
                application_number: string;
                access_token: string;
                access_token_expires_at: string;
                message: string;
            };
        },
        onSuccess: (data) => {
            toast.success(data.message || "Access token rotated successfully!");
            qc.invalidateQueries({
                queryKey: [ADMISSIONS_KEY, "public"],
            });
        },
        onError: (err) => {
            toast.error(admissionsErrorMessage(err, "Failed to rotate access token"));
        },
    });
};




export interface FollowUpRow {
    id: string;
    enquiry_number: string;
    student_name: string;
    guardian_name: string;
    guardian_phone: string;
    level: string;
    source: string;
    status: string;
    assigned_to: string | null;
    assigned_to_name: string | null;
    enquiry_date: string;
    follow_up_date: string | null;
    days_overdue: number;
    notes: string;
}

export interface FollowUpDesk {
    overdue: FollowUpRow[];
    today: FollowUpRow[];
    upcoming: FollowUpRow[];
    unscheduled: FollowUpRow[];
    summary: { overdue: number; today: number; upcoming: number; unscheduled: number };
}

export const useFollowUpDesk = (mine: boolean) =>
    useQuery({
        queryKey: [ADMISSIONS_KEY, "follow-ups", mine],
        queryFn: async () =>
            (await axiosInstance.get<FollowUpDesk>("/admissions/enquiries/follow-ups/", { params: mine ? { mine: "true" } : {} })).data,
    });

export const useRecordFollowUp = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (vars: { id: string; outcome: "contacted" | "qualified" | "lost"; note: string; next_follow_up: string | null }) => {
            const { id, ...body } = vars;
            return (await axiosInstance.post(`/admissions/enquiries/${id}/follow-up/`, body)).data;
        },
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
            toast.success("Follow-up saved");
        },
        onError: (err) => toast.error(admissionsErrorMessage(err, "Could not save the follow-up")),
    });
};


export interface SeatRow {
    level: string;
    level_name: string;
    seats: number | null;
    taken: number;
    free: number | null;
    over_by: number;
    waitlisted: number;
    in_progress: number;
}

export interface AdmissionsReport {
    academic_year: string;
    totals: { enquiries: number; applications: number; enrolled: number };
    by_source: { source: string; label: string; enquiries: number; applied: number; lost: number; enrolled: number }[];
    by_level: { level: string; level_name: string; enquiries: number; applications: number; approved: number; enrolled: number }[];
    average_days_to_enrol: number | null;
    enrolled_with_enquiry: number;
}

export const useSeats = (academicYear: string) =>
    useQuery({
        queryKey: [ADMISSIONS_KEY, "seats", academicYear],
        enabled: !!academicYear,
        queryFn: async () => (await axiosInstance.get<SeatRow[]>("/admissions/seats/", { params: { academic_year: academicYear } })).data,
    });

export const useSetSeatLimit = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (vars: { academic_year: string; level: string; seats: number }) =>
            (await axiosInstance.put<SeatRow[]>("/admissions/seats/", vars)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY, "seats"] });
            toast.success("Seats saved");
        },
        onError: (err) => toast.error(admissionsErrorMessage(err, "Could not save the seats")),
    });
};

export const useAdmissionsReport = (academicYear: string) =>
    useQuery({
        queryKey: [ADMISSIONS_KEY, "report", academicYear],
        enabled: !!academicYear,
        queryFn: async () => (await axiosInstance.get<AdmissionsReport>("/admissions/report/", { params: { academic_year: academicYear } })).data,
    });


export interface RequiredDocuments {
    types: { value: string; label: string }[];
    all_classes: string[];
    by_level: { level: string; level_name: string; document_types: string[] }[];
}

export const useRequiredDocuments = () =>
    useQuery({
        queryKey: [ADMISSIONS_KEY, "required-documents"],
        queryFn: async () => (await axiosInstance.get<RequiredDocuments>("/admissions/required-documents/")).data,
    });

/** Replace the documents asked of one class, or of every class when ``level`` is null. */
export const useSetRequiredDocuments = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (vars: { level: string | null; document_types: string[] }) =>
            (await axiosInstance.put<RequiredDocuments>("/admissions/required-documents/", vars)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: [ADMISSIONS_KEY] });
            toast.success("Required documents saved");
        },
        onError: (err) => toast.error(admissionsErrorMessage(err, "Could not save the list")),
    });
};
