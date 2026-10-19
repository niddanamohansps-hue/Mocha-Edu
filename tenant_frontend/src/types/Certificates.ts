export type CertificateType = "transfer" | "bonafide" | "character" | "experience";
export type CertificateStatus = "issued" | "cancelled" | "superseded";

export interface Certificate {
    id: string;
    certificate_type: CertificateType;
    certificate_type_label: string;
    certificate_number: string;
    // Present only for people who issue, approve or cancel certificates.
    verification_id?: string;
    student?: string | null;
    staff_member?: string | null;
    holder_name: string;
    issue_date: string;
    academic_year: string;
    period_start: string | null;
    period_end: string | null;
    leaving_date: string | null;
    reason: string;
    conduct: string;
    internal_notes?: string;
    status: CertificateStatus;
    issued_by_user_id?: string;
    approved_by_user_id?: string | null;
    issued_at: string;
    cancelled_at: string | null;
    cancellation_reason: string;
    supersedes_number: string | null;
    superseded_by_number: string | null;
    reissue_reason: string;
}

export interface IssueCertificateInput {
    certificate_type: CertificateType;
    student_id?: string;
    staff_id?: string;
    reason?: string;
    conduct?: string;
    academic_year?: string;
    leaving_date?: string | null;
    period_start?: string | null;
    period_end?: string | null;
    internal_notes?: string;
}

export interface ReissueInput {
    reason: string;
    new_reason?: string;
    conduct?: string;
    leaving_date?: string | null;
    period_start?: string | null;
    period_end?: string | null;
}

export interface CertificateFilters {
    page: number;
    certificate_type: CertificateType | "";
    status: CertificateStatus | "";
    search: string;
}

export interface CertificateSettings {
    signatory_name: string;
    signatory_title: string;
    has_signature: boolean;
}

// Public verification response - deliberately minimal.
export interface PublicCertificateVerification {
    valid: boolean;
    status: CertificateStatus | "integrity_failed";
    certificate_type: CertificateType;
    certificate_type_label: string;
    certificate_number: string;
    issue_date: string;
    school_name: string;
    holder_name: string;
    replaced_by_number: string | null;
}

export interface PublicIdCardVerification {
    valid: boolean;
    kind: "student" | "staff" | null;
    school_name: string;
    holder: string;
    status: "active" | "inactive" | "invalid";
}

export interface IdCardData {
    kind: "student" | "staff";
    kind_label: string;
    school_name: string;
    holder_name: string;
    id_number: string;
    details: { label: string; value: string }[];
    photo: string | null;
    logo: string | null;
    qr_svg: string;
}

export const CERTIFICATE_TYPE_LABELS: Record<CertificateType, string> = {
    transfer: "Transfer Certificate",
    bonafide: "Bonafide Certificate",
    character: "Character Certificate",
    experience: "Staff Experience Certificate",
};

export const STAFF_CERTIFICATE_TYPES: CertificateType[] = ["experience"];
