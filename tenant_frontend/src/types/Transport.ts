export type DriverRole = "driver" | "helper";

export interface Vehicle {
    id: string;
    registration_number: string;
    name: string;
    make_model: string;
    capacity: number;
    insurance_expiry: string | null;
    fitness_expiry: string | null;
    is_active: boolean;
    notes: string;
    routes_count: number;
}

export type VehicleInput = Omit<Vehicle, "id" | "routes_count">;

export interface Driver {
    id: string;
    full_name: string;
    role: DriverRole;
    phone: string;
    license_number: string;
    license_expiry: string | null;
    staff: string | null;
    staff_name: string;
    is_active: boolean;
    notes: string;
}

export type DriverInput = Omit<Driver, "id" | "staff_name">;

export interface Route {
    id: string;
    name: string;
    vehicle: string | null;
    vehicle_registration: string;
    capacity: number | null;
    driver: string | null;
    driver_name: string;
    helper: string | null;
    helper_name: string;
    start_point: string;
    end_point: string;
    monthly_fee: string;
    is_active: boolean;
    notes: string;
    seats_taken: number;
    stops_count: number;
}

export interface RouteInput {
    name: string;
    vehicle: string | null;
    driver: string | null;
    helper: string | null;
    start_point: string;
    end_point: string;
    monthly_fee: string;
    is_active: boolean;
    notes: string;
}

export interface RouteStop {
    id: string;
    route: string;
    route_name: string;
    name: string;
    sequence: number;
    pickup_time: string | null;
    drop_time: string | null;
    /** The stop's own fee, or null when it uses the route's fee. */
    monthly_fee: string | null;
    /** The fee that applies at this stop. */
    fee: string;
    students: number;
}

export interface StopInput {
    route: string;
    name: string;
    sequence: number;
    pickup_time: string | null;
    drop_time: string | null;
    monthly_fee: string | null;
}

export type SeatMode = "both" | "pickup" | "dropoff";

export const SEAT_MODE_LABELS: Record<SeatMode, string> = {
    both: "Both ways",
    pickup: "Pick-up only",
    dropoff: "Drop-off only",
};

export interface Seat {
    id: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    route: string;
    route_name: string;
    stop: string | null;
    stop_name: string;
    mode: SeatMode;
    pickup_note: string;
    monthly_fee: string;
    start_date: string;
    end_date: string | null;
    is_open: boolean;
}

export interface TransportBill {
    id: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    month: string;
    route_name: string;
    stop_name: string;
    amount: string;
}

export interface BillRunResult {
    month: string;
    billed: number;
    total: string;
    already_billed: number;
    no_fee: number;
    no_enrollment: string[];
}

export interface ExpiringDocument {
    kind: "vehicle" | "driver";
    id: string;
    subject: string;
    document: string;
    expiry: string;
    days_left: number;
}
