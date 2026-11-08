export type DueBand = "current" | "1-30" | "31-60" | "61-90" | "90+";

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
