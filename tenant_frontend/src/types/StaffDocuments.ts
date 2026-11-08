export type DocumentStatus = "pending" | "received" | "waived";

export interface DocumentType {
    id: string;
    name: string;
    order: number;
    is_active: boolean;
}

export interface ChecklistRow {
    staff: string;
    name: string;
    employee_id: string;
    designation: string;
    joining_date: string | null;
    pending: number;
    received: number;
    total: number;
}

export interface DocumentItem {
    id: string;
    staff: string;
    name: string;
    status: DocumentStatus;
    received_on: string | null;
    note: string;
    has_file: boolean;
    updated_at: string;
}
