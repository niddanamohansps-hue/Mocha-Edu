import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { PaginatedResponse } from "@/types/Pagination";
import {
    BillRunResult,
    Driver,
    DriverInput,
    ExpiringDocument,
    Route,
    RouteInput,
    RouteStop,
    Seat,
    SeatMode,
    StopInput,
    TransportBill,
    Vehicle,
    VehicleInput,
} from "@/types/Transport";

const KEY = "transport";
const errorMessage = inventoryErrorMessage; // the same DRF error shapes
const EVERYTHING = 100; // option lists: the largest page the server allows

function stripEmpty(params: Record<string, unknown>) {
    return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null));
}

function useScopedQuery<T>(parts: unknown[], path: string, params: Record<string, unknown> = {}, enabled = true) {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, ...parts, user?.id, params],
        queryFn: async () => (await axiosInstance.get(path, { params: stripEmpty(params) })).data as T,
        enabled: !!user && enabled,
    });
}

function useMutate<TInput, TResult = unknown>(run: (input: TInput) => Promise<TResult>, success: string, failure: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: run,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            if (success) toast.success(success);
        },
        onError: (error: unknown) => toast.error(errorMessage(error, failure)),
    });
}

// --- Vehicles ------------------------------------------------------------------------------------

export const useVehicles = (params: { page: number; search: string }) =>
    useScopedQuery<PaginatedResponse<Vehicle>>(["vehicles"], "/transport/vehicles/", { ...params });

export const useAllVehicles = () =>
    useScopedQuery<PaginatedResponse<Vehicle>>(["vehicles", "all"], "/transport/vehicles/", { page_size: EVERYTHING });

export const useSaveVehicle = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<VehicleInput> }) =>
            (id ? await axiosInstance.patch(`/transport/vehicles/${id}/`, input) : await axiosInstance.post("/transport/vehicles/", input)).data as Vehicle,
        "Vehicle saved",
        "Could not save the vehicle"
    );

export const useDeleteVehicle = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/transport/vehicles/${id}/`), "Vehicle deleted", "Could not delete the vehicle");

// --- Drivers and helpers -------------------------------------------------------------------------

export const useDrivers = (params: { page: number; search: string }) =>
    useScopedQuery<PaginatedResponse<Driver>>(["drivers"], "/transport/drivers/", { ...params });

export const useAllDrivers = () =>
    useScopedQuery<PaginatedResponse<Driver>>(["drivers", "all"], "/transport/drivers/", { page_size: EVERYTHING });

export const useSaveDriver = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<DriverInput> }) =>
            (id ? await axiosInstance.patch(`/transport/drivers/${id}/`, input) : await axiosInstance.post("/transport/drivers/", input)).data as Driver,
        "Saved",
        "Could not save"
    );

export const useDeleteDriver = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/transport/drivers/${id}/`), "Deleted", "Could not delete");

// --- Routes and stops ----------------------------------------------------------------------------

export const useRoutes = (params: { page: number; search: string }) =>
    useScopedQuery<PaginatedResponse<Route>>(["routes"], "/transport/routes/", { ...params });

export const useAllRoutes = () =>
    useScopedQuery<PaginatedResponse<Route>>(["routes", "all"], "/transport/routes/", { page_size: EVERYTHING });

export const useSaveRoute = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<RouteInput> }) =>
            (id ? await axiosInstance.patch(`/transport/routes/${id}/`, input) : await axiosInstance.post("/transport/routes/", input)).data as Route,
        "Route saved",
        "Could not save the route"
    );

export const useDeleteRoute = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/transport/routes/${id}/`), "Route deleted", "Could not delete the route");

export const useRouteStops = (route: string) =>
    useScopedQuery<RouteStop[]>(["stops", route], "/transport/stops/", { route }, !!route);

export const useSaveStop = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<StopInput> }) =>
            (id ? await axiosInstance.patch(`/transport/stops/${id}/`, input) : await axiosInstance.post("/transport/stops/", input)).data as RouteStop,
        "Stop saved",
        "Could not save the stop"
    );

export const useDeleteStop = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/transport/stops/${id}/`), "Stop deleted", "Could not delete the stop");

export const useRouteRoster = (route: string, enabled: boolean) =>
    useScopedQuery<Seat[]>(["roster", route], `/transport/routes/${route}/students/`, {}, !!route && enabled);

// --- Seats ---------------------------------------------------------------------------------------

export const useSeats = (params: { page: number; search: string; route: string; open: "" | "true" | "false" }) =>
    useScopedQuery<PaginatedResponse<Seat>>(["seats"], "/transport/seats/", { ...params });

export const useAssignSeat = () =>
    useMutate(
        async (input: { student: string; route: string; stop: string | null; start_date: string; mode: SeatMode; pickup_note: string }) =>
            (await axiosInstance.post("/transport/seats/", input)).data as Seat,
        "Seat saved",
        "Could not give the seat"
    );

export const useEndSeat = () =>
    useMutate(
        async ({ id, end_date }: { id: string; end_date?: string }) =>
            (await axiosInstance.post(`/transport/seats/${id}/end/`, end_date ? { end_date } : {})).data as Seat,
        "Seat ended",
        "Could not end the seat"
    );

// --- Billing and reports -------------------------------------------------------------------------

export const useBills = (params: { page: number; month: string; search: string }) =>
    useScopedQuery<PaginatedResponse<TransportBill>>(["bills"], "/transport/bills/", { ...params });

export const useRunBilling = () =>
    useMutate(
        async (input: { month: string; due_date?: string }) =>
            (await axiosInstance.post("/transport/bills/run/", input)).data as BillRunResult,
        "",
        "Could not bill the month"
    );

export const useExpiringDocuments = (days: number) =>
    useScopedQuery<ExpiringDocument[]>(["expiring"], "/transport/expiring/", { days });
