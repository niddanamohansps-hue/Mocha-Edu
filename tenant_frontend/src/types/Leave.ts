export type LeaveStatus = "pending" | "approved" | "rejected" | "cancelled";

export type HalfDaySession = "" | "morning" | "afternoon";

export interface LeaveType {
    id: string;
    name: string;
    code: string;
    description: string;
    annual_allocation_days: string | number;
    is_paid: boolean;
    requires_document: boolean;
    max_consecutive_days: number | null;
    is_active: boolean;
    created_at?: string;
    updated_at?: string;
}

export interface StaffLeaveBalance {
    id: string;
    staff: string;
    staff_name: string;
    employee_id: string;
    leave_type: string;
    leave_type_name: string;
    leave_type_code: string;
    is_paid: boolean;
    academic_year: string;
    allocated_days: string | number;
    used_days: string | number;
    pending_days: string | number;
    available_days: string | number;
    updated_at: string;
}

export interface LeaveApproval {
    id: string;
    decision: "approved" | "rejected" | "cancelled";
    approver: string | null;
    approver_name: string;
    comments: string;
    decided_at: string;
}

export interface LeaveApplication {
    id: string;
    staff: string;
    staff_name: string;
    employee_id: string;
    department?: string;
    designation?: string;
    leave_type: string;
    leave_type_name: string;
    leave_type_code: string;
    academic_year: string;
    start_date: string;
    end_date: string;
    is_half_day: boolean;
    half_day_session: HalfDaySession;
    working_days: string | number;
    reason: string;
    status: LeaveStatus;
    has_document?: boolean;
    document_name?: string;
    document_url?: string | null;
    approvals?: LeaveApproval[];
    applied_at: string;
    updated_at?: string;
}

export interface SubstituteCandidate {
    instructor_id: number;
    name: string;
    specialization: string;
    department: string;
    is_same_subject: boolean;
}

export interface AffectedPeriodSlot {
    date: string;
    day_of_week: string;
    entry_id: string;
    section: string;
    subject: string;
    period: {
        id: string;
        name: string;
        start_time: string;
        end_time: string;
    };
    room: string | null;
    existing_substitution: {
        id: string;
        substitute_instructor: string | null;
        reason: string;
    } | null;
    eligible_substitutes: SubstituteCandidate[];
}

