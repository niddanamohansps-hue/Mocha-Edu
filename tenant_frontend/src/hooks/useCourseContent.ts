import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import type { PaginatedResponse } from "@/types/Pagination";
import {
    CourseContent,
    Assignment,
    AssignmentSubmission,
    SubjectEnrollment,
    CreateAssignmentData,
    CreateContentData,
    BulkEnrollData,
    SubmitAssignmentData,
    GradeSubmissionData
} from "@/types/CourseContent";

// === COURSE CONTENT ===

export const useCourseContent = (contentType?: string, excludeAssignments?: boolean) => {
    return useQuery({
        queryKey: ["course-content", contentType, excludeAssignments],
        queryFn: async () => {
            // page_size=100: backend now paginates this endpoint (see the
            // pagination audit) - 100 safely covers today's library size
            // without requiring this screen to grow visible pagination UI
            // in the same change. Revisit with real Previous/Next controls
            // if the library grows past 100 items.
            const params: any = { page_size: 100 };
            if (contentType) params.content_type = contentType;
            if (excludeAssignments) params.exclude_assignments = 'true';

            const response = await axiosInstance.get("/course-content/content/", { params });
            return (response.data as PaginatedResponse<CourseContent>).results;
        }
    });
};

export const useMyCourseContent = () => {
    return useQuery({
        queryKey: ["my-course-content"],
        queryFn: async () => {
            const response = await axiosInstance.get("/course-content/content/my_content/", {
                params: { page_size: 100 },
            });
            return (response.data as PaginatedResponse<CourseContent>).results;
        }
    });
};

export const useCreateContent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: CreateContentData) => {
            const formData = new FormData();
            formData.append("title", data.title);
            formData.append("description", data.description);
            formData.append("content_type", data.content_type);

            if (data.file) formData.append("file", data.file);
            if (data.external_url) formData.append("external_url", data.external_url);
            if (data.is_published !== undefined) formData.append("is_published", String(data.is_published));
            if (data.is_pinned !== undefined) formData.append("is_pinned", String(data.is_pinned));

            // Handle array fields
            if (data.target_programs) {
                data.target_programs.forEach(id => formData.append("target_programs", id));
            }
            if (data.target_levels) {
                data.target_levels.forEach(id => formData.append("target_levels", id));
            }
            if (data.target_sections) {
                data.target_sections.forEach(id => formData.append("target_sections", id));
            }
            if (data.target_subjects) {
                data.target_subjects.forEach(id => formData.append("target_subjects", id));
            }
            if (data.specific_students) {
                data.specific_students.forEach(id => formData.append("specific_students", id));
            }

            const response = await axiosInstance.post("/course-content/content/", formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["course-content"] });
            queryClient.invalidateQueries({ queryKey: ["my-course-content"] });
            toast.success("Content created successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.message || "Failed to create content");
        }
    });
};

export const useDeleteContent = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/course-content/content/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["course-content"] });
            queryClient.invalidateQueries({ queryKey: ["my-course-content"] });
            toast.success("Content deleted successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.message || "Failed to delete content");
        }
    });
};

// === ASSIGNMENTS ===

export const useAssignments = () => {
    return useQuery({
        queryKey: ["assignments"],
        queryFn: async () => {
            const response = await axiosInstance.get("/course-content/assignments/", {
                params: { page_size: 100 },
            });
            return (response.data as PaginatedResponse<Assignment>).results;
        }
    });
};

