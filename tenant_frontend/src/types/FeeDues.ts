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

export interface DeskResponse {
    broken: DueRow[];
    due_today: DueRow[];
    uncalled: DueRow[];
    summary: { broken: number; due_today: number; uncalled: number };
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


export interface CollectionLine {
    billed: string;
    collected: string;
    outstanding: string;
    rate: number | null;
}

export interface CollectionSummary {
    academic_year: string;
    month: string | null;
    totals: CollectionLine & { fees: number; capped: boolean };
    by_month: (CollectionLine & { month: string; received: string })[];
    by_class: (CollectionLine & { level: string })[];
}
