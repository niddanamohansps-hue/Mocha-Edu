import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";

export interface FeeInstallment {
    id?: string;
    name: string;
    percent: string;
    due_date: string;
}

export interface InstallmentPlan {
    structure: string;
    installments: FeeInstallment[];
    /** True once students have been charged; the plan can no longer change. */
    locked: boolean;
}

export interface ChargePreview {
    installments: { name: string; amount: string; due_date: string | null }[];
    students_total: number;
    students_to_charge: number;
    students_already_charged: number;
    fees_to_create: number;
    amount_to_charge: string;
    concession_total: string;
    students: { student: string; name: string; section: string; concessions: string; discount: string; new_fees: number }[];
}

export type ConcessionKind = "percent" | "fixed";

export interface ConcessionType {
    id: string;
    name: string;
    kind: ConcessionKind;
    value: string;
    fee_head: string | null;
    fee_head_name: string | null;
    description: string;
    is_active: boolean;
}

export interface StudentConcession {
    id: string;
    student: string;
    student_name: string;
    concession_type: string;
    concession_name: string;
    kind: ConcessionKind;
    value: string;
    academic_year: string;
    note: string;
    is_active: boolean;
    created_at: string;
}

export function apiError(error: unknown, fallback: string) {
    const data = (error as { response?: { data?: unknown } }).response?.data;
    if (!data) return fallback;
    if (typeof data === "string") return fallback;
    if (Array.isArray(data) && data.length) return String(data[0]);
    const record = data as Record<string, unknown>;
    if (typeof record.error === "string") return record.error;
    if (typeof record.detail === "string") return record.detail;
    for (const value of Object.values(record)) {
        if (Array.isArray(value) && value.length) return typeof value[0] === "string" ? value[0] : JSON.stringify(value[0]);
        if (typeof value === "string") return value;
    }
    return fallback;
}

const rows = <T,>(data: T[] | { results: T[] }) => (Array.isArray(data) ? data : data.results);

export const useInstallmentPlan = (structureId: string | undefined) =>
    useQuery<InstallmentPlan>({
        queryKey: ["fees", "installments", structureId],
        enabled: !!structureId,
        queryFn: async () => (await axiosInstance.get(`/fees/structures/${structureId}/installments/`)).data,
    });

export const useSaveInstallmentPlan = (structureId: string) => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (installments: FeeInstallment[]) =>
            (await axiosInstance.put(`/fees/structures/${structureId}/installments/`, { installments })).data as InstallmentPlan,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["fees", "installments", structureId] });
            qc.invalidateQueries({ queryKey: ["fees", "charge", structureId] });
            toast.success("Instalments saved");
        },
        onError: (e) => toast.error(apiError(e, "Could not save the instalments")),
    });
};

export const useChargePreview = (structureId: string | undefined, enabled: boolean) =>
    useQuery<ChargePreview>({
        queryKey: ["fees", "charge", structureId],
        enabled: !!structureId && enabled,
        queryFn: async () => (await axiosInstance.get(`/fees/structures/${structureId}/charge/`)).data,
    });

export const useChargeStructure = (structureId: string) => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async () => (await axiosInstance.post(`/fees/structures/${structureId}/charge/`)).data as ChargePreview,
        onSuccess: (data) => {
            qc.invalidateQueries({ queryKey: ["fees"] });
            toast.success(
                data.fees_to_create
                    ? `Charged ${data.students_to_charge} students (${data.fees_to_create} fees)`
                    : "Everyone in this class was already charged",
            );
        },
        onError: (e) => toast.error(apiError(e, "Could not charge the class")),
    });
};

export const useConcessionTypes = () =>
    useQuery<ConcessionType[]>({
        queryKey: ["fees", "concession-types"],
        queryFn: async () => rows((await axiosInstance.get("/fees/concession-types/?page_size=200")).data),
    });

export const useSaveConcessionType = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, ...data }: Partial<ConcessionType>) =>
            id
                ? (await axiosInstance.patch(`/fees/concession-types/${id}/`, data)).data
                : (await axiosInstance.post("/fees/concession-types/", data)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["fees", "concession-types"] });
            toast.success("Concession saved");
        },
        onError: (e) => toast.error(apiError(e, "Could not save the concession")),
    });
};

export const useStudentConcessions = (academicYear: string | undefined) =>
    useQuery<StudentConcession[]>({
        queryKey: ["fees", "concessions", academicYear],
        enabled: !!academicYear,
        queryFn: async () =>
            rows((await axiosInstance.get(`/fees/concessions/?academic_year=${encodeURIComponent(academicYear!)}&page_size=500`)).data),
    });

export const useGrantConcession = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: { student: string; concession_type: string; academic_year: string; note: string }) =>
            (await axiosInstance.post("/fees/concessions/", data)).data,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["fees", "concessions"] });
            toast.success("Concession given");
        },
        onError: (e) => toast.error(apiError(e, "Could not give the concession")),
    });
};

export const useSetConcessionActive = () => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) =>
            (await axiosInstance.patch(`/fees/concessions/${id}/`, { is_active })).data,
        onSuccess: () => qc.invalidateQueries({ queryKey: ["fees", "concessions"] }),
        onError: (e) => toast.error(apiError(e, "Could not update the concession")),
    });
};
