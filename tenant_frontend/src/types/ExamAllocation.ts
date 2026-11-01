export interface SittingPaper {
    schedule: string;
    subject: string;
    class: string;
}

export interface SittingSummary {
    id: string;
    examination: string;
    date: string;
    start_time: string;
    end_time: string;
    papers: SittingPaper[];
    seated: number;
    rooms_used: number;
    invigilators: number;
}

export interface PlanSeat {
    seat: number;
    student_id: string;
    student: string;
    enrollment_id: string;
    class: string;
    subject: string;
}

export interface PlanInvigilator {
    id: string;
    staff_id: string;
    name: string;
    employee_id: string;
    role: "chief" | "invigilator" | "relief";
}

export interface PlanRoom {
    room: { id: string; name: string; capacity: number };
    seats: PlanSeat[];
    invigilators: PlanInvigilator[];
}

export interface SittingPlan {
    sitting: SittingSummary;
    rooms: PlanRoom[];
    /** Students of the papers who have no seat (for example enrolled after the allocation). */
    unseated: number;
}

export interface DutyRow {
    id: string;
    staff_id: string;
    staff: string;
    employee_id: string;
    examination: string;
    date: string;
    start_time: string;
    end_time: string;
    room: string;
    role: "chief" | "invigilator" | "relief";
}
