import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { useAcademicYear } from "@/providers/AcademicYearProvider";
import {
    CalendarEventItem,
    CalendarEventInput,
    CalendarEventFilters,
} from "@/types/Calendar";

export function calendarErrorMessage(error: unknown, fallback: string): string {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data || typeof data !== "object") return fallback;
    if (typeof data.detail === "string") return data.detail;
    for (const key of Object.keys(data)) {
        const value = data[key];
        const text = Array.isArray(value) ? value[0] : value;
        if (typeof text === "string") return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
    }
    return fallback;
}

const KEY = "calendar-events";

export const useCalendarEvents = (filters?: CalendarEventFilters) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "list", user?.id, filters],
        queryFn: async () => {
            const params: Record<string, string | boolean> = {};
            if (filters?.date) params.date = filters.date;
            if (filters?.date_from) params.date_from = filters.date_from;
            if (filters?.date_to) params.date_to = filters.date_to;
            if (filters?.start_date) params.start_date = filters.start_date;
            if (filters?.end_date) params.end_date = filters.end_date;
            if (filters?.month) params.month = filters.month;
            if (filters?.event_type) params.event_type = filters.event_type;
            if (filters?.is_holiday !== undefined && filters?.is_holiday !== "") {
                params.is_holiday = filters.is_holiday;
            }
            if (filters?.status) params.status = filters.status;
            if (filters?.academic_year) params.academic_year = filters.academic_year;
            if (filters?.audience) params.audience = filters.audience;
            if (filters?.search) params.search = filters.search;

            const response = await axiosInstance.get("/calendar-events/", { params });
            // May be paginated or array
            const data = response.data;
            if (Array.isArray(data)) {
                return data as CalendarEventItem[];
            }
            if (data && Array.isArray(data.results)) {
                return data.results as CalendarEventItem[];
            }
            return [] as CalendarEventItem[];
        },
        enabled: !!user,
    });
};

export const useUpcomingEvents = (limit: number = 5, audience?: string) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: ["upcoming-events", user?.id, limit, audience],
        queryFn: async () => {
            const params: Record<string, string | number> = { limit };
            if (audience) params.audience = audience;
            const response = await axiosInstance.get("/calendar-events/upcoming/", { params });
            return (response.data || []) as CalendarEventItem[];
        },
        enabled: !!user,
    });
};

export const useCalendarHolidays = (filters?: { academic_year?: string; date_from?: string; date_to?: string }) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: ["calendar-holidays", user?.id, filters],
        queryFn: async () => {
            const params: Record<string, string> = {};
            if (filters?.academic_year) params.academic_year = filters.academic_year;
            if (filters?.date_from) params.date_from = filters.date_from;
            if (filters?.date_to) params.date_to = filters.date_to;
            const response = await axiosInstance.get("/calendar-events/holidays/", { params });
            return (response.data || []) as CalendarEventItem[];
        },
        enabled: !!user,
    });
};

export const useCalendarEvent = (id: string) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "detail", user?.id, id],
        queryFn: async () => {
            const response = await axiosInstance.get(`/calendar-events/${id}/`);
            return response.data as CalendarEventItem;
        },
        enabled: !!user && !!id,
    });
};

export const useCreateCalendarEvent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (payload: CalendarEventInput) => {
            const response = await axiosInstance.post("/calendar-events/", payload);
            return response.data as CalendarEventItem;
        },
        onSuccess: (data) => {
            toast.success(`Event "${data.title}" created successfully`);
            queryClient.invalidateQueries({ queryKey: [KEY] });
            queryClient.invalidateQueries({ queryKey: ["upcoming-events"] });
            queryClient.invalidateQueries({ queryKey: ["calendar-holidays"] });
        },
        onError: (err) => {
            toast.error(calendarErrorMessage(err, "Failed to create event"));
        },
    });
};

export const useUpdateCalendarEvent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: Partial<CalendarEventInput> }) => {
            const response = await axiosInstance.patch(`/calendar-events/${id}/`, data);
            return response.data as CalendarEventItem;
        },
        onSuccess: (data) => {
            toast.success(`Event "${data.title}" updated successfully`);
            queryClient.invalidateQueries({ queryKey: [KEY] });
            queryClient.invalidateQueries({ queryKey: ["upcoming-events"] });
            queryClient.invalidateQueries({ queryKey: ["calendar-holidays"] });
        },
        onError: (err) => {
            toast.error(calendarErrorMessage(err, "Failed to update event"));
        },
    });
};

export const useDeleteCalendarEvent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/calendar-events/${id}/`);
            return id;
        },
        onSuccess: () => {
            toast.success("Event deleted successfully");
            queryClient.invalidateQueries({ queryKey: [KEY] });
            queryClient.invalidateQueries({ queryKey: ["upcoming-events"] });
            queryClient.invalidateQueries({ queryKey: ["calendar-holidays"] });
        },
        onError: (err) => {
            toast.error(calendarErrorMessage(err, "Failed to delete event"));
        },
    });
};

export const usePublishCalendarEvent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            const response = await axiosInstance.post(`/calendar-events/${id}/publish/`);
            return response.data as CalendarEventItem;
        },
        onSuccess: (data) => {
            toast.success(`Event "${data.title}" published`);
            queryClient.invalidateQueries({ queryKey: [KEY] });
            queryClient.invalidateQueries({ queryKey: ["upcoming-events"] });
            queryClient.invalidateQueries({ queryKey: ["calendar-holidays"] });
        },
        onError: (err) => {
            toast.error(calendarErrorMessage(err, "Failed to publish event"));
        },
    });
};

export const useCancelCalendarEvent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            const response = await axiosInstance.post(`/calendar-events/${id}/cancel/`);
            return response.data as CalendarEventItem;
        },
        onSuccess: (data) => {
            toast.success(`Event "${data.title}" cancelled`);
            queryClient.invalidateQueries({ queryKey: [KEY] });
            queryClient.invalidateQueries({ queryKey: ["upcoming-events"] });
            queryClient.invalidateQueries({ queryKey: ["calendar-holidays"] });
        },
        onError: (err) => {
            toast.error(calendarErrorMessage(err, "Failed to cancel event"));
        },
    });
};

export const useAttendanceHolidayAdvisory = (date?: string) => {
    const { data: user } = useMe();
    const { selectedYear } = useAcademicYear();

    return useQuery({
        queryKey: [KEY, "advisory", user?.id, date, selectedYear?.id],
        queryFn: async () => {
            if (!date) return [] as CalendarEventItem[];
            const params: Record<string, string | boolean> = {
                date,
                is_holiday: true,
                status: "PUBLISHED",
            };
            if (selectedYear?.id) {
                params.academic_year = selectedYear.id;
            }

            const response = await axiosInstance.get("/calendar-events/", { params });
            const data = response.data;
            const items: CalendarEventItem[] = Array.isArray(data)
                ? data
                : Array.isArray(data?.results)
                ? data.results
                : [];

            // Strict defense-in-depth:
            // 1. Must be published
            // 2. Must be holiday or closure or is_holiday flag
            // 3. Must cover the selected date
            return items.filter((evt) => {
                const status = (evt.status || "").toUpperCase();
                if (status !== "PUBLISHED") return false;
                const type = (evt.event_type || "").toUpperCase();
                const isHolidayOrClosure = evt.is_holiday || type === "HOLIDAY" || type === "CLOSURE";
                if (!isHolidayOrClosure) return false;
                return evt.start_date <= date && date <= evt.end_date;
            });
        },
        enabled: !!user && !!date && /^\d{4}-\d{2}-\d{2}$/.test(date),
        staleTime: 60 * 1000,
    });
};


