export type PositionType = "instructor" | "staff";
export type OpeningStatus = "draft" | "open" | "closed";
export type ApplicantStage = "applied" | "shortlisted" | "interview" | "offered" | "hired" | "rejected";

export const STAGES: { value: ApplicantStage; label: string }[] = [
    { value: "applied", label: "Applied" },
    { value: "shortlisted", label: "Shortlisted" },
    { value: "interview", label: "Interview" },
    { value: "offered", label: "Offered" },
    { value: "hired", label: "Hired" },
    { value: "rejected", label: "Rejected" },
];

// Mirrors the server's rules (recruitment/services.py ALLOWED_MOVES); the server is what actually enforces them.
// "hired" is reached only through the hire action.
export const NEXT_STAGES: Record<ApplicantStage, ApplicantStage[]> = {
    applied: ["shortlisted", "rejected"],
    shortlisted: ["interview", "rejected", "applied"],
    interview: ["offered", "rejected", "shortlisted"],
    offered: ["rejected", "interview"],
    hired: [],
    rejected: ["applied"],
};

export interface JobOpening {
    id: string;
    title: string;
    position_type: PositionType;
    department: string;
    specialization: string;
    vacancies: number;
    description: string;
    requirements: string;
    min_experience_years: number;
    last_date: string | null;
    status: OpeningStatus;
    closed_at: string | null;
    created_at: string;
    applicant_count: number;
    hired_count: number;
    accepting_applications: boolean;
}

export interface Applicant {
    id: string;
    reference: string;
    opening: string;
    opening_title: string;
    first_name: string;
    last_name: string;
    full_name: string;
    email: string;
    phone: string;
    gender: "male" | "female" | "other" | "";
    date_of_birth: string | null;
    address: string;
    qualification: string;
    experience_years: number;
    current_employer: string;
    expected_salary: string | null;
    resume_url: string | null;
    cover_note: string;
    source: string;
    stage: ApplicantStage;
    stage_changed_at: string;
    rejection_reason: string;
    hired_staff: string | null;
    average_score: number | null;
    created_at: string;
}

export interface ApplicantEvent {
    id: string;
    from_stage: string;
    to_stage: string;
    note: string;
    actor_name: string;
    created_at: string;
}

export interface Interview {
    id: string;
    applicant: string;
    applicant_name: string;
    round_name: string;
    scheduled_at: string;
    mode: "in_person" | "online" | "phone";
    location_or_url: string;
    interviewer: string | null;
    interviewer_name: string | null;
    status: "scheduled" | "completed" | "cancelled";
    score: string | null;
    feedback: string;
    created_at: string;
}

export interface RecruitmentSummary {
    open_openings: number;
    applicants_by_stage: Record<ApplicantStage, number>;
    upcoming_interviews: number;
}
