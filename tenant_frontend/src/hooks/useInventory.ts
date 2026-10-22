import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { PaginatedResponse } from "@/types/Pagination";
import {
    Asset,
    AssetActionName,
    AssetCategory,
    AssetEvent,
    AssetFilters,
    AssetInput,
    AssetSummary,
    AssetAssignment,
    InventoryItem,
    ItemCategory,
    ItemInput,
    MaintenanceRecord,
    MovementFilters,
    Purchase,
    PurchaseFilters,
    PurchaseInput,
    StockActionInput,
    StockLevel,
    StockLocation,
    StockMovement,
    Supplier,
} from "@/types/Inventory";

/** First readable message from a DRF error body (field errors, `detail`, or `error`). */
export function inventoryErrorMessage(error: unknown, fallback: string) {
    const data = (error as { response?: { data?: unknown } })?.response?.data;
    if (!data || typeof data !== "object") return fallback;
    const body = data as Record<string, unknown>;
    if (typeof body.detail === "string") return body.detail;
    if (typeof body.error === "string") return body.error;
    for (const key of Object.keys(body)) {
        const value = body[key];
        const text = Array.isArray(value) ? value[0] : value;
        if (typeof text === "string") return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
    }
    return fallback;
}

const KEY = "inventory";

function useScopedQuery<T>(parts: unknown[], path: string, params: Record<string, unknown> = {}, enabled = true) {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, ...parts, user?.id, params],
        queryFn: async () => (await axiosInstance.get(path, { params: stripEmpty(params) })).data as T,
        enabled: !!user && enabled,
    });
}

function stripEmpty(params: Record<string, unknown>) {
    return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null));
}

/** Every page of a small configuration list (categories, locations, suppliers) for pickers. */
export function useAllOf<T>(resource: string, params: Record<string, unknown> = {}) {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "all", resource, user?.id, params],
        queryFn: async () => {
            const rows: T[] = [];
            for (let page = 1; page <= 20; page++) {
                const data = (await axiosInstance.get(`/inventory/${resource}/`, { params: { ...stripEmpty(params), page } }))
                    .data as PaginatedResponse<T>;
                rows.push(...data.results);
                if (!data.next) break;
            }
            return rows;
        },
        enabled: !!user,
    });
}

// --- Items and stock ---------------------------------------------------------------------------

export const useItems = (filters: { page: number; search: string; category: string; low_stock: boolean; is_active: "" | "true" | "false" }) =>
    useScopedQuery<PaginatedResponse<InventoryItem>>(["items"], "/inventory/items/", {
        page: filters.page,
        search: filters.search,
        category: filters.category,
        is_active: filters.is_active,
        low_stock: filters.low_stock ? "true" : "",
    });

export const useStockLevels = (itemId: string | null) =>
    useScopedQuery<PaginatedResponse<StockLevel>>(["levels", itemId], "/inventory/stock/", { item: itemId, hide_empty: "true" }, !!itemId);

export const useMovements = (filters: MovementFilters) =>
    useScopedQuery<PaginatedResponse<StockMovement>>(["movements"], "/inventory/movements/", { ...filters });

function useInventoryMutation<TInput, TResult = unknown>(
    run: (input: TInput) => Promise<TResult>,
    success: string,
    failure: string
) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: run,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success(success);
        },
        onError: (error: unknown) => toast.error(inventoryErrorMessage(error, failure)),
    });
}

export const useSaveItem = () =>
    useInventoryMutation(
        async ({ id, input }: { id?: string; input: Partial<ItemInput> }) =>
            (id
                ? await axiosInstance.patch(`/inventory/items/${id}/`, input)
                : await axiosInstance.post("/inventory/items/", input)
            ).data as InventoryItem,
        "Item saved",
        "Could not save the item"
    );

export const useStockAction = () =>
    useInventoryMutation(
        async ({ action, ...body }: StockActionInput) =>
            (await axiosInstance.post(`/inventory/movements/${action}/`, body)).data,
        "Stock updated",
        "Could not update the stock"
    );

export const useReverseMovement = () =>
    useInventoryMutation(
        async ({ id, reason }: { id: string; reason: string }) =>
            (await axiosInstance.post(`/inventory/movements/${id}/reverse/`, { reason })).data,
        "Movement reversed",
        "Could not reverse the movement"
    );

