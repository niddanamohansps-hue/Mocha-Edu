import { useQuery } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { useMe } from "@/hooks/useAuth";

export interface DashboardStudentCounts {
    total: number;
    active: number;
    inactive: number;
    graduated: number;
    withdrawn: number;
    transferred: number;
}

export interface DashboardStaffCounts {
    active: number;
}

export interface DashboardAcademicCounts {
    programs: number;
    levels: number;
    sections: number;
}

export interface DashboardAttendanceSummary {
    today_percentage: number | null;
}

export interface DashboardFeesSummary {
    outstanding: string;
}

export interface DashboardPromotionActivity {
    id: string;
    student: string;
    student_name: string;
    enrollment_id: string;
    action: string;
    source_academic_year: string;
    target_academic_year: string;
    source_level_name: string | null;
    target_level_name: string | null;
    source_section_name: string | null;
    target_section_name: string | null;
    reason: string;
    is_reversed: boolean;
    created_at: string;
}

export interface DashboardPromotionSummary {
    recent: DashboardPromotionActivity[];
}

export interface DashboardNotificationsSummary {
    unread: number;
}

export interface DashboardSummary {
    students: DashboardStudentCounts;
    staff: DashboardStaffCounts;
    academics: DashboardAcademicCounts;
    attendance: DashboardAttendanceSummary;
    fees: DashboardFeesSummary;
    promotion: DashboardPromotionSummary;
    notifications: DashboardNotificationsSummary;
}

export const useDashboardSummary = () => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: ["dashboard", "summary", user?.id],
        queryFn: async () => {
            const response = await axiosInstance.get("/dashboard/summary/");
            return response.data as DashboardSummary;
        },
        enabled: !!user,
    });
};
