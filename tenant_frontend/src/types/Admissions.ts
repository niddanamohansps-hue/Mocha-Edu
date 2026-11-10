export type EnquirySource =
    | "website"
    | "walk_in"
    | "phone"
    | "referral"
    | "campaign"
    | "other";

export type EnquiryStatus =
    | "new"
    | "contacted"
    | "qualified"
    | "converted"
    | "closed";

export type ApplicationStatus =
    | "draft"
    | "submitted"
    | "under_review"
    | "documents_pending"
    | "documents_verified"
    | "assessment_pending"
    | "approved"
    | "waitlisted"
    | "rejected"
    | "offer_accepted"
    | "enrolled"
    | "withdrawn";

export type DocumentType =
    | "birth_certificate"
    | "transfer_certificate"
    | "previous_marksheet"
    | "photo"
    | "address_proof"
    | "medical_record"
    | "other";

export type VerificationStatus =
    | "pending"
    | "verified"
    | "rejected";

export type InterviewType =
    | "written_test"
    | "student_interview"
    | "parent_interaction"
    | "portfolio_review"
    | "other";

export type InterviewStatus =
    | "scheduled"
    | "completed"
    | "cancelled";

export type InterviewRecommendation =
    | "recommended"
    | "conditional"
    | "waitlist"
    | "not_recommended";

export interface AdmissionEnquiry {
    id: string;
    enquiry_number: string;
    student_name: string;
    date_of_birth?: string | null;
    gender?: string;
    guardian_name: string;
    guardian_relationship: string;
    guardian_phone: string;
    guardian_email?: string;
    address?: string;
    previous_school?: string;
    academic_year: string;
    academic_year_ref?: string | null;
    preferred_level?: string | null;
    preferred_level_name?: string;
    source: EnquirySource;
    status: EnquiryStatus;
    assigned_to?: string | null;
    assigned_to_name?: string | null;
    enquiry_date: string;
    follow_up_date?: string | null;
    notes?: string;
    created_at: string;
    updated_at: string;
}

export type DocumentScanStatus = "pending" | "clean" | "infected" | "error";

export interface AdmissionDocument {
    id: string;
    application: string;
    document_type: DocumentType;
    document_type_display: string;
    title: string;
    file: string;
    file_name: string;
    verification_status: VerificationStatus;
    scan_status?: DocumentScanStatus;
    scan_details?: string;
    verified_by?: string | null;
    verified_by_name?: string | null;
    verified_at?: string | null;
    rejection_reason?: string;
    uploaded_at: string;
}

export interface AdmissionInterview {
    id: string;
    application: string;
    interview_type: InterviewType;
    interview_type_display: string;
    scheduled_at?: string | null;
    completed_at?: string | null;
    interviewer?: string | null;
    interviewer_name?: string | null;
    status: InterviewStatus;
    score?: number | string | null;
    recommendation?: InterviewRecommendation | "";
    feedback?: string;
    created_at: string;
}

export interface AdmissionActivityLog {
    id: string;
    action: string;
    from_status?: string;
    to_status?: string;
    performed_by?: string | null;
    performed_by_name?: string | null;
    notes?: string;
    created_at: string;
}

