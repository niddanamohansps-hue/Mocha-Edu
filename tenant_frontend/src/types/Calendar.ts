export type CalendarEventType =
    | 'holiday'
    | 'academic'
    | 'closure'
    | 'exam'
    | 'meeting'
    | 'activity';

export type CalendarEventStatus = 'draft' | 'published' | 'cancelled';

export type CalendarAudience = 'all' | 'staff' | 'students_parents';

export interface CalendarEventItem {
    id: string;
    title: string;
    description: string;
    event_type: CalendarEventType;
    event_type_display: string;
    start_date: string; // YYYY-MM-DD
    end_date: string;   // YYYY-MM-DD
    start_time: string | null; // HH:MM:SS
    end_time: string | null;   // HH:MM:SS
    is_all_day: boolean;
    is_holiday: boolean;
    status: CalendarEventStatus;
    status_display: string;
    academic_year: string | null;
    academic_year_name: string | null;
    location: string;
    audience: CalendarAudience;
    audience_display: string;
    created_by_id: number | null;
    created_by_username: string;
    created_at: string;
    updated_at: string;
}

export interface CalendarEventInput {
    title: string;
    description?: string;
    event_type: CalendarEventType;
    start_date: string;
    end_date: string;
    start_time?: string | null;
    end_time?: string | null;
    is_all_day?: boolean;
    is_holiday?: boolean;
    status?: CalendarEventStatus;
    academic_year?: string | null;
    location?: string;
    audience?: CalendarAudience;
}

export interface CalendarEventFilters {
    date?: string;
    date_from?: string;
    date_to?: string;
    start_date?: string;
    end_date?: string;
    month?: string;
    event_type?: CalendarEventType | '';
    is_holiday?: boolean | '';
    status?: CalendarEventStatus | '';
    academic_year?: string;
    audience?: CalendarAudience | '';
    search?: string;
}

