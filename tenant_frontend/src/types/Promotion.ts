export type PromotionAction =
    | "promoted"
    | "retained"
    | "transferred"
    | "withdrawn"
    | "graduated";

export interface PromotionCandidate {
    student_id: string;
    full_name: string;
    enrollment_id: string;
    current_level: string | null;
    current_level_name: string | null;
    current_section: string | null;
    current_section_name: string | null;
    default_target_level: string | null;
    default_target_level_name: string | null;
    fee_warning: string | null;
    exam_warning: string[] | null;
}

export interface PromotionEntryInput {
    student: string;
    action: PromotionAction;
    target_academic_year?: string;
    target_level?: string;
    target_section?: string;
    reason?: string;
}

export interface PromotionBatchInput {
    source_academic_year: string;
    entries: PromotionEntryInput[];
}

export interface PromotionPreviewResult {
    student: string;
    action: PromotionAction;
    eligible: boolean;
    conflicts: string[];
    warnings: string[];
    source_academic_year: string | null;
    target_academic_year: string | null;
    target_level: string | null;
    target_section: string | null;
}

export interface PromotionExecuteResult {
    student: string;
    action: PromotionAction;
    status: "success" | "skipped";
    record_id?: string;
    error?: string;
}

export interface PromotionExecuteResponse {
    results: PromotionExecuteResult[];
}

export interface PromotionRecord {
    id: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    action: PromotionAction | "reversed";
    source_academic_year: string;
    target_academic_year: string;
    source_level: string | null;
    source_level_name: string | null;
    target_level: string | null;
    target_level_name: string | null;
    source_section: string | null;
    source_section_name: string | null;
    target_section: string | null;
    target_section_name: string | null;
    reason: string;
    reverses: string | null;
    is_reversed: boolean;
    created_by: string | null;
    created_at: string;
}

export const PROMOTION_ACTION_LABELS: Record<PromotionAction, string> = {
    promoted: "Promote",
    retained: "Retain",
    withdrawn: "Withdraw",
    transferred: "Transfer",
    graduated: "Graduate",
};
