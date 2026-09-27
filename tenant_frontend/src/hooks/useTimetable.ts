import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import {
    MyTimetableResponse,
    Period,
    Room,
    TimetableEntry,
    TimetableEntryInput,
    TimetableSubstitution,
} from "@/types/Timetable";

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

export const usePeriods = (academicYear?: string) => {
    return useQuery({
        queryKey: ["timetable", "periods", academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/timetable/periods/${params}`);
            return response.data as Period[];
        },
    });
};

export const useCreatePeriod = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<Period>) => {
            const response = await axiosInstance.post("/timetable/periods/", data);
            return response.data as Period;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["timetable", "periods"] });
            toast.success("Period created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create period")),
    });
};

export const useRooms = () => {
    return useQuery({
        queryKey: ["timetable", "rooms"],
        queryFn: async () => {
            const response = await axiosInstance.get("/timetable/rooms/");
            return response.data as Room[];
        },
    });
};

export const useCreateRoom = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<Room>) => {
            const response = await axiosInstance.post("/timetable/rooms/", data);
            return response.data as Room;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["timetable", "rooms"] });
            toast.success("Room created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create room")),
    });
};

export const useSectionTimetable = (sectionId: string | undefined, academicYear?: string) => {
    return useQuery({
        queryKey: ["timetable", "section", sectionId, academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(
                `/timetable/sections/${sectionId}/timetable/${params}`
            );
            return response.data as TimetableEntry[];
        },
        enabled: !!sectionId,
    });
};

export const useMyTimetable = (academicYear?: string) => {
    return useQuery({
        queryKey: ["timetable", "my-timetable", academicYear],
        queryFn: async () => {
            const params = academicYear ? `?academic_year=${academicYear}` : "";
            const response = await axiosInstance.get(`/timetable/my-timetable/${params}`);
            return response.data as MyTimetableResponse;
        },
    });
};

export const useCreateTimetableEntry = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: TimetableEntryInput) => {
            const response = await axiosInstance.post("/timetable/entries/", data);
            return response.data as TimetableEntry;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["timetable"] });
            toast.success("Timetable entry created");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create entry")),
    });
};

export const useUpdateTimetableEntry = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: Partial<TimetableEntryInput> }) => {
            const response = await axiosInstance.patch(`/timetable/entries/${id}/`, data);
            return response.data as TimetableEntry;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["timetable"] });
            toast.success("Timetable entry updated");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to update entry")),
    });
};

export const useDeleteTimetableEntry = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/timetable/entries/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["timetable"] });
            toast.success("Timetable entry deleted");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to delete entry")),
    });
};

export const useCreateSubstitution = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({
            entryId,
            data,
        }: {
            entryId: string;
            data: { date: string; substitute_instructor: string; reason?: string };
        }) => {
            const response = await axiosInstance.post(`/timetable/entries/${entryId}/substitute/`, data);
            return response.data as TimetableSubstitution;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["timetable", "substitutions"] });
            toast.success("Substitution recorded");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to create substitution")),
    });
};

export const useSubstitutions = () => {
    return useQuery({
        queryKey: ["timetable", "substitutions"],
        queryFn: async () => {
            const response = await axiosInstance.get("/timetable/substitutions/");
            return response.data as TimetableSubstitution[];
        },
    });
};

export const useDeleteSubstitution = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/timetable/substitutions/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["timetable", "substitutions"] });
            toast.success("Substitution removed");
        },
        onError: (error: any) => toast.error(errorMessage(error, "Failed to remove substitution")),
    });
};
