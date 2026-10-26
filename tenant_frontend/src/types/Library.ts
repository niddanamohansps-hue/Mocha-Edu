export type CopyStatus = "available" | "issued" | "lost" | "withdrawn";

export const COPY_STATUS_LABELS: Record<CopyStatus, string> = {
    available: "Available",
    issued: "Issued",
    lost: "Lost",
    withdrawn: "Withdrawn",
};

export interface BookCategory {
    id: string;
    name: string;
    books_count: number;
}

export interface Book {
    id: string;
    title: string;
    author: string;
    isbn: string;
    category: string | null;
    category_name: string;
    publisher: string;
    publication_year: number | null;
    shelf_location: string;
    price: string | null;
    description: string;
    is_active: boolean;
    copies_total: number;
    copies_available: number;
}

export interface BookInput {
    title: string;
    author: string;
    isbn: string;
    category: string | null;
    publisher: string;
    publication_year: number | null;
    shelf_location: string;
    price: string | null;
    description: string;
    is_active: boolean;
}

export interface BookCopy {
    id: string;
    book: string;
    book_title: string;
    accession_number: string;
    status: CopyStatus;
    notes: string;
    borrower_name: string;
}

export type BorrowerType = "student" | "staff";

export interface Loan {
    id: string;
    copy: string;
    book: string;
    book_title: string;
    accession_number: string;
    borrower_type: BorrowerType;
    borrower_name: string;
    borrower_ref: string;
    issued_on: string;
    due_on: string;
    returned_on: string | null;
    outcome: "" | "returned" | "lost";
    renewals: number;
    is_open: boolean;
    is_overdue: boolean;
    days_overdue: number;
    projected_fine: string;
}

export type LoanState = "" | "open" | "overdue" | "closed";

export type FineStatus = "pending" | "billed" | "collected" | "waived";

export const FINE_STATUS_LABELS: Record<FineStatus, string> = {
    pending: "Pending",
    billed: "Billed in Fees",
    collected: "Collected",
    waived: "Waived",
};

export interface Fine {
    id: string;
    loan: string;
    book_title: string;
    borrower_type: BorrowerType;
    borrower_name: string;
    borrower_ref: string;
    kind: "overdue" | "lost";
    amount: string;
    days_overdue: number;
    status: FineStatus;
    student_fee: string | null;
    waive_reason: string;
    resolved_at: string | null;
}

export interface ClosedLoanResult extends Loan {
    fine: Fine | null;
}

export interface LibrarySettings {
    student_loan_days: number;
    staff_loan_days: number;
    student_max_books: number;
    staff_max_books: number;
    max_renewals: number;
    fine_per_day: string;
    is_default: boolean;
    currency: string;
}

export interface LibrarySummary {
    titles: number;
    copies: { total: number; available: number; issued: number; lost: number };
    open_loans: number;
    overdue_loans: number;
    pending_fines: number;
}
