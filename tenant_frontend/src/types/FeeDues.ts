export type DueBand = "current" | "1-30" | "31-60" | "61-90" | "90+";

export type PromiseStatus = "pending" | "kept" | "broken" | "replaced";

export interface PromiseInfo {
    amount: string | null;
    date: string;
    status: PromiseStatus;
    paid_since: string;
}

export interface CallRow {
    id: string;
    outcome: string;
    outcome_label: string;
    note: string;
    promise: PromiseInfo | null;
    by: string;
    at: string;
}

export interface DueRow {
    student: string;
    name: string;
    enrollment_id: string;
    level: string;
    section: string;
    outstanding: string;
    overdue: string;
    fees: number;
    oldest_due: string | null;
    days_late: number;
    band: DueBand;
    guardian_name: string;
    guardian_phone: string;
    guardian_relation: string;
    last_call_at: string | null;
    last_outcome: string | null;
    promise: PromiseInfo | null;
}

export interface DuesResponse {
    totals: {
        students: number;
        outstanding: string;
        overdue: string;
        bands: Record<DueBand, string>;
        capped: boolean;
    };
    count: number;
    results: DueRow[];
}
