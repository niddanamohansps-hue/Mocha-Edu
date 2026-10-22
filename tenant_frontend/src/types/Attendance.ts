export type AttendanceStatus = "present" | "absent" | "late" | "half_day" | "leave";

export interface StudentAttendanceRecord {
    id: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    status: AttendanceStatus;
    remarks: string;
    recorded_by: string | null;
    created_at: string;
    updated_at: string;
}

export interface AttendanceSession {
    id: string;
    section: string;
    section_name: string;
    academic_year: string;
    date: string;
    recorded_by: string | null;
    is_locked: boolean;
    locked_at: string | null;
    student_records: StudentAttendanceRecord[];
    created_at: string;
    updated_at: string;
}

export interface RosterStudent {
    student: string;
    full_name: string;
    enrollment_id: string;
    existing: StudentAttendanceRecord | null;
}

export interface SectionRosterResponse {
    date: string;
    section: string;
    session: AttendanceSession | null;
    students: RosterStudent[];
}

export interface AttendanceRecordInput {
    student: string;
    status: AttendanceStatus;
    remarks?: string;
}

export interface StudentAttendanceHistory {
    student: string;
    counts: Partial<Record<AttendanceStatus, number>>;
    percentage: number | null;
    records: { date: string; status: AttendanceStatus; remarks: string }[];
}

export interface SectionSummary {
    section: string;
    counts: Partial<Record<AttendanceStatus, number>>;
    percentage: number | null;
}

export interface TenantAttendanceSummary {
    date: string;
    counts: Partial<Record<AttendanceStatus, number>>;
    percentage: number | null;
}

export interface BelowThresholdStudent {
    student: string;
    full_name: string;
    enrollment_id: string;
    percentage: number;
}

export interface BelowThresholdReport {
    threshold: number;
    students: BelowThresholdStudent[];
}

export interface StaffAttendanceRecord {
    id: string;
    staff: string;
    staff_name: string;
    date: string;
    status: AttendanceStatus;
    remarks: string;
    recorded_by: string | null;
}

export interface StaffAttendanceRecordInput {
    staff: string;
    status: AttendanceStatus;
    remarks?: string;
}

export interface AttendanceSettings {
    id: string;
    status_weights: Partial<Record<AttendanceStatus, number | null>>;
    minimum_attendance_percentage: string;
    lock_after_days: number;
    /** Weekdays the school is closed every week: 0 = Monday ... 6 = Sunday. */
    weekly_off_days: number[];
}
