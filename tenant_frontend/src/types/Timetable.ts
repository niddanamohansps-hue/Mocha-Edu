export interface Period {
    id: string;
    academic_year: string;
    name: string;
    order: number;
    start_time: string;
    end_time: string;
    is_break: boolean;
}

export interface Room {
    id: string;
    name: string;
    capacity: number;
}

export interface TimetableEntry {
    id: string;
    academic_year: string;
    section: string;
    section_name: string;
    subject: string;
    subject_name: string;
    instructor: string | null;
    instructor_name: string | null;
    room: string | null;
    room_name: string | null;
    day_of_week: number;
    day_of_week_display: string;
    period: string;
    period_name: string;
    period_order: number;
}

export interface TimetableEntryInput {
    academic_year: string;
    section: string;
    subject: string;
    instructor: string | null;
    room: string | null;
    day_of_week: number;
    period: string;
}

export interface TimetableSubstitution {
    id: string;
    timetable_entry: string;
    date: string;
    substitute_instructor: string | null;
    reason: string;
    created_by: string | null;
    created_at: string;
}

export interface MyTimetableResponse {
    role: "student" | "instructor" | null;
    section?: string;
    results: TimetableEntry[];
}

export const DAY_LABELS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
