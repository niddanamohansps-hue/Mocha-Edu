import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import {
    LeaveType,
    StaffLeaveBalance,
    LeaveApplication,
    AffectedPeriodSlot,
} from "@/types/Leave";

export function leaveErrorMessage(error: unknown, fallback: string): string {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data || typeof data !== "object") return fallback;
    if (typeof data.error === "string") return data.error;
    if (typeof data.detail === "string") return data.detail;
    for (const key of Object.keys(data)) {
        const value = data[key];
        const text = Array.isArray(value) ? value[0] : value;
        if (typeof text === "string") return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
    }
    return fallback;
}

const KEY = "staff-leaves";

export const useLeaveTypes = (includeInactive = false) => {
    return useQuery({
        queryKey: [KEY, "types", includeInactive],
        queryFn: async () => {
            const res = await axiosInstance.get<LeaveType[]>("/staff/leaves/types/");
            return res.data;
        },
    });
};

export const useMyLeaveBalances = (academicYear?: string) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "balances", "my", user?.id, academicYear],
        queryFn: async () => {
            const params: Record<string, string> = {};
            if (academicYear) params.academic_year = academicYear;
            const res = await axiosInstance.get<StaffLeaveBalance[]>("/staff/leaves/balances/my/", { params });
            return res.data;
        },
        enabled: !!user,
    });
};

export const useAllLeaveBalances = (filters?: { staff?: string; academic_year?: string; leave_type?: string }) => {
    return useQuery({
        queryKey: [KEY, "balances", "all", filters],
        queryFn: async () => {
            const params: Record<string, string> = {};
            if (filters?.staff) params.staff = filters.staff;
            if (filters?.academic_year) params.academic_year = filters.academic_year;
            if (filters?.leave_type) params.leave_type = filters.leave_type;

            const res = await axiosInstance.get<{ results: StaffLeaveBalance[]; count: number }>("/staff/leaves/balances/", { params });
            return res.data;
        },
    });
};

export const useMyLeaveApplications = (filters?: { status?: string; academic_year?: string }) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "applications", "my", user?.id, filters],
        queryFn: async () => {
            const params: Record<string, string> = {};
            if (filters?.status) params.status = filters.status;
            if (filters?.academic_year) params.academic_year = filters.academic_year;

            const res = await axiosInstance.get<{ results: LeaveApplication[]; count: number }>("/staff/leaves/applications/my/", { params });
            return res.data;
        },
        enabled: !!user,
    });
};

export const useApproverInbox = (filters?: { status?: string; staff?: string }) => {
    return useQuery({
        queryKey: [KEY, "approvals", "inbox", filters],
        queryFn: async () => {
            const params: Record<string, string> = {};
            if (filters?.status) params.status = filters.status;
            if (filters?.staff) params.staff = filters.staff;

            const res = await axiosInstance.get<{ results: LeaveApplication[]; count: number }>("/staff/leaves/approvals/inbox/", { params });
            return res.data;
        },
    });
};

export const useLeaveApplicationDetail = (id?: string) => {
    return useQuery({
        queryKey: [KEY, "application", id],
        queryFn: async () => {
            if (!id) return null;
            const res = await axiosInstance.get<LeaveApplication>(`/staff/leaves/applications/${id}/`);
            return res.data;
        },
        enabled: !!id,
    });
};

export const useAffectedPeriods = (id?: string) => {
    return useQuery({
        queryKey: [KEY, "affected-periods", id],
        queryFn: async () => {
            if (!id) return [];
            const res = await axiosInstance.get<AffectedPeriodSlot[]>(`/staff/leaves/applications/${id}/affected-periods/`);
            return res.data;
        },
        enabled: !!id,
    });
};

export const useApplyLeave = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (formData: FormData) => {
            const res = await axiosInstance.post<LeaveApplication>("/staff/leaves/applications/", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Leave application submitted successfully.");
            queryClient.invalidateQueries({ queryKey: [KEY] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to submit leave application."));
        },
    });
};

export const useApproveLeave = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, comments }: { id: string; comments?: string }) => {
            const res = await axiosInstance.post<LeaveApplication>(`/staff/leaves/applications/${id}/approve/`, { comments });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Leave application approved and attendance updated.");
            queryClient.invalidateQueries({ queryKey: [KEY] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to approve leave application."));
        },
    });
};

export const useRejectLeave = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, comments }: { id: string; comments: string }) => {
            const res = await axiosInstance.post<LeaveApplication>(`/staff/leaves/applications/${id}/reject/`, { comments });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Leave application rejected.");
            queryClient.invalidateQueries({ queryKey: [KEY] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to reject leave application."));
        },
    });
};

export const useCancelLeave = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, reason }: { id: string; reason?: string }) => {
            const res = await axiosInstance.post<LeaveApplication>(`/staff/leaves/applications/${id}/cancel/`, { reason });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Leave application cancelled.");
            queryClient.invalidateQueries({ queryKey: [KEY] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to cancel leave application."));
        },
    });
};

export const useCreateLeaveType = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (payload: Partial<LeaveType>) => {
            const res = await axiosInstance.post<LeaveType>("/staff/leaves/types/", payload);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Leave type created successfully.");
            queryClient.invalidateQueries({ queryKey: [KEY, "types"] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to create leave type."));
        },
    });
};

export const useUpdateLeaveType = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, payload }: { id: string; payload: Partial<LeaveType> }) => {
            const res = await axiosInstance.patch<LeaveType>(`/staff/leaves/types/${id}/`, payload);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Leave type updated successfully.");
            queryClient.invalidateQueries({ queryKey: [KEY, "types"] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to update leave type."));
        },
    });
};

export const useDeactivateLeaveType = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/staff/leaves/types/${id}/`);
        },
        onSuccess: () => {
            toast.success("Leave type deactivated.");
            queryClient.invalidateQueries({ queryKey: [KEY, "types"] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to deactivate leave type."));
        },
    });
};

export const useAdjustStaffLeaveBalance = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (payload: {
            staff_id: string;
            leave_type_id: string;
            academic_year: string;
            allocated_days: number;
            reason: string;
        }) => {
            const res = await axiosInstance.post<StaffLeaveBalance>("/staff/leaves/balances/adjust/", payload);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Staff leave balance adjusted.");
            queryClient.invalidateQueries({ queryKey: [KEY, "balances"] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to adjust balance."));
        },
    });
};

export const useAssignSubstitution = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (payload: {
            entry_id: string;
            date: string;
            substitute_instructor_id: number;
            reason?: string;
        }) => {
            const res = await axiosInstance.post("/staff/leaves/substitutions/assign/", payload);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Substitute teacher assigned successfully.");
            queryClient.invalidateQueries({ queryKey: [KEY, "affected-periods"] });
        },
        onError: (err) => {
            toast.error(leaveErrorMessage(err, "Failed to assign substitute teacher."));
        },
    });
};

