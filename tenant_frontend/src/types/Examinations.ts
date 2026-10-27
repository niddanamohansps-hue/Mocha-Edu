export interface ExamType {
    id: string;
    name: string;
    order: number;
}

export interface Examination {
    id: string;
    academic_year: string;
    name: string;
    exam_type: string;
    exam_type_name: string;
    start_date: string;
    end_date: string;
    is_published: boolean;
    published_at: string | null;
    publication_requested_by_user_id: string | null;
    publication_requested_at: string | null;
    published_by_user_id: string | null;
}

export interface ExaminationSettings {
    require_separate_publisher: boolean;
    is_default: boolean;
}

export interface ExamSchedule {
    id: string;
    examination: string;
    examination_name: string;
    academic_year: string;
    subject: string;
    subject_name: string;
    section: string;
    section_name: string;
    date: string;
    start_time: string;
    end_time: string;
    period: string | null;
    period_name: string | null;
    room: string | null;
    room_name: string | null;
    max_marks: string;
    pass_marks: string;
    is_locked: boolean;
    locked_at: string | null;
}

export interface ExamScheduleInput {
    examination: string;
    academic_year: string;
    subject: string;
    section: string;
    date: string;
    start_time: string;
    end_time: string;
    period?: string | null;
    room?: string | null;
    max_marks: string;
    pass_marks: string;
}

export interface ExamMarkRecordInput {
    student: string;
    marks_obtained: number | null;
    is_absent: boolean;
    attendance?: MarkAttendance;
    remarks?: string;
}

export interface ExamMark {
    id: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    marks_obtained: string | null;
    is_absent: boolean;
    remarks: string;
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
    attendance?: MarkAttendance;
    grace_marks?: number;
}

export interface ExamResult {
    id: string;
    examination: string;
    student: string;
    student_name: string;
    academic_year: string;
    total_marks_obtained: string;
    total_max_marks: string;
    percentage: string;
    overall_grade: string;
    is_pass: boolean;
    subject_breakdown: SubjectResultBreakdown[];
    published_at: string;
}

export interface InstitutionSummary {
    name: string;
    address: string;
    phone: string;
    email: string;
    website: string;
    tagline: string;
    logo_url: string | null;
}

export interface AttendanceSummary {
    percentage: number | null;
    total_days: number;
    present_days: number;
    absent_days: number;
    late_days: number;
    half_days: number;
    leave_days: number;
    status_counts: Record<string, number>;
}

export interface PromotionSummary {
    action: string;
    action_display: string;
    source_level?: string | null;
    target_level?: string | null;
    target_section?: string | null;
    target_academic_year?: string | null;
    reason?: string | null;
    date?: string | null;
}

export interface TeacherRemark {
    subject: string;
    examination: string;
    remarks: string;
}

export interface ReportCardSubjectBreakdown {
    subject: string;
    subject_name: string;
    marks_obtained: number | null;
    max_marks: number;
    percentage: number | null;
    grade: string | null;
    grade_point: number | null;
    credits: number;
    is_absent: boolean;
    is_pass: boolean;
}

export interface ReportCardExamination {
    id: string;
    examination: string;
    examination_name: string;
    exam_type: string;
    academic_year: string;
    total_marks_obtained: number;
    total_max_marks: number;
    percentage: number;
    overall_grade: string;
    is_pass: boolean;
    gpa: number | null;
    subject_breakdown: ReportCardSubjectBreakdown[];
    published_at: string | null;
}

export interface ReportCard {
    institution?: InstitutionSummary;
    student: {
        id: string;
        full_name: string;
        enrollment_id: string;
        date_of_birth?: string | null;
        gender?: string | null;
        level?: string | null;
        section?: string | null;
        status?: string;
    };
    academic_year: string | null;
    examinations: ReportCardExamination[];
    summary?: {
        total_marks_obtained: number;
        total_max_marks: number;
        percentage: number | null;
        overall_grade: string | null;
        gpa: number | null;
        is_pass: boolean;
        total_exams: number;
    };
    attendance?: AttendanceSummary;
    promotion?: PromotionSummary | null;
    remarks?: TeacherRemark[];
    generated_at?: string;
}

export interface TranscriptYearBlock {
    academic_year: string;
    level: string | null;
    section: string | null;
    examinations: ReportCardExamination[];
    summary: {
        total_marks_obtained: number;
        total_max_marks: number;
        percentage: number | null;
        overall_grade: string | null;
        gpa: number | null;
        is_pass: boolean;
        total_exams: number;
    };
    attendance: AttendanceSummary;
    promotion: PromotionSummary | null;
}

export interface CumulativeTranscriptSummary {
    total_marks_obtained: number;
    total_max_marks: number;
    cumulative_percentage: number | null;
    cgpa: number | null;
    total_credits_attempted: number;
    total_credits_earned: number;
    total_years: number;
    status: string;
}

export interface OfficialTranscript {
    institution: InstitutionSummary;
    student: {
        id: string;
        full_name: string;
        enrollment_id: string;
        date_of_birth?: string | null;
        gender?: string | null;
        admission_date?: string | null;
        status: string;
    };
    years: TranscriptYearBlock[];
    cumulative_summary: CumulativeTranscriptSummary;
    issuance: {
        issued_date: string;
        signatories: { title: string }[];
    };
    generated_at: string;
}


export interface GradeBoundary {
    id: string;
    academic_year: string;
    min_percentage: string;
    max_percentage: string;
    grade_label: string;
    grade_point: string | null;
}

export interface BelowPassingReport {
    examination: string;
    students: { student: string; full_name: string; enrollment_id: string; percentage: number }[];
}

// --- Marks integrity -------------------------------------------------------------------------------

export type MarkAttendance = "present" | "absent" | "medical" | "malpractice" | "exempt";

export const ATTENDANCE_LABELS: Record<MarkAttendance, string> = {
    present: "Present",
    absent: "Absent",
    medical: "Absent (medical)",
    malpractice: "Malpractice",
    exempt: "Exempt",
};

export interface SavedMark {
    id: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    marks_obtained: string | null;
    is_absent: boolean;
    attendance: MarkAttendance;
    grace_marks: string;
    remarks: string;
}

export interface ScheduleMarks {
    is_published: boolean;
    marks: SavedMark[];
}

export interface MarkChange {
    id: string;
    mark: string;
    kind: "entry" | "correction" | "import" | "grace" | "recheck";
    student_name: string;
    enrollment_id: string;
    old_marks: string | null;
    new_marks: string | null;
    old_attendance: string;
    new_attendance: string;
    old_grace: string;
    new_grace: string;
    reason: string;
    changed_by: string;
    created_at: string;
}

export interface MarksImportResult {
    dry_run: boolean;
    rows?: { line: number; enrollment_id: string; student_name: string; marks: string | null; attendance: MarkAttendance }[];
    total?: number;
    created?: number;
    updated?: number;
    changed?: number;
}

export type RecheckStatus = "pending" | "accepted" | "rejected";

export interface RecheckRequest {
    id: string;
    mark: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    subject_name: string;
    examination_name: string;
    max_marks: string;
    current_marks: string | null;
    status: RecheckStatus;
    reason: string;
    original_marks: string | null;
    revised_marks: string | null;
    decision_comment: string;
    created_at: string;
    decided_at: string | null;
}
