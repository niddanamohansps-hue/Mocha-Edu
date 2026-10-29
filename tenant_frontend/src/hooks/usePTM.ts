import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";

export interface PTMSlot {
    id: string;
    session: string;
    teacher: string;
    teacher_detail?: {
        id: string;
        employee_id: string;
        designation: string;
        department: string;
        full_name: string;
    };
    start_time: string;
    end_time: string;
    status: "available" | "booked" | "blocked" | "completed";
    student?: string | null;
    student_detail?: {
        id: string;
        enrollment_id: string;
        full_name: string;
        current_class: string;
    } | null;
    booked_by_parent?: string | null;
    parent_detail?: {
        id: string;
        full_name: string;
        phone_number: string;
    } | null;
    booked_at?: string | null;
    parent_notes?: string;
    teacher_feedback?: string;
    attended: boolean;
    created_at: string;
    updated_at: string;
}

export interface PTMSession {
    id: string;
    title: string;
    academic_year?: string | null;
    academic_year_name?: string;
    meeting_date: string;
    start_time: string;
    end_time: string;
    slot_duration_minutes: number;
    buffer_minutes: number;
    mode: "in_person" | "online";
    location_or_url?: string;
    level?: string | null;
    level_name?: string;
    section?: string | null;
    section_name?: string;
    teachers: string[];
    teachers_detail?: {
        id: string;
        employee_id: string;
        designation: string;
        department: string;
        full_name: string;
    }[];
    status: "draft" | "published" | "completed" | "cancelled";
    instructions?: string;
    total_slots: number;
    booked_slots_count: number;
    created_at: string;
    updated_at: string;
}

export interface CreatePTMSessionPayload {
    title: string;
    academic_year?: string;
    meeting_date: string;
    start_time: string;
    end_time: string;
    slot_duration_minutes: number;
    buffer_minutes?: number;
    mode: "in_person" | "online";
    location_or_url?: string;
    level?: string;
    section?: string;
    teacher_ids?: string[];
    instructions?: string;
}

// ---------------------------------------------------------------------------
// Admin & Teacher Hooks
// ---------------------------------------------------------------------------

export function usePTMSessions(filters?: {
    academic_year?: string;
    level?: string;
    status?: string;
    meeting_date?: string;
}) {
    return useQuery<PTMSession[]>({
        queryKey: ["ptm-sessions", filters],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (filters?.academic_year) params.append("academic_year", filters.academic_year);
            if (filters?.level) params.append("level", filters.level);
            if (filters?.status) params.append("status", filters.status);
            if (filters?.meeting_date) params.append("meeting_date", filters.meeting_date);

            const res = await axiosInstance.get(`/api/ptm/sessions/?${params.toString()}`);
            return res.data?.results || res.data || [];
        },
    });
}

export function usePTMSessionRoster(sessionId: string | null) {
    return useQuery<{ session: PTMSession; slots: PTMSlot[] }>({
        queryKey: ["ptm-session-roster", sessionId],
        queryFn: async () => {
            if (!sessionId) throw new Error("Session ID is required");
            const res = await axiosInstance.get(`/api/ptm/sessions/${sessionId}/roster/`);
            return res.data;
        },
        enabled: !!sessionId,
    });
}

