import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { apiError, ChargePreview } from "@/hooks/useFeeCharging";

export type HostelGender = "boys" | "girls" | "mixed";

export interface Hostel {
    id: string;
    name: string;
    gender: HostelGender;
    warden: string | null;
    warden_name: string | null;
    warden_phone: string;
    fee_structure: string | null;
    fee_structure_label: string | null;
    is_active: boolean;
    rooms: number;
    beds: number;
    occupied: number;
}

export interface HostelRoom {
    id: string;
    hostel: string;
    number: string;
    floor: string;
    capacity: number;
    is_active: boolean;
    occupied: number;
    occupants: { allocation: string; student: string; name: string; since: string }[];
}

export interface HostelStay {
    id: string;
    student: string;
    student_name: string;
    room: string;
    room_number: string;
    hostel_name: string;
    warden_phone: string;
    start_date: string;
    end_date: string | null;
    note: string;
}

/** "2026-11-11" -> "11 Nov 2026". */
export const showDate = (iso: string) =>
    new Date(`${iso}T00:00:00`).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });

const rows = <T,>(d: T[] | { results: T[] }) => (Array.isArray(d) ? d : d.results);

export const useHostels = () =>
    useQuery<Hostel[]>({ queryKey: ["hostel", "list"], queryFn: async () => rows((await axiosInstance.get("/hostel/hostels/")).data) });

export const useRooms = (hostelId: string | undefined) =>
    useQuery<HostelRoom[]>({
        queryKey: ["hostel", "rooms", hostelId],
        enabled: !!hostelId,
        queryFn: async () => rows((await axiosInstance.get(`/hostel/rooms/?hostel=${hostelId}&page_size=500`)).data),
    });

function useHostelMutation<T>(fn: (data: T) => Promise<unknown>, ok: string, fail: string) {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: fn,
        onSuccess: () => {
            qc.invalidateQueries({ queryKey: ["hostel"] });
            if (ok) toast.success(ok);
        },
        onError: (e) => toast.error(apiError(e, fail)),
    });
}

export const useSaveHostel = () =>
    useHostelMutation(
        async ({ id, ...data }: Partial<Hostel>) =>
            id ? (await axiosInstance.patch(`/hostel/hostels/${id}/`, data)).data : (await axiosInstance.post("/hostel/hostels/", data)).data,
        "Hostel saved",
        "Could not save the hostel",
    );

export const useSaveRoom = () =>
    useHostelMutation(
        async ({ id, ...data }: Partial<HostelRoom>) =>
            id ? (await axiosInstance.patch(`/hostel/rooms/${id}/`, data)).data : (await axiosInstance.post("/hostel/rooms/", data)).data,
        "Room saved",
        "Could not save the room",
    );

export const useAllocate = () =>
    useHostelMutation(
        async (data: { student: string; room: string; start_date?: string }) => (await axiosInstance.post("/hostel/allocations/", data)).data,
        "Room given",
        "Could not give the room",
    );

export const useVacate = () =>
    useHostelMutation(
        async ({ id, end_date }: { id: string; end_date?: string }) =>
            (await axiosInstance.post(`/hostel/allocations/${id}/vacate/`, end_date ? { end_date } : {})).data,
        "Student moved out",
        "Could not record the move-out",
    );

export const useHostelChargePreview = (hostelId: string | undefined, enabled: boolean) =>
    useQuery<ChargePreview>({
        queryKey: ["hostel", "charge", hostelId],
        enabled: !!hostelId && enabled,
        retry: false,
        queryFn: async () => (await axiosInstance.get(`/hostel/hostels/${hostelId}/charge/`)).data,
    });

export const useChargeHostel = (hostelId: string) => {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async () => (await axiosInstance.post(`/hostel/hostels/${hostelId}/charge/`)).data as ChargePreview,
        onSuccess: (d) => {
            qc.invalidateQueries({ queryKey: ["hostel"] });
            qc.invalidateQueries({ queryKey: ["fees"] });
            toast.success(d.fees_to_create ? `Charged ${d.students_to_charge} boarders (${d.fees_to_create} fees)` : "Every boarder was already charged");
        },
        onError: (e) => toast.error(apiError(e, "Could not charge the hostel fee")),
    });
};

export const useStudentHostel = (studentId: string | undefined) =>
    useQuery<{ current: HostelStay | null; history: HostelStay[] }>({
        queryKey: ["hostel", "student", studentId],
        enabled: !!studentId,
        retry: false,
        queryFn: async () => (await axiosInstance.get(`/hostel/students/${studentId}/`)).data,
    });