export interface AdmissionApplication {
    id: string;
    application_number: string;
    enquiry?: string | null;
    enquiry_number?: string | null;
    student?: string | null;
    student_enrollment_id?: string | null;
    first_name: string;
    middle_name?: string;
    last_name: string;
    date_of_birth: string;
    gender: "male" | "female" | "other";
    email?: string | null;
    phone?: string;
    address?: string;
    previous_school?: string;
    last_grade_passed?: string;
    guardian_first_name: string;
    guardian_last_name: string;
    guardian_relationship: string;
    guardian_phone: string;
    guardian_email?: string | null;
    guardian_occupation?: string;
    guardian_address?: string;
    secondary_guardian_name?: string;
    secondary_guardian_relationship?: string;
    secondary_guardian_phone?: string;
    academic_year: string;
    academic_year_ref?: string | null;
    level: string;
    level_name?: string;
    section?: string | null;
    section_name?: string | null;
    status: ApplicationStatus;
    submission_date?: string | null;
    assigned_reviewer?: string | null;
    assigned_reviewer_name?: string | null;
    decision_date?: string | null;
    decision_notice_sent_at?: string | null;
    documents_reminded_at?: string | null;
    document_checklist?: { document_type: string; label: string; status: "verified" | "received" | "rejected" | "missing" }[];
    decision_reason?: string;
    decision_by?: string | null;
    decision_by_name?: string | null;
    enrolled_at?: string | null;
    enrolled_by?: string | null;
    enrolled_by_name?: string | null;
    notes?: string;
    created_at: string;
    updated_at: string;
    documents?: AdmissionDocument[];
    interviews?: AdmissionInterview[];
    activities?: AdmissionActivityLog[];
}

export interface AdmissionsDashboardStats {
    total_enquiries: number;
    enquiries_new: number;
    enquiries_contacted: number;
    enquiries_converted: number;
    total_applications: number;
    applications_submitted: number;
    applications_under_review: number;
    applications_documents_pending: number;
    applications_assessment_pending: number;
    applications_approved: number;
    applications_enrolled: number;
    applications_rejected: number;
    pending_document_verifications: number;
    scheduled_interviews: number;
    conversion_rate: number;
}

export interface PublicAdmissionsInfo {
    institution: {
        name: string;
        address?: string;
        phone?: string;
        email?: string;
    };
    academic_years: {
        id: string;
        name: string;
        is_current: boolean;
        start_date: string;
        end_date: string;
    }[];
    levels: {
        id: string;
        name: string;
        program_name: string;
        program_code: string;
        order: number;
    }[];
    document_requirements: {
        document_type: DocumentType;
        label: string;
        description: string;
        required: boolean;
    }[];
    upload_policy: {
        max_file_size_mb: number;
        allowed_extensions: string[];
    };
    instructions: string;
}

export interface PublicEnquiryPayload {
    student_name: string;
    guardian_name: string;
    guardian_relationship: string;
    guardian_phone: string;
    guardian_email?: string;
    address?: string;
    previous_school?: string;
    academic_year_ref?: string;
    /** Optional: a family may enquire before deciding the class. */
    preferred_level?: string;
    notes?: string;
    consent: boolean;
}

export interface PublicApplicationPayload {
    first_name: string;
    middle_name?: string;
    last_name: string;
    date_of_birth: string;
    gender: "male" | "female" | "other";
    email?: string;
    phone?: string;
    address?: string;
    previous_school?: string;
    last_grade_passed?: string;
    guardian_first_name: string;
    guardian_last_name: string;
    guardian_relationship: string;
    guardian_phone: string;
    guardian_email?: string;
    guardian_occupation?: string;
    guardian_address?: string;
    secondary_guardian_name?: string;
    secondary_guardian_relationship?: string;
    secondary_guardian_phone?: string;
    academic_year_ref: string;
    level: string;
    enquiry_number?: string;
    consent: boolean;
}

export interface PublicApplicationSubmissionResult {
    success: boolean;
    application_number: string;
    access_token: string;
    access_token_expires_at?: string;
    submission_date?: string;
    status: ApplicationStatus;
    message: string;
}

export interface PublicApplicationStatus {
    application_number: string;
    submission_date?: string;
    first_name: string;
    student_masked_name: string;
    level_name: string;
    academic_year: string;
    status: ApplicationStatus;
    status_display: string;
    status_description: string;
    next_steps: string;
    can_upload_documents: boolean;
    documents: {
        id: string;
        document_type: DocumentType;
        document_type_display: string;
        title: string;
        file_name: string;
        verification_status: VerificationStatus;
        scan_status?: DocumentScanStatus;
        rejection_reason?: string;
        uploaded_at: string;
    }[];
}

export interface PublicTokenRotationResult {
    success: boolean;
    application_number: string;
    access_token: string;
    access_token_expires_at: string;
    message: string;
}

