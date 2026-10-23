// Money arrives from the API as decimal strings ("24000.00") and is never converted to a JS number
// for arithmetic, only for display.

export type ComponentKind = "earning" | "deduction";
export type Calculation = "fixed" | "percent_of_basic";

export interface SalaryComponent {
    id: string;
    name: string;
    code: string;
    kind: ComponentKind;
    calculation: Calculation;
    default_value: string;
    description: string;
    is_active: boolean;
    sort_order: number;
    assigned_count: number;
}

export interface ComponentInput {
    name: string;
    code: string;
    kind: ComponentKind;
    calculation: Calculation;
    default_value: string;
    description?: string;
    is_active?: boolean;
}

export interface StaffSalary {
    id: string;
    staff: string;
    staff_name: string;
    employee_id: string;
    basic_amount: string;
    effective_from: string;
    note: string;
}

export interface StaffComponentAssignment {
    id: string;
    staff: string;
    component: string;
    component_name: string;
    component_code: string;
    kind: ComponentKind;
    calculation: Calculation;
    value: string | null;
    effective_value: string;
    effective_from: string;
    effective_to: string | null;
}

export interface StructureLine {
    code: string;
    name: string;
    kind: "basic" | ComponentKind;
    amount: string;
    detail: string;
}

export interface PayStructure {
    staff: string;
    on_date: string;
    rounded_to_whole_rupee: boolean;
    lines: StructureLine[];
    basic: string;
    gross: string;
    deductions: string;
    net: string;
    net_is_negative: boolean;
}

export interface PayrollSettings {
    round_to_whole_rupee: boolean;
    require_separate_approver: boolean;
    is_default: boolean;
    currency: string;
}

export type RunStatus = "draft" | "calculated" | "approved" | "paid" | "cancelled";

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
    draft: "Not calculated yet",
    calculated: "Calculated, waiting for approval",
    approved: "Approved, waiting for payment",
    paid: "Paid",
    cancelled: "Cancelled",
};

export interface PayrollRun {
    id: string;
    year: number;
    month: number;
    month_label: string;
    period_start: string;
    period_end: string;
    status: RunStatus;
    notes: string;
    working_days: number | null;
    weekly_off_days: number[];
    round_to_whole_rupee: boolean;
    calculation_notes: {
        payslips?: number;
        skipped_no_salary?: string[];
        skipped_inactive?: number;
        negative_net?: number;
        unmarked_staff?: number;
    };
    payslip_count: number;
    total_gross: string;
    total_deductions: string;
    total_net: string;
    prepared_by_user_id: string | null;
    calculated_at: string | null;
    approved_at: string | null;
    paid_on: string | null;
    payment_method: string;
    payment_reference: string;
    cancelled_at: string | null;
    cancellation_reason: string;
}

export interface PayslipLine {
    id: string;
    code: string;
    name: string;
    kind: "basic" | ComponentKind;
    amount: string;
    detail: string;
}

export interface Payslip {
    id: string;
    run: string;
    run_status: RunStatus;
    month_label: string;
    staff: string;
    employee_id: string;
    staff_name: string;
    designation: string;
    department: string;
    basic_amount: string;
    gross_amount: string;
    deductions_amount: string;
    net_amount: string;
    net_is_negative: boolean;
    working_days: number;
    unpaid_days: string;
    unmarked_days: string;
}

export interface PayslipDetail extends Payslip {
    lines: PayslipLine[];
}

export interface PayrollAdjustment {
    id: string;
    run: string;
    staff: string;
    staff_name: string;
    employee_id: string;
    kind: ComponentKind;
    name: string;
    amount: string;
    reason: string;
}

export interface RunSummary {
    month_label: string;
    status: RunStatus;
    people: number;
    gross: string;
    deductions: string;
    net: string;
    unpaid_days_total: string;
    negative_net: number;
    unmarked_attendance: number;
    by_department: { department: string; people: number; gross: string; deductions: string; net: string }[];
    by_component: { code: string; name: string; kind: string; people: number; total: string }[];
}

export type PaymentMethod = "bank_transfer" | "cash" | "cheque" | "other";

export const PAYMENT_METHOD_LABELS: Record<PaymentMethod, string> = {
    bank_transfer: "Bank transfer",
    cash: "Cash",
    cheque: "Cheque",
    other: "Other",
};