export const useCreateAssignment = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: CreateAssignmentData) => {
            const formData = new FormData();
            formData.append("title", data.title);
            formData.append("description", data.description);
            formData.append("due_date", data.due_date);
            formData.append("instructions", data.instructions);

            if (data.file) formData.append("file", data.file);
            if (data.external_url) formData.append("external_url", data.external_url);
            if (data.total_points) formData.append("total_points", String(data.total_points));
            if (data.submission_type) formData.append("submission_type", data.submission_type);
            if (data.allow_late_submission !== undefined) formData.append("allow_late_submission", String(data.allow_late_submission));
            if (data.late_penalty_percent) formData.append("late_penalty_percent", String(data.late_penalty_percent));
            if (data.is_published !== undefined) formData.append("is_published", String(data.is_published));
            if (data.is_pinned !== undefined) formData.append("is_pinned", String(data.is_pinned));

            // Handle array fields
            if (data.target_programs) {
                data.target_programs.forEach(id => formData.append("target_programs", id));
            }
            if (data.target_levels) {
                data.target_levels.forEach(id => formData.append("target_levels", id));
            }
            if (data.target_sections) {
                data.target_sections.forEach(id => formData.append("target_sections", id));
            }
            if (data.target_subjects) {
                data.target_subjects.forEach(id => formData.append("target_subjects", id));
            }
            if (data.specific_students) {
                data.specific_students.forEach(id => formData.append("specific_students", id));
            }

            const response = await axiosInstance.post("/course-content/assignments/", formData, {
                headers: { "Content-Type": "multipart/form-data" }
            });
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["assignments"] });
            toast.success("Assignment created successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.message || "Failed to create assignment");
        }
    });
};

export const useDeleteAssignment = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (id: string) => {
            await axiosInstance.delete(`/course-content/assignments/${id}/`);
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["assignments"] });
            toast.success("Assignment deleted successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.message || "Failed to delete assignment");
        }
    });
};

// === SUBMISSIONS ===

export const useSubmissions = (assignmentId?: string) => {
    return useQuery({
        queryKey: ["submissions", assignmentId],
        queryFn: async () => {
            const params: Record<string, string | number> = { page_size: 100 };
            if (assignmentId) params.assignment = assignmentId;
            const response = await axiosInstance.get("/course-content/submissions/", { params });
            return (response.data as PaginatedResponse<AssignmentSubmission>).results;
        }
    });
};

export const useMySubmissions = () => {
    return useQuery({
        queryKey: ["my-submissions"],
        queryFn: async () => {
            const response = await axiosInstance.get("/course-content/submissions/", {
                params: { page_size: 100 },
            });
            return (response.data as PaginatedResponse<AssignmentSubmission>).results;
        }
    });
};

export const useSubmitAssignment = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ submissionId, data }: { submissionId: string; data: SubmitAssignmentData }) => {
            const formData = new FormData();
            if (data.submission_file) formData.append("submission_file", data.submission_file);
            if (data.submission_text) formData.append("submission_text", data.submission_text);
            if (data.submission_url) formData.append("submission_url", data.submission_url);

            const response = await axiosInstance.post(
                `/course-content/submissions/${submissionId}/submit/`,
                formData,
                { headers: { "Content-Type": "multipart/form-data" } }
            );
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["submissions"] });
            queryClient.invalidateQueries({ queryKey: ["my-submissions"] });
            toast.success("Assignment submitted successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.message || "Failed to submit assignment");
        }
    });
};

export const useGradeSubmission = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ submissionId, data }: { submissionId: string; data: GradeSubmissionData }) => {
            const response = await axiosInstance.post(
                `/course-content/submissions/${submissionId}/grade/`,
                data
            );
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["submissions"] });
            toast.success("Submission graded successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.message || "Failed to grade submission");
        }
    });
};

// === SUBJECT ENROLLMENT ===

export const useSubjectEnrollments = (studentId?: string, subjectId?: string) => {
    return useQuery({
        queryKey: ["subject-enrollments", studentId, subjectId],
        queryFn: async () => {
            const params: any = {};
            if (studentId) params.student = studentId;
            if (subjectId) params.subject = subjectId;

            const response = await axiosInstance.get("/course-content/subject-enrollments/", { params });
            return response.data as SubjectEnrollment[];
        }
    });
};

export const useBulkEnroll = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (data: BulkEnrollData) => {
            const response = await axiosInstance.post("/course-content/subject-enrollments/bulk_enroll/", data);
            return response.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["subject-enrollments"] });
            toast.success("Students enrolled successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.message || "Failed to enroll students");
        }
    });
};
