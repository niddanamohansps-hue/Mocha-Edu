// Quantities and money arrive from the API as decimal strings ("12.500", "85000.00"); they are
// never converted to JS numbers for arithmetic, only for display.

export interface ItemCategory {
    id: string;
    name: string;
    description: string;
}

export interface StockLocation {
    id: string;
    name: string;
    description: string;
    room: string | null;
    is_active: boolean;
}

export interface Supplier {
    id: string;
    name: string;
    contact_name: string;
    phone: string;
    email: string;
    address: string;
    notes: string;
    is_active: boolean;
}

export interface InventoryItem {
    id: string;
    sku: string;
    name: string;
    category: string;
    category_name: string;
    unit: string;
    description: string;
    reorder_level: string;
    is_active: boolean;
    on_hand: string;
    low_stock: boolean;
}

export interface ItemInput {
    sku: string;
    name: string;
    category: string;
    unit: string;
    description?: string;
    reorder_level?: string;
    is_active?: boolean;
}

export interface StockLevel {
    id: string;
    item: string;
    item_name: string;
    item_sku: string;
    unit: string;
    location: string;
    location_name: string;
    quantity: string;
}

export type MovementKind =
    | "receive"
    | "issue"
    | "return"
    | "adjust_in"
    | "adjust_out"
    | "write_off"
    | "transfer_out"
    | "transfer_in"
    | "reversal";

export const MOVEMENT_LABELS: Record<MovementKind, string> = {
    receive: "Received",
    issue: "Issued",
    return: "Returned",
    adjust_in: "Adjusted up",
    adjust_out: "Adjusted down",
    write_off: "Written off",
    transfer_out: "Transferred out",
    transfer_in: "Transferred in",
    reversal: "Reversal",
};

export interface StockMovement {
    id: string;
    item: string;
    item_name: string;
    location: string;
    location_name: string;
    kind: MovementKind;
    quantity_delta: string;
    balance_after: string;
    unit_cost: string | null;
    reason: string;
    reference: string;
    issued_to_staff: string | null;
    issued_to_note: string;
    reverses: string | null;
    reversed: boolean;
    created_at: string;
}

export interface MovementFilters {
    page: number;
    item: string;
    location: string;
    kind: MovementKind | "";
    search: string;
}

/** The stock actions a storekeeper can take, with the permission each one needs. */
export type StockActionKind = "receive" | "issue" | "return" | "adjust" | "write-off" | "transfer";

export interface StockActionInput {
    action: StockActionKind;
    item: string;
    location?: string;
    from_location?: string;
    to_location?: string;
    quantity: string;
    unit_cost?: string;
    reference?: string;
    reason?: string;
    direction?: "in" | "out";
    issued_to_staff?: string | null;
    issued_to_note?: string;
}

export interface PurchaseLine {
    id: string;
    item: string;
    item_name: string;
    item_sku: string;
    quantity: string;
    unit_cost: string;
    line_total: string;
}

export interface Purchase {
    id: string;
    supplier: string;
    supplier_name: string;
    location: string;
    location_name: string;
    reference: string;
    purchase_date: string;
    notes: string;
    status: "received" | "cancelled";
    total_cost: string;
    cancelled_at: string | null;
    cancellation_reason: string;
    lines: PurchaseLine[];
    created_at: string;
}

export interface PurchaseInput {
    supplier: string;
    location: string;
    purchase_date: string;
    reference?: string;
    notes?: string;
    lines: { item: string; quantity: string; unit_cost: string }[];
}

export interface PurchaseFilters {
    page: number;
    supplier: string;
    status: "" | "received" | "cancelled";
    search: string;
}

export type AssetStatus = "available" | "assigned" | "in_repair" | "lost" | "disposed";
export type AssetCondition = "new" | "good" | "fair" | "poor";

export const ASSET_STATUS_LABELS: Record<AssetStatus, string> = {
    available: "Available",
    assigned: "Assigned",
    in_repair: "In repair",
    lost: "Lost",
    disposed: "Disposed",
};

export const ASSET_CONDITION_LABELS: Record<AssetCondition, string> = {
    new: "New",
    good: "Good",
    fair: "Fair",
    poor: "Poor",
};

export interface AssetCategory {
    id: string;
    name: string;
    description: string;
}

export interface AssetAssignment {
    id: string;
    staff: string | null;
    staff_name: string | null;
    location: string | null;
    location_name: string | null;
    note: string;
    assigned_at: string;
    returned_at: string | null;
    return_condition: string;
}

export interface Asset {
    id: string;
    tag: string;
    name: string;
    category: string;
    category_name: string;
    serial_number: string;
    description: string;
    supplier: string | null;
    supplier_name: string | null;
    purchase_date: string | null;
    purchase_cost: string | null;
    condition: AssetCondition;
    status: AssetStatus;
    location: string | null;
    location_name: string | null;
    current_assignment: AssetAssignment | null;
    disposed_at: string | null;
    disposal_reason: string;
}

export interface AssetInput {
    tag: string;
    name: string;
    category: string;
    serial_number?: string;
    description?: string;
    supplier?: string | null;
    purchase_date?: string | null;
    purchase_cost?: string | null;
    condition?: AssetCondition;
    location?: string | null;
}

export interface AssetFilters {
    page: number;
    status: AssetStatus | "";
    category: string;
    search: string;
}

export interface AssetEvent {
    id: string;
    kind: string;
    from_status: string;
    to_status: string;
    note: string;
    created_at: string;
}

export interface MaintenanceRecord {
    id: string;
    reason: string;
    opened_at: string;
    closed_at: string | null;
    cost: string | null;
    notes: string;
}

export type AssetActionName = "assign" | "return" | "move" | "repair" | "complete-repair" | "lost" | "found" | "dispose";

export interface AssetSummary {
    total: number;
    by_status: Record<AssetStatus, number>;
    by_category: { category: string; count: number }[];
    purchase_cost_in_service: string;
}

export interface StaffOption {
    id: string;
    employee_id: string;
    first_name: string;
    last_name: string;
}
