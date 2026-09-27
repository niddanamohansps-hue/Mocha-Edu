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

export interface ReportCard {
    student: { id: string; full_name: string; enrollment_id: string };
    academic_year: string | null;
    examinations: ExamResult[];
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