// --- Configuration lists -----------------------------------------------------------------------

export type ConfigResource = "categories" | "locations" | "suppliers" | "asset-categories";
type ConfigRow = ItemCategory | StockLocation | Supplier | AssetCategory;

export const useSaveConfig = (resource: ConfigResource) =>
    useInventoryMutation(
        async ({ id, input }: { id?: string; input: Record<string, unknown> }) =>
            (id
                ? await axiosInstance.patch(`/inventory/${resource}/${id}/`, input)
                : await axiosInstance.post(`/inventory/${resource}/`, input)
            ).data as ConfigRow,
        "Saved",
        "Could not save"
    );

export const useDeleteConfig = (resource: ConfigResource) =>
    useInventoryMutation(
        async (id: string) => (await axiosInstance.delete(`/inventory/${resource}/${id}/`)).data,
        "Deleted",
        "Could not delete"
    );

// --- Purchases ---------------------------------------------------------------------------------

export const usePurchases = (filters: PurchaseFilters) =>
    useScopedQuery<PaginatedResponse<Purchase>>(["purchases"], "/inventory/purchases/", { ...filters });

export const useCreatePurchase = () =>
    useInventoryMutation(
        async (input: PurchaseInput) => (await axiosInstance.post("/inventory/purchases/", input)).data as Purchase,
        "Purchase recorded and stock received",
        "Could not record the purchase"
    );

export const useCancelPurchase = () =>
    useInventoryMutation(
        async ({ id, reason }: { id: string; reason: string }) =>
            (await axiosInstance.post(`/inventory/purchases/${id}/cancel/`, { reason })).data as Purchase,
        "Purchase cancelled",
        "Could not cancel the purchase"
    );

// --- Assets ------------------------------------------------------------------------------------

export const useAssets = (filters: AssetFilters) =>
    useScopedQuery<PaginatedResponse<Asset>>(["assets"], "/inventory/assets/", { ...filters });

export const useAsset = (id: string) =>
    useScopedQuery<Asset>(["asset", id], `/inventory/assets/${id}/`, {}, !!id);

export const useAssetSummary = () => useScopedQuery<AssetSummary>(["asset-summary"], "/inventory/assets/summary/");

export const useAssetHistory = (id: string) =>
    useScopedQuery<PaginatedResponse<AssetEvent>>(["asset-history", id], `/inventory/assets/${id}/history/`, {}, !!id);

export const useAssetAssignments = (id: string) =>
    useScopedQuery<PaginatedResponse<AssetAssignment>>(["asset-assignments", id], `/inventory/assets/${id}/assignments/`, {}, !!id);

export const useAssetMaintenance = (id: string) =>
    useScopedQuery<PaginatedResponse<MaintenanceRecord>>(["asset-maintenance", id], `/inventory/assets/${id}/maintenance/`, {}, !!id);

export const useSaveAsset = () =>
    useInventoryMutation(
        async ({ id, input }: { id?: string; input: Partial<AssetInput> }) =>
            (id
                ? await axiosInstance.patch(`/inventory/assets/${id}/`, input)
                : await axiosInstance.post("/inventory/assets/", input)
            ).data as Asset,
        "Asset saved",
        "Could not save the asset"
    );

export const useAssetAction = () =>
    useInventoryMutation(
        async ({ id, action, body }: { id: string; action: AssetActionName; body: Record<string, unknown> }) =>
            (await axiosInstance.post(`/inventory/assets/${id}/${action}/`, body)).data as Asset,
        "Asset updated",
        "Could not update the asset"
    );

// --- Alert setting -----------------------------------------------------------------------------

export const useLowStockAlertSetting = (enabled: boolean) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "alert-setting", user?.id],
        queryFn: async () =>
            (await axiosInstance.get("/notifications/settings/")).data as { low_stock_alerts_enabled: boolean },
        enabled: !!user && enabled,
    });
};

export const useUpdateLowStockAlertSetting = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (value: boolean) =>
            (await axiosInstance.patch("/notifications/settings/", { low_stock_alerts_enabled: value })).data,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY, "alert-setting"] });
            toast.success("Alert setting saved");
        },
        onError: (error: unknown) => toast.error(inventoryErrorMessage(error, "Could not save the setting")),
    });
};
