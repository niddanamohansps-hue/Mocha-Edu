export interface Program {
    id: string;
    name: string;
    code: string;
    description: string;
    is_active: boolean;
    levels: AcademicLevel[];
}

export interface AcademicLevel {
    id: string;
    program: string; // Program parameters
    program_name: string;
    name: string;
    order: number;
    sections: Section[];
}

export interface Section {
    id: string;
    level: string;
    level_name: string;
    program_name: string;
    name: string;
    capacity: number;
}

export interface Subject {
    id: string;
    level: string;
    level_name: string;
    name: string;
    code: string;
    credits: number;
    is_elective: boolean;
    description: string;
}

export interface SubjectAssignment {
    id: string;
    section: string;
    section_details: Section;
    subject: string;
    subject_details: Subject;
    instructor: string | null;
    instructor_details: any; // Using any for now to avoid circular dependency with Staff types if not needed fully
}

export interface AcademicYear {
    id: string;
    name: string;
    start_date: string;
    end_date: string;
    is_current: boolean;
    created_at: string;
    updated_at: string;
}

