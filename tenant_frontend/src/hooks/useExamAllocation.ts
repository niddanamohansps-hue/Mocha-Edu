import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type { AdmitCardData, DutyRow, MarksProgress, RankList, SittingPlan, SittingSummary } from "@/types/ExamAllocation";

const KEY = "exam-allocation";
const BASE = "/examinations";

/** The API answers a rule failure ("not enough seats...") with a one-item list; show that message. */
export function allocationError(error: unknown, fallback: string): string {
    const data = (error as { response?: { data?: unknown } })?.response?.data;
    if (Array.isArray(data) && data.length) return String(data[0]);
    if (typeof data === "string") return data;
    if (data && typeof data === "object") {
        const first = Object.values(data as Record<string, unknown>)[0];
        if (Array.isArray(first) && first.length) return String(first[0]);
        if (typeof first === "string") return first;
    }
    return fallback;
}

function useAllocationMutation<TVars>(run: (vars: TVars) => Promise<unknown>, success: string, failure: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: run,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success(success);
        },
        onError: (error: unknown) => toast.error(allocationError(error, failure)),
    });
}

export const useSittings = (examination: string | undefined) =>
    useQuery({
        queryKey: [KEY, "sittings", examination],
        enabled: !!examination,
        queryFn: async () =>
            (await axiosInstance.get<SittingSummary[]>(`${BASE}/exam-sittings/`, { params: { examination } })).data,
    });

export const useSyncSittings = () =>
    useAllocationMutation(
        async (examination: string) => (await axiosInstance.post(`${BASE}/exam-sittings/sync/`, { examination })).data,
        "Sittings updated from the exam schedule",
        "Could not update the sittings",
    );

export const useSittingPlan = (sitting: string | undefined) =>
    useQuery({
        queryKey: [KEY, "plan", sitting],
        enabled: !!sitting,
        queryFn: async () => (await axiosInstance.get<SittingPlan>(`${BASE}/exam-sittings/${sitting}/`)).data,
    });

export const useAllocateRooms = () =>
    useAllocationMutation(
        async (vars: { sitting: string; mix: boolean; rooms?: string[] }) =>
            (await axiosInstance.post(`${BASE}/exam-sittings/${vars.sitting}/allocate-rooms/`, { mix: vars.mix, rooms: vars.rooms })).data,
        "Rooms allocated",
        "Could not allocate rooms",
    );

export const useMoveSeat = () =>
    useAllocationMutation(
        async (vars: { sitting: string; student: string; room: string; seat: number }) =>
            (await axiosInstance.post(`${BASE}/exam-sittings/${vars.sitting}/move-seat/`, {
                student: vars.student, room: vars.room, seat: vars.seat,
            })).data,
        "Seat updated",
        "Could not move the student",
    );

export const useAllocateInvigilators = () =>
    useAllocationMutation(
        async (vars: { sitting: string; per_room: number; avoid_own_class: boolean; include_non_teaching: boolean }) => {
            const { sitting, ...body } = vars;
            return (await axiosInstance.post(`${BASE}/exam-sittings/${sitting}/allocate-invigilators/`, body)).data;
        },
        "Invigilators allocated and notified",
        "Could not allocate invigilators",
    );

export const useReplaceInvigilator = () =>
    useAllocationMutation(
        async (vars: { duty: string; staff: string }) =>
            (await axiosInstance.post(`${BASE}/exam-invigilations/${vars.duty}/replace/`, { staff: vars.staff })).data,
        "Invigilator replaced",
        "Could not replace the invigilator",
    );

export const useMyDuties = () =>
    useQuery({
        queryKey: [KEY, "mine"],
        queryFn: async () => (await axiosInstance.get<DutyRow[]>(`${BASE}/my-duties/`)).data,
    });

export const useDutyRoster = (examination: string | undefined) =>
    useQuery({
        queryKey: [KEY, "roster", examination],
        enabled: !!examination,
        queryFn: async () => (await axiosInstance.get<DutyRow[]>(`${BASE}/duty-roster/`, { params: { examination } })).data,
    });

export const useAdmitCards = (examination: string | undefined, section: string | undefined) =>
    useQuery({
        queryKey: [KEY, "admit-cards", examination, section],
        enabled: !!examination && !!section,
        queryFn: async () =>
            (await axiosInstance.get<AdmitCardData>(`${BASE}/admit-cards/`, { params: { examination, section } })).data,
    });

export const useMarksProgress = (examination: string | undefined) =>
    useQuery({
        queryKey: [KEY, "marks-progress", examination],
        enabled: !!examination,
        queryFn: async () =>
            (await axiosInstance.get<MarksProgress>(`${BASE}/marks-progress/`, { params: { examination } })).data,
    });

export const useRemindTeachers = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (examination: string) =>
            (await axiosInstance.post<{ teachers: number; papers: number; unassigned: number; already_reminded: number }>(
                `${BASE}/examinations/${examination}/remind-marks/`,
            )).data,
        onSuccess: (result) => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            const parts = [`${result.teachers} teacher(s) reminded`];
            if (result.already_reminded) parts.push(`${result.already_reminded} already reminded today`);
            if (result.unassigned) parts.push(`${result.unassigned} paper(s) have no teacher assigned`);
            toast.success(parts.join(", "));
        },
        onError: (error: unknown) => toast.error(allocationError(error, "Could not send the reminders")),
    });
};

export const useSetMarksDueDate = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (vars: { examination: string; date: string | null }) =>
            (await axiosInstance.patch(`${BASE}/examinations/${vars.examination}/`, { marks_due_date: vars.date })).data,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            queryClient.invalidateQueries({ queryKey: ["examinations"] });
            toast.success("Due date saved");
        },
        onError: (error: unknown) => toast.error(allocationError(error, "Could not save the due date")),
    });
};

export const useRankList = (
    examination: string | undefined,
    scope: "section" | "level",
    target: string | undefined,
    includeFailed: boolean,
    enabled: boolean,
) =>
    useQuery({
        queryKey: [KEY, "rank-list", examination, scope, target, includeFailed],
        enabled: enabled && !!examination && !!target,
        queryFn: async () =>
            (await axiosInstance.get<RankList>(`${BASE}/rank-list/`, {
                params: { examination, [scope]: target, include_failed: includeFailed },
            })).data,
    });
