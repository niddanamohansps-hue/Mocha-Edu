export interface LinkedChildSummary {
    id: string;
    enrollment_id: string;
    full_name: string;
}

export interface ParentChildRelation {
    relation_id: number;
    relation_type: string;
    is_primary: boolean;
    can_pickup: boolean;
    student: LinkedChildSummary;
}

export interface ParentProfileDetails {
    id: string;
    user_id?: string | null;
    username?: string | null;
    local_username?: string | null;
    email?: string | null;
    first_name: string;
    middle_name?: string | null;
    last_name: string;
    gender?: string | null;
    date_of_birth?: string | null;
    phone?: string | null;
    address?: string | null;
    profile_image?: string | null;
    created_at?: string;
    updated_at?: string;
}

export interface Parent {
    id: string;
    profile: string | null;
    profile_details: ParentProfileDetails;
    occupation?: string | null;
    office_address?: string | null;
    income_level?: string | null;
    whatsapp_opt_in?: boolean;
    whatsapp_opt_in_at?: string | null;
    children: ParentChildRelation[];
}

export interface ParentFormData {
    first_name: string;
    middle_name?: string;
    last_name: string;
    phone?: string;
    email?: string;
    gender?: string;
    address?: string;
    occupation?: string;
    office_address?: string;
    income_level?: string;
    whatsapp_opt_in?: boolean;
}

export interface StudentParentRelation {
    id: number;
    student: string;
    parent: string;
    relation_type: string;
    is_primary_contact: boolean;
    can_pickup: boolean;
    student_name?: string;
    parent_name?: string;
    student_enrollment_id?: string;
}

export interface LinkChildFormData {
    student: string;
    parent: string;
    relation_type: string;
    is_primary_contact: boolean;
    can_pickup: boolean;
}

export interface ParentPortalActivationData {
    parent_id: string;
    username: string;
    password?: string;
    email?: string;
}

export interface ParentPendingCredential {
    id: string;
    full_name: string;
    username: string;
    initial_password: string;
}

