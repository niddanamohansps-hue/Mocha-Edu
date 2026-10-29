import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type { PaginatedResponse } from "@/types/Pagination";

export interface StudentEnrollmentData {
    first_name: string;
    middle_name?: string;
    last_name: string;
    email?: string;
    gender: 'male' | 'female' | 'other';
    date_of_birth: string;
    phone?: string;
    address?: string;
    level: string;
    section?: string;
    academic_year: string;
    admission_date?: string;
    previous_school?: string;
    last_grade_passed?: string;
    parents?: Array<{
        first_name: string;
        last_name: string;
        phone: string;
        gender: string;
        occupation?: string;
        relation: string;
        is_primary: boolean;
    }>;
}

export const useEnrollStudent = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (data: StudentEnrollmentData) => {
            const response = await axiosInstance.post("/students/enroll/", data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["students"] });
            toast.success("Student enrolled successfully!");
        },
        onError: (error: any) => {
            const message = error.response?.data?.message || "Failed to enroll student";
            toast.error(message);
        }
    });
};

export interface Student {
    id: string;
    first_name: string;
    middle_name?: string;
    last_name: string;
    full_name: string;
    enrollment_id: string;
    level: string;
    section: string;
    status: string;
    has_account: boolean;
    apaar_id?: string;
    pen?: string;
    caste_category?: string;
    is_rte?: boolean;
    aadhaar_last_4?: string;
    mother_name?: string;
    father_name?: string;
    guardian_name?: string;
}

export interface AccountCreationData {
    student_id: string;
    username: string;
    password?: string;
    email?: string;
}

export interface PendingCredential {
    id: string;
    full_name: string;
    enrollment_id: string;
    username: string;
    initial_password: string;
}

export const usePortalActivation = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (enrollments: AccountCreationData[]) => {
            const response = await axiosInstance.post("/students/portal-activation/", { enrollments });
            return response.data;
        },
        onSuccess: (data) => {
            queryClient.invalidateQueries({ queryKey: ["students"] });
            queryClient.invalidateQueries({ queryKey: ["pending-credentials"] });
            toast.success(data.message || "Portal activated successfully!");
        },
        onError: (error: any) => {
            const message = error.response?.data?.message || "Failed to activate portal";
            toast.error(message);
        }
    });
};

export const useStudents = (
    options: { page?: number; unenrolled?: boolean; pageSize?: number; search?: string; status?: string } = {}
) => {
    const { page = 1, unenrolled = false, pageSize = 20, search = "", status = "" } = options;
    return useQuery({
        queryKey: ["students", { page, unenrolled, pageSize, search, status }],
        queryFn: async () => {
            const response = await axiosInstance.get(`/students/list/`, {
                params: {
                    unenrolled, page, page_size: pageSize,
                    ...(search ? { search } : {}),
                    ...(status ? { status } : {}),
                }
            });
            return response.data as PaginatedResponse<Student>;
        }
    });
};

export const usePendingCredentials = () => {
    return useQuery({
        queryKey: ["pending-credentials"],
        queryFn: async () => {
            const response = await axiosInstance.get("/students/credentials/");
            return response.data as PendingCredential[];
        }
    });
};
export const useUpdateStudent = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ id, data }: { id: string; data: StudentEnrollmentData }) => {
            const response = await axiosInstance.put(`/students/detail/${id}/`, data);
            return response.data;
        },
        onSuccess: (_, variables) => {
            queryClient.invalidateQueries({ queryKey: ["students"] });
            queryClient.invalidateQueries({ queryKey: ["student", variables.id] });
            toast.success("Student updated successfully!");
        },
        onError: (error: any) => {
            const message = error.response?.data?.message || "Failed to update student";
            toast.error(message);
        }
    });
};

export const useDeleteStudent = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/students/detail/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["students"] });
            toast.success("Student deleted successfully!");
        },
        onError: (error: any) => {
            const message = error.response?.data?.message || "Failed to delete student";
            toast.error(message);
        }
    });
};

export const useStudent = (id: string, enabled: boolean = true) => {
    return useQuery({
        queryKey: ["student", id],
        queryFn: async () => {
            const response = await axiosInstance.get(`/students/detail/${id}/`);
            return response.data;
        },
        enabled: !!id && enabled
    });
};
