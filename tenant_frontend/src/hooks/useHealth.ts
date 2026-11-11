import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { apiError } from "@/hooks/useFeeCharging";

export type IncidentKind = "illness" | "injury" | "allergic_reaction" | "medication" | "other";

export const INCIDENT_KINDS: { value: IncidentKind; label: string }[] = [
    { value: "illness", label: "Illness" },
    { value: "injury", label: "Injury" },
    { value: "allergic_reaction", label: "Allergic reaction" },
    { value: "medication", label: "Medicine given" },
    { value: "other", label: "Other" },
];

export interface HealthProfile {
    student: string;
    allergies: string;
    medical_conditions: string;
    medications: string;
    dietary_notes: string;
    doctor_name: string;
    doctor_phone: string;
    notes: string;
    blood_group: string;
    has_alert: boolean;
    updated_at: string | null;
}

export interface HealthIncident {
    id: string;
    student: string;
    student_name: string;
    occurred_at: string;
    kind: IncidentKind;
    kind_display: string;
    description: string;
    action_taken: string;
    sent_home: boolean;
    parent_informed: boolean;
    recorded_by_name: string | null;
    created_at: string;
}

export interface StudentHealth {
    student: string;
    student_name: string;
    profile: HealthProfile;
    incidents: HealthIncident[];
    can_manage: boolean;
}

export interface HealthAlert {
    student: string;
    student_name: string;
    allergies: string;
    medical_conditions: string;
    medications: string;
}

export const useStudentHealth = (studentId: string | undefined) =>
    useQuery<StudentHealth>({
        queryKey: ["health", "student", studentId],
        enabled: !!studentId,
        retry: false,
        queryFn: async () => (await axiosInstance.get(`/health-records/students/${studentId}/`)).data,
    });

export const useSaveHealthProfile = (studentId: string) => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<HealthProfile>) =>
            (await axiosInstance.put(`/health-records/students/${studentId}/`, data)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["health"] });
            toast.success("Health information saved");
        },
        onError: (e) => toast.error(apiError(e, "Could not save the health information")),
    });
};

export const useRecordIncident = (studentId: string) => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<HealthIncident>) =>
            (await axiosInstance.post(`/health-records/students/${studentId}/incidents/`, data)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["health"] });
            toast.success("Incident recorded");
        },
        onError: (e) => toast.error(apiError(e, "Could not record the incident")),
    });
};

export const useUpdateIncident = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, ...data }: Partial<HealthIncident> & { id: string }) =>
            (await axiosInstance.patch(`/health-records/incidents/${id}/`, data)).data,
        onSuccess: () => qc.invalidateQueries({ queryKey: ["health"] }),
        onError: (e) => toast.error(apiError(e, "Could not update the incident")),
    });
};

export const useIncidentLog = (from: string, to: string, page: number) =>
    useQuery<{ count: number; results: HealthIncident[] }>({
        queryKey: ["health", "log", from, to, page],
        queryFn: async () => {
            const q = new URLSearchParams({ page: String(page) });
            if (from) q.set("from", from);
            if (to) q.set("to", to);
            return (await axiosInstance.get(`/health-records/incidents/?${q}`)).data;
        },
    });

export const useHealthAlerts = (sectionId: string | undefined) =>
    useQuery<HealthAlert[]>({
        queryKey: ["health", "alerts", sectionId],
        queryFn: async () =>
            (await axiosInstance.get(`/health-records/alerts/${sectionId ? `?section=${sectionId}` : ""}`)).data,
    });
