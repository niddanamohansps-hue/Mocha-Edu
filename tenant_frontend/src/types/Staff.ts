export interface InstructorOnboardingData {
    // Personal Info
    first_name: string;
    middle_name?: string;
    last_name: string;
    gender: 'male' | 'female' | 'other';
    date_of_birth?: string;
    phone?: string;
    address?: string;
    email?: string;

    // Professional Info
    joining_date?: string;
    specialization: string; // Default: General
    qualification?: string;
    experience_years?: number;
    bio?: string;
}

export interface InstructorActivationData {
    staff_id: string;
    username: string;
    password?: string; // Optional if we generate it, but usually required
    email?: string;
}

export interface StaffOnboardingData {
    // Personal Info
    first_name: string;
    middle_name?: string;
    last_name: string;
    gender: 'male' | 'female' | 'other';
    date_of_birth?: string;
    phone?: string;
    address?: string;
    email?: string;

    // Professional Info
    designation: string; // Required for generic staff
    department?: string;
    joining_date?: string;
    qualification?: string;
    experience_years?: number;
}

export interface StaffActivationData {
    staff_id: string;
    username: string;
    password?: string;
    email?: string;
    role_slug: string; // Required for generic staff activation
}

export interface ProfileDetails {
    first_name: string;
    middle_name?: string;
    last_name: string;
    gender: string;
    date_of_birth?: string;
    phone: string;
    email: string; // Global user email
    address?: string;
    user_id?: string; // If null, not activated
    local_username?: string;
    photo?: string | null;
    profile_image?: string | null;
}

export interface Instructor {
    id: string; // ID of the Instructor record
    staff_member: StaffMember;
    specialization: string;
    bio: string;
}

export interface StaffMember {
    id: string;
    employee_id: string;
    designation: string;
    department: string;
    joining_date: string;
    qualification?: string;
    experience_years?: number;
    profile_details: ProfileDetails;
    /** Present only for teaching staff; its id is what the assignments filter expects. */
    instructor_data?: { id: number } | null;
}
