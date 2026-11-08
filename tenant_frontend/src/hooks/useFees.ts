import { Query, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import {
    FeeHead,
    FeeStructure,
    InitiateOnlinePaymentInput,
    InitiateOnlinePaymentResponse,
    InitiateParentChildPaymentInput,
    OnlinePaymentOrder,
    OnlinePaymentOrdersResponse,
    OutstandingReportResponse,
    PayableGateway,
    Payment,
    PaymentAllocationInput,
    PaymentGatewayInput,
    PaymentGatewaySetup,
    PaymentMethod,
    StudentFeesResponse,
    VerifyOnlinePaymentResponse,
} from "@/types/Fees";

function errorMessage(error: unknown, fallback: string) {
    const err = error as { response?: { data?: Record<string, unknown> } };
    const data = err.response?.data;
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

// === ONLINE PAYMENTS ===

export const useInitiateOnlinePayment = () => {
    return useMutation({
        mutationFn: async (data: InitiateOnlinePaymentInput) => {
            const response = await axiosInstance.post("/fees/online/initiate/", data);
            return response.data as InitiateOnlinePaymentResponse;
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Failed to initiate online payment")),
    });
};

export const useInitiateParentChildPayment = () => {
    return useMutation({
        mutationFn: async ({ student_id, ...data }: InitiateParentChildPaymentInput) => {
            const response = await axiosInstance.post(`/parent-portal/children/${student_id}/pay-fees/`, data);
            return response.data as InitiateOnlinePaymentResponse;
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Failed to initiate online payment")),
    });
};

export const useVerifyOnlinePayment = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: {
            data?: string;
            encoded_data?: string;
            order_id?: string;
            transaction_uuid?: string;
            razorpay_order_id?: string;
            razorpay_payment_id?: string;
            razorpay_signature?: string;
        }) => {
            const response = await axiosInstance.post("/fees/online/verify/", data);
            return response.data as VerifyOnlinePaymentResponse;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "student"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "payments"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "online", "orders"] });
            queryClient.invalidateQueries({ queryKey: ["parent-portal", "fees"] });
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Failed to verify online payment")),
    });
};

export const useOnlinePaymentOrder = (
    orderId?: string,
    options?: {
        refetchInterval?:
            | number
            | false
            | ((query: Query<OnlinePaymentOrder, Error, OnlinePaymentOrder, readonly unknown[]>) => number | false);
    }
) => {
    return useQuery({
        queryKey: ["fees", "online", "order", orderId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/fees/online/orders/${orderId}/`);
            return response.data as OnlinePaymentOrder;
        },
        enabled: !!orderId,
        refetchInterval: options?.refetchInterval,
    });
};

export const useOnlinePaymentOrders = (params?: { student?: string; status?: string; gateway?: string }) => {
    return useQuery({
        queryKey: ["fees", "online", "orders", params],
        queryFn: async () => {
            const sp = new URLSearchParams();
            if (params?.student) sp.set("student", params.student);
            if (params?.status) sp.set("status", params.status);
            if (params?.gateway) sp.set("gateway", params.gateway);
            const qs = sp.toString();
            const response = await axiosInstance.get(`/fees/online/orders/${qs ? `?${qs}` : ""}`);
            if (Array.isArray(response.data)) {
                return {
                    count: response.data.length,
                    next: null,
                    previous: null,
                    results: response.data,
                } as OnlinePaymentOrdersResponse;
            }
            return response.data as OnlinePaymentOrdersResponse;
        },
    });
};

// === PAYMENT GATEWAYS (per school) ===

export const usePaymentGateways = () =>
    useQuery({
        queryKey: ["fees", "gateways"],
        queryFn: async () => (await axiosInstance.get("/fees/gateways/")).data as PaymentGatewaySetup[],
    });

export const useSavePaymentGateway = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ gateway, ...body }: PaymentGatewayInput & { gateway: string }) =>
            (await axiosInstance.put(`/fees/gateways/${gateway}/`, body)).data as PaymentGatewaySetup,
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["fees", "gateways"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "payable-gateways"] });
            toast.success(`${data.label} saved`);
        },
    });
};

export const useTestPaymentGateway = () =>
    useMutation({
        mutationFn: async (gateway: string) =>
            (await axiosInstance.post(`/fees/gateways/${gateway}/test/`)).data as { ok: boolean; message: string },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not check the keys")),
    });

/** The gateways a parent or student can pay with in this school. */
export const usePayableGateways = (enabled = true) =>
    useQuery({
        queryKey: ["fees", "payable-gateways"],
        queryFn: async () => (await axiosInstance.get("/fees/online/gateways/")).data as PayableGateway[],
        enabled,
    });


export interface DuesFilters {
    academic_year?: string;
    level?: string;
    section?: string;
    band?: string;
    search?: string;
    sort?: "amount" | "age" | "name";
    promise?: string;
    page?: number;
}

export const useDues = (filters: DuesFilters) =>
    useQuery({
        queryKey: ["fees", "dues", filters],
        queryFn: async () => {
            const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== undefined && v !== ""));
            return (await axiosInstance.get<import("@/types/FeeDues").DuesResponse>("/fees/reports/dues/", { params })).data;
        },
        placeholderData: (previous) => previous,
    });


export const useFollowUpDesk = () =>
    useQuery({
        queryKey: ["fees", "dues", "desk"],
        queryFn: async () => (await axiosInstance.get<import("@/types/FeeDues").DeskResponse>("/fees/reports/follow-ups/")).data,
    });

export const useStudentCalls = (student: string | null) =>
    useQuery({
        queryKey: ["fees", "calls", student],
        enabled: !!student,
        queryFn: async () => (await axiosInstance.get<import("@/types/FeeDues").CallRow[]>(`/fees/students/${student}/calls/`)).data,
    });

export const useRecordCall = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (vars: {
            student: string;
            outcome: string;
            note: string;
            promise_date?: string | null;
            promise_amount?: string | null;
        }) => {
            const { student, ...body } = vars;
            return (await axiosInstance.post(`/fees/students/${student}/calls/`, body)).data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["fees", "dues"] });
            queryClient.invalidateQueries({ queryKey: ["fees", "calls"] });
            toast.success("Call saved");
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "Could not save the call")),
    });
};
