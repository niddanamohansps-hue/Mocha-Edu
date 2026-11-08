export interface SittingPaper {
    schedule: string;
    subject: string;
    class: string;
}

export interface SittingSummary {
    id: string;
    examination: string;
    date: string;
    start_time: string;
    end_time: string;
    papers: SittingPaper[];
    seated: number;
    rooms_used: number;
    invigilators: number;
}

export interface PlanSeat {
    seat: number;
    student_id: string;
    student: string;
    enrollment_id: string;
    class: string;
    subject: string;
}

export interface PlanInvigilator {
    id: string;
    staff_id: string;
    name: string;
    employee_id: string;
    role: "chief" | "invigilator" | "relief";
}

export interface PlanRoom {
    room: { id: string; name: string; capacity: number };
    seats: PlanSeat[];
    invigilators: PlanInvigilator[];
}

export interface SittingPlan {
    sitting: SittingSummary;
    rooms: PlanRoom[];
    /** Students of the papers who have no seat (for example enrolled after the allocation). */
    unseated: number;
}

export interface DutyRow {
    id: string;
    staff_id: string;
    staff: string;
    employee_id: string;
    examination: string;
    date: string;
    start_time: string;
    end_time: string;
    room: string;
    role: "chief" | "invigilator" | "relief";
    sitting: string;
    room_id: string;
}

export interface AdmitCardPaper {
    subject: string;
    date: string;
    start_time: string;
    end_time: string;
    room: string;
    seat: number | null;
}

export interface AdmitCard {
    student_id: string;
    name: string;
    enrollment_id: string;
    class: string;
    papers: AdmitCardPaper[];
}

export interface AdmitCardData {
    examination: { id: string; name: string; start_date: string; end_date: string };
    class: string;
    cards: AdmitCard[];
}

export interface MarksProgressRow {
    schedule: string;
    subject: string;
    class: string;
    date: string;
    teachers: string[];
    expected: number;
    entered: number;
    state: "complete" | "in_progress" | "not_started";
    locked: boolean;
    overdue: boolean;
}

export interface MarksProgress {
    due_date: string | null;
    summary: { papers: number; complete: number; in_progress: number; not_started: number; overdue: number };
    rows: MarksProgressRow[];
}

export interface RankRow {
    rank: number | null;
    student_id: string;
    name: string;
    enrollment_id: string;
    class: string;
    total_marks: string;
    max_marks: string;
    percentage: string;
    grade: string;
    is_pass: boolean;
}

export interface RankList {
    examination: { id: string; name: string; academic_year: string };
    scope: "section" | "class";
    title: string;
    include_failed: boolean;
    rows: RankRow[];
    toppers: RankRow[];
}

export interface FamilyExam {
    id: string;
    name: string;
    academic_year: string;
    start_date: string;
    end_date: string;
    date_sheet_published_at: string | null;
    is_published: boolean;
}

export interface AnalyticsSubject {
    subject_id: string;
    subject: string;
    appeared: number;
    absent: number;
    passed: number;
    pass_percentage: number | null;
    average_percentage: number | null;
    highest_percentage: number | null;
    lowest_percentage: number | null;
}

export interface ExamAnalytics {
    examination: { id: string; name: string; academic_year: string };
    scope: "section" | "class";
    title: string;
    overall: {
        students: number;
        passed: number;
        failed: number;
        pass_percentage: number | null;
        average_percentage: number | null;
        highest_percentage: number | null;
        lowest_percentage: number | null;
    };
    distribution: { label: string; count: number }[];
    sections: { section: string; students: number; passed: number; pass_percentage: number | null; average_percentage: number | null }[];
    subjects: AnalyticsSubject[];
}

export interface ExamComparison {
    title: string;
    first: { name: string; students: number; pass_percentage: number | null; average_percentage: number | null };
    second: { name: string; students: number; pass_percentage: number | null; average_percentage: number | null };
    subjects: {
        subject: string;
        first_average: number | null;
        second_average: number | null;
        change: number | null;
        first_pass_percentage: number | null;
        second_pass_percentage: number | null;
    }[];
}

export interface WeakStudent {
    student_id: string;
    name: string;
    enrollment_id: string;
    class: string;
    percentage: number;
    is_pass: boolean;
    weak_subjects: { subject: string; status: "failed" | "borderline" | "absent"; percentage: number | null }[];
    failed_count: number;
    attendance_percentage: number | null;
}

export interface WeakStudents {
    examination: { id: string; name: string };
    title: string;
    margin: number;
    rows: WeakStudent[];
}

export interface ModerationRow {
    mark_id: string;
    student_id: string;
    name: string;
    enrollment_id: string;
    old: string;
    new: string;
    passed_before: boolean;
    passed_after: boolean;
}

export interface ModerationPreview {
    schedule: string;
    summary: {
        students_with_marks: number;
        changed: number;
        capped: number;
        passed_before: number;
        passed_after: number;
        average_before: number | null;
        average_after: number | null;
        max_marks: string;
        pass_marks: string;
    };
    rows: ModerationRow[];
}

export interface ModerationOptions {
    method: "add" | "scale";
    value: string;
    step: string;
    below?: string;
}

export type MalpracticeDecision = "dismissed" | "warning" | "marks_cancelled" | "all_papers_cancelled";

export interface MalpracticeCase {
    id: string;
    examination: string;
    examination_name: string;
    schedule: string;
    subject: string;
    class: string;
    student_id: string;
    student: string;
    enrollment_id: string;
    description: string;
    evidence_notes: string;
    reported_by: string;
    reported_by_user_id: string | null;
    reported_at: string;
    status: "reported" | "decided";
    decision: MalpracticeDecision | "";
    decision_label: string;
    decision_notes: string;
    decided_by: string;
    decided_at: string | null;
}

export interface HallRow {
    student_id: string;
    name: string;
    enrollment_id: string;
    class: string;
    subject: string;
    seat: number;
    status: "" | "present" | "absent";
}

export interface HallAttendance {
    sitting: { id: string; examination: string; date: string; start_time: string; end_time: string };
    room: { id: string; name: string };
    rows: HallRow[];
}

export interface HallSaveResult {
    saved: number;
    absent: number;
    conflicts: { student_id: string; name: string; problem: string }[];
    attendance: HallAttendance;
}
