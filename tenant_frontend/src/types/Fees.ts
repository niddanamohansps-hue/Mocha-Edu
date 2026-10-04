export interface FeeHead {
    id: string;
    name: string;
    description: string;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export const FEE_FREQUENCY_CHOICES = ["one_time", "monthly", "term", "annual"] as const;
export type FeeFrequency = (typeof FEE_FREQUENCY_CHOICES)[number];

export interface FeeStructure {
    id: string;
    fee_head: string;
    fee_head_name: string;
    academic_year: string;
    level: string | null;
    level_name: string | null;
    section: string | null;
    section_name: string | null;
    amount: string;
    frequency: FeeFrequency;
    due_date: string | null;
    effective_from: string | null;
    effective_to: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
}

export type StudentFeeStatus = "active" | "cancelled";

export interface StudentFee {
    id: string;
    student: string;
    fee_structure: string | null;
    fee_head: string;
    fee_head_name: string;
    academic_year: string;
    level_name: string;
    section_name: string;
    amount_due: string;
    discount_amount: string;
    discount_reason: string;
    due_date: string | null;
    status: StudentFeeStatus;
    cancellation_reason: string;
    cancelled_at: string | null;
    amount_paid: string;
    outstanding_balance: string;
    created_at: string;
    updated_at: string;
}

export interface StudentFeesResponse {
    student: string;
    total_outstanding: string;
    fees: StudentFee[];
}

export const PAYMENT_METHOD_CHOICES = ["cash", "bank_transfer", "upi", "cheque", "online"] as const;
export type PaymentMethod = (typeof PAYMENT_METHOD_CHOICES)[number];

export interface PaymentAllocationInput {
    student_fee: string;
    amount: string;
}

export interface PaymentAllocation {
    id: string;
    student_fee: string;
    fee_head_name: string;
    amount: string;
    created_at: string;
}

export type PaymentStatus = "completed" | "reversed";

export interface Payment {
    id: string;
    student: string;
    student_name: string;
    amount: string;
    method: PaymentMethod;
    status: PaymentStatus;
    receipt_number: string;
    reference_note: string;
    reverses: string | null;
    recorded_by: string | null;
    allocations: PaymentAllocation[];
    is_reversed: boolean;
    created_at: string;
}

export interface OutstandingReportRow {
    student: string;
    full_name: string;
    enrollment_id: string;
    fee_head: string;
    academic_year: string;
    due_date: string | null;
    outstanding: string;
}

export interface OutstandingReportResponse {
    count: number;
    next: string | null;
    previous: string | null;
    total_outstanding_amount: string;
    results: OutstandingReportRow[];
}
