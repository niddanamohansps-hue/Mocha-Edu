import { useQuery } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import {
    ChildAttendance,
    ChildExamResult,
    ChildFeesResponse,
    ChildReportCard,
    ChildTimetableResponse,
    LinkedChild,
    ParentMe,
    UpcomingExam,
} from "@/types/ParentPortal";

export const useParentMe = () => {
    return useQuery({
        queryKey: ["parent-portal", "me"],
        queryFn: async () => {
            const response = await axiosInstance.get("/parent-portal/me/");
            return response.data as ParentMe;
        },
        retry: false,
    });
};

export const useLinkedChildren = () => {
    return useQuery({
        queryKey: ["parent-portal", "children"],
        queryFn: async () => {
            const response = await axiosInstance.get("/parent-portal/children/");
            return response.data as LinkedChild[];
        },
    });
};

export const useChildAttendance = (
    studentId: string | undefined,
    startDate?: string,
    endDate?: string
) => {
    return useQuery({
        queryKey: ["parent-portal", "attendance", studentId, startDate, endDate],
        queryFn: async () => {
            const params = new URLSearchParams();
            if (startDate) params.set("start_date", startDate);
            if (endDate) params.set("end_date", endDate);
            const qs = params.toString();
            const response = await axiosInstance.get(
                `/parent-portal/children/${studentId}/attendance/${qs ? `?${qs}` : ""}`
            );
            return response.data as ChildAttendance;
        },
        enabled: !!studentId,
    });
};

export const useChildTimetable = (studentId: string | undefined) => {
    return useQuery({
        queryKey: ["parent-portal", "timetable", studentId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/parent-portal/children/${studentId}/timetable/`);
            return response.data as ChildTimetableResponse;
        },
        enabled: !!studentId,
    });
};

export const useChildResults = (studentId: string | undefined) => {
    return useQuery({
        queryKey: ["parent-portal", "results", studentId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/parent-portal/children/${studentId}/results/`);
            return response.data as ChildExamResult[];
        },
        enabled: !!studentId,
    });
};

export const useChildReportCard = (studentId: string | undefined) => {
    return useQuery({
        queryKey: ["parent-portal", "report-card", studentId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/parent-portal/children/${studentId}/report-card/`);
            return response.data as ChildReportCard;
        },
        enabled: !!studentId,
    });
};

export const useChildFees = (studentId: string | undefined) => {
    return useQuery({
        queryKey: ["parent-portal", "fees", studentId],
        queryFn: async () => {
            const response = await axiosInstance.get(`/parent-portal/children/${studentId}/fees/`);
            return response.data as ChildFeesResponse;
        },
        enabled: !!studentId,
    });
};

export const useChildUpcomingExams = (studentId: string | undefined) => {
    return useQuery({
        queryKey: ["parent-portal", "upcoming-exams", studentId],
        queryFn: async () => {
            const response = await axiosInstance.get(
                `/parent-portal/children/${studentId}/upcoming-exams/`
            );
            return response.data as UpcomingExam[];
        },
        enabled: !!studentId,
    });
};
