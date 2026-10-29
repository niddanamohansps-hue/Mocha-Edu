import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";

export interface VisitorLog {
    id: string;
    pass_number: string;
    visitor_name: string;
    phone: string;
    id_proof_type: string;
    id_proof_number: string;
    organization: string;
    purpose: string;
    purpose_display?: string;
    purpose_details: string;
    person_to_meet_staff?: string;
    person_to_meet_staff_name?: string;
    person_to_meet_name?: string;
    student?: string;
    student_name?: string;
    student_enrollment_id?: string;
    number_of_visitors: number;
    badge_number: string;
    vehicle_number: string;
    check_in_time: string;
    check_out_time?: string | null;
    status: "active" | "checked_out" | "cancelled";
    remarks: string;
    created_at: string;
}

export interface StudentGatePass {
    id: string;
    pass_number: string;
    student: string;
    student_name?: string;
    student_enrollment_id?: string;
    student_class_section?: string;
    departure_date: string;
    departure_time: string;
    actual_exit_time?: string | null;
    reason_category: string;
    reason_category_display?: string;
    reason_details: string;
    picked_up_by_name: string;
    relationship: string;
    relationship_display?: string;
    picked_up_by_phone: string;
    authorized_by_staff?: string;
    authorized_by_staff_name?: string;
    status: "issued" | "departed" | "cancelled";
    gate_security_note: string;
    created_at: string;
}

export interface PostalRecord {
    id: string;
    tracking_number: string;
    record_type: "inward" | "outward";
    record_type_display?: string;
    title: string;
    from_title: string;
    to_title: string;
    courier_company: string;
    dispatch_date: string;
    reference_number: string;
    recipient_staff?: string;
    recipient_staff_name?: string;
    notes: string;
    created_at: string;
}

export interface FrontOfficeOverview {
    today: string;
    active_visitors_inside: number;
    visitors_today: number;
    gate_passes_today: number;
    active_gate_passes: number;
    postal_inward_this_month: number;
}

// -------------------------------------------------------------
// Hooks
// -------------------------------------------------------------

export function useFrontOfficeOverview() {
    return useQuery<FrontOfficeOverview>({
        queryKey: ["front-office-overview"],
        queryFn: async () => {
            const res = await axiosInstance.get("/front-office/overview/");
            return res.data;
        },
    });
}

export function useVisitors(params?: {
    status?: string;
    date?: string;
    search?: string;
}) {
    return useQuery<VisitorLog[]>({
        queryKey: ["visitors", params],
        queryFn: async () => {
            const res = await axiosInstance.get("/front-office/visitors/", { params });
            return Array.isArray(res.data) ? res.data : (res.data.results || []);
        },
    });
}

export function useGatePasses(params?: {
    status?: string;
    date?: string;
    student?: string;
    search?: string;
}) {
    return useQuery<StudentGatePass[]>({
        queryKey: ["gate-passes", params],
        queryFn: async () => {
            const res = await axiosInstance.get("/front-office/gate-passes/", { params });
            return Array.isArray(res.data) ? res.data : (res.data.results || []);
        },
    });
}

export function usePostalRecords(params?: {
    record_type?: string;
    date?: string;
    search?: string;
}) {
    return useQuery<PostalRecord[]>({
        queryKey: ["postal-records", params],
        queryFn: async () => {
            const res = await axiosInstance.get("/front-office/postal/", { params });
            return Array.isArray(res.data) ? res.data : (res.data.results || []);
        },
    });
}

export function useCreateVisitor() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<VisitorLog>) => {
            const res = await axiosInstance.post("/front-office/visitors/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Visitor checked in successfully");
            qc.invalidateQueries({ queryKey: ["visitors"] });
            qc.invalidateQueries({ queryKey: ["front-office-overview"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.visitor_name?.[0] || "Failed to check in visitor");
        },
    });
}

export function useCheckOutVisitor() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, remarks }: { id: string; remarks?: string }) => {
            const res = await axiosInstance.post(`/front-office/visitors/${id}/check_out/`, { remarks });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Visitor checked out");
            qc.invalidateQueries({ queryKey: ["visitors"] });
            qc.invalidateQueries({ queryKey: ["front-office-overview"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.detail || "Failed to check out visitor");
        },
    });
}

export function useCreateGatePass() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<StudentGatePass>) => {
            const res = await axiosInstance.post("/front-office/gate-passes/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Student Gate Pass issued successfully");
            qc.invalidateQueries({ queryKey: ["gate-passes"] });
            qc.invalidateQueries({ queryKey: ["front-office-overview"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.detail || err.response?.data?.student?.[0] || "Failed to issue gate pass");
        },
    });
}

export function useConfirmGatePassExit() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, note }: { id: string; note?: string }) => {
            const res = await axiosInstance.post(`/front-office/gate-passes/${id}/confirm_exit/`, {
                gate_security_note: note,
            });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Student departure recorded by security gate");
            qc.invalidateQueries({ queryKey: ["gate-passes"] });
            qc.invalidateQueries({ queryKey: ["front-office-overview"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.detail || "Failed to record departure");
        },
    });
}

export function useCancelGatePass() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, reason }: { id: string; reason: string }) => {
            const res = await axiosInstance.post(`/front-office/gate-passes/${id}/cancel/`, { reason });
            return res.data;
        },
        onSuccess: () => {
            toast.success("Gate pass cancelled");
            qc.invalidateQueries({ queryKey: ["gate-passes"] });
            qc.invalidateQueries({ queryKey: ["front-office-overview"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.detail || "Failed to cancel gate pass");
        },
    });
}

export function useCreatePostalRecord() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: async (data: Partial<PostalRecord>) => {
            const res = await axiosInstance.post("/front-office/postal/", data);
            return res.data;
        },
        onSuccess: () => {
            toast.success("Postal dispatch logged successfully");
            qc.invalidateQueries({ queryKey: ["postal-records"] });
            qc.invalidateQueries({ queryKey: ["front-office-overview"] });
        },
        onError: (err: any) => {
            toast.error(err.response?.data?.title?.[0] || "Failed to log postal record");
        },
    });
}

