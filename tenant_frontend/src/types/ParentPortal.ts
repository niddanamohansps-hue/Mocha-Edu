export interface ParentMe {
    parent_id: string;
    full_name: string;
    occupation: string;
    office_address: string;
    income_level: string;
    children_count: number;
}

export interface LinkedChild {
    student_id: string;
    full_name: string;
    enrollment_id: string;
    relation_type: string;
    is_primary_contact: boolean;
    can_pickup: boolean;
    level: string | null;
    section: string | null;
    academic_year: string | null;
}

export type AttendanceStatus = "present" | "absent" | "late" | "half_day" | "leave";

export interface ChildAttendance {
    student: string;
    counts: Partial<Record<AttendanceStatus, number>>;
    percentage: number | null;
    records: { date: string; status: AttendanceStatus; remarks: string }[];
}

export interface ChildTimetableEntry {
    id: string;
    day_of_week: number;
    day_of_week_display: string;
    period: string;
    period_name: string;
    period_order: number;
    subject: string;
    subject_name: string;
    instructor_name: string | null;
    room: string | null;
    room_name: string | null;
}

export interface ChildTimetableResponse {
    student: string;
    section: string | null;
    results: ChildTimetableEntry[];
}

export interface SubjectResultBreakdown {
    subject: string;
    subject_name: string;
    marks_obtained: number | null;
    max_marks: number;
    percentage: number | null;
    grade: string | null;
    is_absent: boolean;
    is_pass: boolean;
}

export interface ChildExamResult {
    id: string;
    examination: string;
    examination_name: string;
    academic_year: string;
    total_marks_obtained: string;
    total_max_marks: string;
    percentage: string;
    overall_grade: string;
    is_pass: boolean;
    subject_breakdown: SubjectResultBreakdown[];
    published_at: string;
}

export interface ChildReportCard {
    student: { id: string; full_name: string; enrollment_id: string };
    academic_year: string | null;
    examinations: ChildExamResult[];
}

export interface ChildFee {
    id: string;
    fee_head: string;
    academic_year: string;
    amount_due: string;
    discount_amount: string;
    amount_paid: string;
    outstanding_balance: string;
    due_date: string | null;
    status: "active" | "cancelled";
}

export interface ChildPaymentSummary {
    id: string;
    amount: string;
    method: string;
    status: string;
    receipt_number: string;
    created_at: string;
}

export interface ChildFeesResponse {
    student: string;
    total_outstanding: string;
    fees: ChildFee[];
    payments: ChildPaymentSummary[];
}

export interface UpcomingExam {
    id: string;
    examination: string;
    examination_name: string;
    subject_name: string;
    date: string;
    start_time: string;
    end_time: string;
}

export const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