export function useCreatePTMSession() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: CreatePTMSessionPayload) => {
            const res = await axiosInstance.post("/api/ptm/sessions/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("PTM Session created successfully");
            queryClient.invalidateQueries({ queryKey: ["ptm-sessions"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to create PTM session");
        },
    });
}

export function useGenerateSlots() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (sessionId: string) => {
            const res = await axiosInstance.post(`/api/ptm/sessions/${sessionId}/generate_slots/`);
            return res.data;
        },
        onSuccess: (data) => {
            toast.success(data.message || "Slots generated successfully");
            queryClient.invalidateQueries({ queryKey: ["ptm-sessions"] });
            queryClient.invalidateQueries({ queryKey: ["ptm-session-roster"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to generate slots");
        },
    });
}

export function usePublishPTMSession() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (sessionId: string) => {
            const res = await axiosInstance.post(`/api/ptm/sessions/${sessionId}/publish/`);
            return res.data;
        },
        onSuccess: () => {
            toast.success("PTM Session published and opened for parent bookings!");
            queryClient.invalidateQueries({ queryKey: ["ptm-sessions"] });
            queryClient.invalidateQueries({ queryKey: ["ptm-session-roster"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to publish session");
        },
    });
}

export function useCancelPTMSession() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (sessionId: string) => {
            const res = await axiosInstance.post(`/api/ptm/sessions/${sessionId}/cancel_session/`);
            return res.data;
        },
        onSuccess: () => {
            toast.success("PTM Session cancelled");
            queryClient.invalidateQueries({ queryKey: ["ptm-sessions"] });
            queryClient.invalidateQueries({ queryKey: ["ptm-session-roster"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to cancel session");
        },
    });
}

export function useBlockSlot() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (slotId: string) => {
            const res = await axiosInstance.post(`/api/ptm/slots/${slotId}/block/`);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Slot blocked");
            queryClient.invalidateQueries({ queryKey: ["ptm-session-roster"] });
            queryClient.invalidateQueries({ queryKey: ["teacher-ptm-schedule"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to block slot");
        },
    });
}

export function useUnblockSlot() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (slotId: string) => {
            const res = await axiosInstance.post(`/api/ptm/slots/${slotId}/unblock/`);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Slot unblocked");
            queryClient.invalidateQueries({ queryKey: ["ptm-session-roster"] });
            queryClient.invalidateQueries({ queryKey: ["teacher-ptm-schedule"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to unblock slot");
        },
    });
}

export function useRecordSlotFeedback() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({
            slotId,
            feedback,
            attended,
        }: {
            slotId: string;
            feedback: string;
            attended: boolean;
        }) => {
            const res = await axiosInstance.post(`/api/ptm/slots/${slotId}/feedback/`, {
                feedback,
                attended,
            });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Meeting notes and attendance saved");
            queryClient.invalidateQueries({ queryKey: ["ptm-session-roster"] });
            queryClient.invalidateQueries({ queryKey: ["teacher-ptm-schedule"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to save meeting notes");
        },
    });
}

export function useTeacherSchedule() {
    return useQuery<{
        teacher: { id: string; full_name: string; designation: string };
        slots: PTMSlot[];
    }>({
        queryKey: ["teacher-ptm-schedule"],
        queryFn: async () => {
            const res = await axiosInstance.get("/api/ptm/my-schedule/");
            return res.data;
        },
    });
}

// ---------------------------------------------------------------------------
// Parent Portal PTM Hooks
// ---------------------------------------------------------------------------

export function useParentPTMSessions() {
    return useQuery<PTMSession[]>({
        queryKey: ["parent-ptm-sessions"],
        queryFn: async () => {
            const res = await axiosInstance.get("/api/ptm/parent/sessions/");
            return res.data;
        },
    });
}

export function useParentAvailableSlots(sessionId: string | null, studentId: string | null) {
    return useQuery<{
        session: PTMSession;
        child: { id: string; full_name: string; enrollment_id: string };
        slots: {
            id: string;
            start_time: string;
            end_time: string;
            status: string;
            is_booked_for_this_child: boolean;
            teacher: {
                id: string;
                full_name: string;
                designation: string;
                department: string;
            };
            parent_notes: string;
        }[];
    }>({
        queryKey: ["parent-ptm-available-slots", sessionId, studentId],
        queryFn: async () => {
            if (!sessionId || !studentId) throw new Error("Session and Child are required");
            const res = await axiosInstance.get(
                `/api/ptm/parent/available-slots/?session_id=${sessionId}&student_id=${studentId}`
            );
            return res.data;
        },
        enabled: !!sessionId && !!studentId,
    });
}

export function useParentBookSlot() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({
            slotId,
            studentId,
            notes,
        }: {
            slotId: string;
            studentId: string;
            notes?: string;
        }) => {
            const res = await axiosInstance.post("/api/ptm/parent/book/", {
                slot_id: slotId,
                student_id: studentId,
                notes: notes || "",
            });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Meeting slot booked successfully!");
            queryClient.invalidateQueries({ queryKey: ["parent-ptm-available-slots"] });
            queryClient.invalidateQueries({ queryKey: ["parent-ptm-my-bookings"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to book slot");
        },
    });
}

export function useParentCancelBooking() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (slotId: string) => {
            const res = await axiosInstance.post("/api/ptm/parent/cancel/", {
                slot_id: slotId,
            });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Meeting slot cancelled");
            queryClient.invalidateQueries({ queryKey: ["parent-ptm-available-slots"] });
            queryClient.invalidateQueries({ queryKey: ["parent-ptm-my-bookings"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.error || "Failed to cancel booking");
        },
    });
}

export function useParentMyBookings() {
    return useQuery<PTMSlot[]>({
        queryKey: ["parent-ptm-my-bookings"],
        queryFn: async () => {
            const res = await axiosInstance.get("/api/ptm/parent/my-bookings/");
            return res.data;
        },
    });
}

