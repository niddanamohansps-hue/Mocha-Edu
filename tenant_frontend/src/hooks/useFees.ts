import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import {
    FeeHead,
    FeeStructure,
    OutstandingReportResponse,
    Payment,
    PaymentAllocationInput,
    PaymentMethod,
    StudentFeesResponse,
} from "@/types/Fees";

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

// === FEE HEADS ===

export const useFeeHeads = () => {
    return useQuery({
        queryKey: ["fees", "heads"],
        queryFn: async () => {
            const response = await axiosInstance.get("/fees/heads/");
            return response.data as FeeHead[];
        },
    });
};

export const useCreateFeeHead = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<FeeHead>) => {
            const response = await axiosInstance.post("/fees/heads/", data);
            return response.data as FeeHead;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "heads"] });
            toast.success("Fee head created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create fee head")),
    });
};

// === FEE STRUCTURES ===

export const useFeeStructures = (academicYear?: string) => {
    return useQuery({
        queryKey: ["fees", "structures", academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/fees/structures/${params}`);
            return response.data as FeeStructure[];
        },
    });
};

export const useCreateFeeStructure = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<FeeStructure>) => {
            const response = await axiosInstance.post("/fees/structures/", data);
            return response.data as FeeStructure;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "structures"] });
            toast.success("Fee structure created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create fee structure")),
    });
};

// === STUDENT FEES ===

export const useStudentFees = (studentId: string | undefined, academicYear?: string) => {
    return useQuery({
        queryKey: ["fees", "student", studentId, academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/fees/students/${studentId}/${params}`);
            return response.data as StudentFeesResponse;
        },
        enabled: !!studentId,
    });
};

export const useAssignStudentFee = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({
            studentId,
            data,
        }: {
            studentId: string;
            data: {
                fee_structure?: string;
                fee_head?: string;
                academic_year: string;
                amount_due?: string;
                due_date?: string;
                discount_amount?: string;
                discount_reason?: string;
            };
        }) => {
            const response = await axiosInstance.post(`/fees/students/${studentId}/assign/`, data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "student"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "reports"] });
            toast.success("Fee assigned to student");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to assign fee")),
    });
};

export const useCancelStudentFee = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({
            studentId,
            feeId,
            cancellationReason,
        }: {
            studentId: string;
            feeId: string;
            cancellationReason: string;
        }) => {
            const response = await axiosInstance.post(`/fees/students/${studentId}/cancel/${feeId}/`, {
                cancellation_reason: cancellationReason,
            });
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "student"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "reports"] });
            toast.success("Fee cancelled");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to cancel fee")),
    });
};

// === PAYMENTS ===

export const useStudentPayments = (studentId: string | undefined) => {
    return useQuery({
        queryKey: ["fees", "payments", studentId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/fees/students/${studentId}/payments/`);
            return response.data as Payment[];
        },
        enabled: !!studentId,
    });
};

export const useRecordPayment = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: {
            student: string;
            amount: string;
            method: PaymentMethod;
            reference_note?: string;
            allocations: PaymentAllocationInput[];
        }) => {
            const response = await axiosInstance.post("/fees/payments/", data);
            return response.data as Payment;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "student"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "payments"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "reports"] });
            toast.success("Payment recorded");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to record payment")),
    });
};

export const useReversePayment = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ paymentId, reason }: { paymentId: string; reason?: string }) => {
            const response = await axiosInstance.post(`/fees/payments/${paymentId}/reverse/`, { reason });
            return response.data as Payment;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "student"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "payments"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "reports"] });
            toast.success("Payment reversed");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to reverse payment")),
    });
};

export const usePaymentReceipt = (paymentId: string | undefined) => {
    return useQuery({
        queryKey: ["fees", "receipt", paymentId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/fees/payments/${paymentId}/receipt/`);
            return response.data as Payment;
        },
        enabled: !!paymentId,
    });
};

// === REPORTS ===

export const useOutstandingReport = (academicYear?: string, sectionId?: string) => {
    return useQuery({
        queryKey: ["fees", "reports", "outstanding", academicYear, sectionId],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (academicYear) params.set("academic_year", academicYear);
            if (sectionId) params.set("section", sectionId);
            const qs = params.toString();
            const response = await axiosInstance.get(`/fees/reports/outstanding/${qs ? `?${qs}` : ""}`);
            return response.data as OutstandingReportResponse;
        },
    });
};
