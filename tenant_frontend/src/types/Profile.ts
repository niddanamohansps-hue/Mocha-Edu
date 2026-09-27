export interface BaseProfile {
    id: string;
    email: string; // From User model
    student_id?: string | null;
    staff_id?: string | null;
    first_name: string;
    middle_name?: string;
    last_name: string;
    phone?: string;
    date_of_birth?: string;
    gender?: 'male' | 'female' | 'other';
    address?: string;
    profile_image?: string;
    created_at: string;
    updated_at: string;
}

export interface StudentProfile extends BaseProfile {
    enrollment_id: string;
    current_level: string;
    section?: string;
    admission_date?: string;
    guardian_name?: string;
    guardian_phone?: string;
    guardian_email?: string;
}

export interface InstructorProfile extends BaseProfile {
    employee_id: string;
    specialization: string;
    qualification?: string;
    years_of_experience: number;
    joining_date?: string;
}

export interface StaffProfile extends BaseProfile {
    employee_id: string;
    designation: string;
    department?: string;
    joining_date?: string;
}

export interface InstitutionProfile {
    id: string;
    name: string; // From Organization model
    email?: string; // From Organization model
    phone?: string; // From Organization model
    logo?: string;
    banner?: string;
    tagline?: string;
    mission?: string;
    vision?: string;
    about?: string;
    established_date?: string;
    website?: string;
    facebook_url?: string;
    instagram_url?: string;
    twitter_url?: string;
    linkedin_url?: string;
    created_at: string;
    updated_at: string;
}

export type AnyProfile = StudentProfile | InstructorProfile | StaffProfile;
