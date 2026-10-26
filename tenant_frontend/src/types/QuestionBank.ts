export type QuestionType = "mcq" | "multi_select" | "true_false" | "short" | "long" | "case_based";
export type Difficulty = "easy" | "medium" | "hard";
export type QuestionStatus = "draft" | "submitted" | "changes_requested" | "approved" | "rejected" | "archived";
export type ReviewDecision = "approved" | "changes_requested" | "rejected";

export const TYPE_LABELS: Record<QuestionType, string> = {
    mcq: "Multiple choice (one answer)",
    multi_select: "Multiple choice (several answers)",
    true_false: "True or false",
    short: "Short answer",
    long: "Long answer",
    case_based: "Case-based",
};

export const CHOICE_TYPES: QuestionType[] = ["mcq", "multi_select", "true_false"];

export const DIFFICULTY_LABELS: Record<Difficulty, string> = { easy: "Easy", medium: "Medium", hard: "Hard" };

export const STATUS_LABELS: Record<QuestionStatus, string> = {
    draft: "Draft",
    submitted: "Waiting for review",
    changes_requested: "Changes requested",
    approved: "Approved",
    rejected: "Rejected",
    archived: "Archived",
};

export interface QuestionOption {
    text: string;
    is_correct: boolean;
}

export interface Topic {
    id: string;
    chapter: string;
    name: string;
    order: number;
}

export interface Chapter {
    id: string;
    subject: string;
    subject_name: string;
    name: string;
    order: number;
    topics: Topic[];
}

export interface SubjectReviewer {
    id: string;
    subject: string;
    subject_name: string;
    level_name: string;
    staff: string;
    staff_name: string;
}

export interface ScopeSubject {
    id: string;
    name: string;
    code: string;
    level_name: string;
}

export interface MyScope {
    is_manager: boolean;
    can_write: ScopeSubject[];
    can_review: ScopeSubject[];
}

export interface Question {
    id: string;
    subject: string;
    subject_name: string;
    level_name: string;
    chapter: string | null;
    chapter_name: string;
    topic: string | null;
    topic_name: string;
    question_type: QuestionType;
    difficulty: Difficulty;
    marks: string;
    body: string;
    options: QuestionOption[];
    answer: string;
    explanation: string;
    marking_scheme: string;
    learning_outcome: string;
    status: QuestionStatus;
    version: number;
    author_name: string;
    is_mine: boolean;
    submitted_at: string | null;
    decided_at: string | null;
    updated_at: string;
}

export interface QuestionInput {
    subject: string;
    chapter: string | null;
    topic: string | null;
    question_type: QuestionType;
    difficulty: Difficulty;
    marks: string;
    body: string;
    options: QuestionOption[];
    answer: string;
    explanation: string;
    marking_scheme: string;
    learning_outcome: string;
}

export interface QuestionHistory {
    versions: { id: string; number: number; content: Record<string, unknown>; created_at: string }[];
    reviews: { id: string; version: number; decision: ReviewDecision; comment: string; reviewer_name: string; created_at: string }[];
}

// --- Question papers -----------------------------------------------------------------------------

export type PaperStatus = "draft" | "submitted" | "approved" | "released" | "withdrawn";

export const PAPER_STATUS_LABELS: Record<PaperStatus, string> = {
    draft: "Draft",
    submitted: "Waiting for approval",
    approved: "Approved",
    released: "Released",
    withdrawn: "Withdrawn",
};

export interface BlueprintRule {
    id: string;
    section: string;
    count: number;
    question_type: QuestionType | "";
    difficulty: Difficulty | "";
    chapter: string | null;
    chapter_name: string;
    description: string;
}

export interface PaperItem {
    id: string;
    section: string;
    question: string;
    question_version: number;
    order: number;
    marks: string;
    body: string;
    question_type: QuestionType;
    difficulty: Difficulty;
    chapter_name: string;
    question_status: QuestionStatus;
}

export interface PaperSection {
    id: string;
    paper: string;
    order: number;
    title: string;
    instructions: string;
    rules: BlueprintRule[];
    items: PaperItem[];
}

export interface QuestionPaper {
    id: string;
    examination: string;
    examination_name: string;
    subject: string;
    subject_name: string;
    level_name: string;
    set_label: string;
    title: string;
    instructions: string;
    total_marks: string;
    duration_minutes: number;
    allow_shared_questions: boolean;
    status: PaperStatus;
    release_at: string | null;
    review_comment: string;
    withdraw_reason: string;
    marks_so_far: string;
    question_count: number;
    is_released: boolean;
    is_mine: boolean;
    submitted_at: string | null;
    approved_at: string | null;
    released_at: string | null;
    sections?: PaperSection[];
    problems?: string[];
}

export interface PaperInput {
    examination: string;
    subject: string;
    set_label: string;
    title: string;
    instructions: string;
    total_marks: string;
    duration_minutes: number;
    allow_shared_questions: boolean;
}

export interface PrintedQuestion {
    number: number;
    marks: string;
    type: QuestionType;
    body: string;
    options: string[];
    correct?: number[];
    answer?: string;
    explanation?: string;
    marking_scheme?: string;
    chapter: string;
}

export interface PrintablePaper {
    title: string;
    set_label: string;
    instructions: string;
    examination: string;
    subject: string;
    level: string;
    total_marks: string;
    duration_minutes: number;
    status: PaperStatus;
    is_frozen: boolean;
    sections: { title: string; instructions: string; questions: PrintedQuestion[] }[];
}

export interface PaperAccessEntry {
    user: string;
    kind: "paper" | "answer_key";
    status: PaperStatus;
    at: string;
}
