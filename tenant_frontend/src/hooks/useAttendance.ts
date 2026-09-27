import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import {
    AttendanceRecordInput,
    AttendanceSession,
    AttendanceSettings,
    BelowThresholdReport,
    SectionRosterResponse,
    SectionSummary,
    StaffAttendanceRecord,
    StaffAttendanceRecordInput,
    StudentAttendanceHistory,
    TenantAttendanceSummary,
} from "@/types/Attendance";

function errorMessage(error: any, fallback: string) {
    const data = error.response?.data;
    if (!data) return fallback;
    if (typeof data.error === "string") return data.error;
    if (data.records) return Array.isArray(data.records) ? data.records.join(" ") : String(data.records);
    return fallback;
}

export const useSectionRoster = (sectionId: string | undefined, date: string) => {
    return useQuery({
        queryKey: ["attendance", "roster", sectionId, date],
        queryFn: async () => {
            const response = await axiosInstance.get(
                `/attendance/sections/${sectionId}/roster/?date=${date}`
            );
            return response.data as SectionRosterResponse;
        },
        enabled: !!sectionId && !!date,
    });
};

export const useSubmitAttendanceSession = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (payload: { section: string; date: string; records: AttendanceRecordInput[] }) => {
            const response = await axiosInstance.post("/attendance/sessions/", payload);
            return response.data as AttendanceSession;
        },
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["attendance", "roster", variables.section, variables.date] });
            toast.success("Attendance saved");
        },
        onError: (error: any) => {
            if (error.response?.status === 423) {
                toast.error("This attendance session is locked and cannot be edited.");
            } else {
                toast.error(errorMessage(error, "Failed to save attendance"));
            }
        },
    });
};

export const useUpdateAttendanceSession = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({
            sessionId,
            records,
        }: {
            sessionId: string;
            records: AttendanceRecordInput[];
        }) => {
            const response = await axiosInstance.patch(`/attendance/sessions/${sessionId}/`, { records });
            return response.data as AttendanceSession;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["attendance", "roster"] });
            toast.success("Attendance updated");
        },
        onError: (error: any) => {
            if (error.response?.status === 423) {
                toast.error("This attendance session is locked and cannot be edited.");
            } else {
                toast.error(errorMessage(error, "Failed to update attendance"));
            }
        },
    });
};

export const useLockAttendanceSession = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ sessionId, isLocked }: { sessionId: string; isLocked: boolean }) => {
            const response = await axiosInstance.post(`/attendance/sessions/${sessionId}/lock/`, {
                is_locked: isLocked,
            });
            return response.data as AttendanceSession;
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["attendance", "roster"] });
            toast.success(data.is_locked ? "Attendance locked" : "Attendance unlocked");
        },
        onError: (error: any) => {
            toast.error(errorMessage(error, "Failed to update lock status"));
        },
    });
};

export const useDeleteAttendanceSession = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (sessionId: string) => {
            await axiosInstance.delete(`/attendance/sessions/${sessionId}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["attendance"] });
            toast.success("Attendance session deleted");
        },
        onError: (error: any) => {
            toast.error(errorMessage(error, "Failed to delete session"));
        },
    });
};

export const useStudentAttendanceHistory = (studentId: string | undefined, startDate?: string, endDate?: string) => {
    return useQuery({
        queryKey: ["attendance", "student-history", studentId, startDate, endDate],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (startDate) params.set("start_date", startDate);
            if (endDate) params.set("end_date", endDate);
            const response = await axiosInstance.get(
                `/attendance/students/${studentId}/history/?${params.toString()}`
            );
            return response.data as StudentAttendanceHistory;
        },
        enabled: !!studentId,
    });
};

export const useSectionAttendanceSummary = (sectionId: string | undefined, month?: string, year?: string) => {
    return useQuery({
        queryKey: ["attendance", "section-summary", sectionId, month, year],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (month) params.set("month", month);
            if (year) params.set("year", year);
            const response = await axiosInstance.get(
                `/attendance/sections/${sectionId}/summary/?${params.toString()}`
            );
            return response.data as SectionSummary;
        },
        enabled: !!sectionId,
    });
};

export const useBelowThresholdReport = (sectionId?: string, academicYear?: string) => {
    return useQuery({
        queryKey: ["attendance", "below-threshold", sectionId, academicYear],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (sectionId) params.set("section", sectionId);
            if (academicYear) params.set("academic_year", academicYear);
            const response = await axiosInstance.get(`/attendance/reports/below-threshold/?${params.toString()}`);
            return response.data as BelowThresholdReport;
        },
    });
};

export const useTenantAttendanceSummary = (date?: string) => {
    return useQuery({
        queryKey: ["attendance", "tenant-summary", date],
        queryFn: async () => {
            const params = date ? `?date=${date}` : "";
            const response = await axiosInstance.get(`/attendance/reports/tenant-summary/${params}`);
            return response.data as TenantAttendanceSummary;
        },
    });
};

export const useSubmitStaffAttendance = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (payload: { date: string; records: StaffAttendanceRecordInput[] }) => {
            const response = await axiosInstance.post("/attendance/staff-sessions/", payload);
            return response.data as StaffAttendanceRecord[];
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["attendance", "staff-history"] });
            toast.success("Staff attendance saved");
        },
        onError: (error: any) => {
            toast.error(errorMessage(error, "Failed to save staff attendance"));
        },
    });
};

export const useStaffAttendanceHistory = (staffId: string | undefined, startDate?: string, endDate?: string) => {
    return useQuery({
        queryKey: ["attendance", "staff-history", staffId, startDate, endDate],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (startDate) params.set("start_date", startDate);
            if (endDate) params.set("end_date", endDate);
            const response = await axiosInstance.get(
                `/attendance/staff/${staffId}/history/?${params.toString()}`
            );
            return response.data;
        },
        enabled: !!staffId,
    });
};

export const useAttendanceSettings = () => {
    return useQuery({
        queryKey: ["attendance", "settings"],
        queryFn: async () => {
            const response = await axiosInstance.get("/attendance/settings/");
            return response.data as AttendanceSettings;
        },
    });
};

export const useUpdateAttendanceSettings = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<AttendanceSettings>) => {
            const response = await axiosInstance.patch("/attendance/settings/", data);
            return response.data as AttendanceSettings;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["attendance", "settings"] });
            toast.success("Attendance settings updated");
        },
        onError: (error: any) => {
            toast.error(errorMessage(error, "Failed to update settings"));
        },
    });
};
