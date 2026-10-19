import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { PaginatedResponse } from "@/types/Pagination";
import {
    Certificate,
    CertificateFilters,
    CertificateSettings,
    IdCardData,
    IssueCertificateInput,
    PublicCertificateVerification,
    PublicIdCardVerification,
    ReissueInput,
} from "@/types/Certificates";

export function certificateErrorMessage(error: unknown, fallback: string) {
    const data = (error as { response?: { data?: Record<string, unknown> } })?.response?.data;
    if (!data || typeof data !== "object") return fallback;
    if (typeof data.detail === "string") return data.detail;
    for (const key of Object.keys(data)) {
        const value = data[key];
        const text = Array.isArray(value) ? value[0] : value;
        if (typeof text === "string") return key === "non_field_errors" ? text : `${key.replace(/_/g, " ")}: ${text}`;
    }
    return fallback;
}

const KEY = "certificates";

export const useCertificates = (filters: CertificateFilters) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "list", user?.id, filters],
        queryFn: async () => {
            const params: Record<string, string | number> = { page: filters.page };
            if (filters.certificate_type) params.certificate_type = filters.certificate_type;
            if (filters.status) params.status = filters.status;
            if (filters.search) params.search = filters.search;
            return (await axiosInstance.get("/certificates/", { params })).data as PaginatedResponse<Certificate>;
        },
        enabled: !!user,
    });
};

export const useCertificate = (id: string) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "detail", user?.id, id],
        queryFn: async () => (await axiosInstance.get(`/certificates/${id}/`)).data as Certificate,
        enabled: !!user && !!id,
    });
};

export const useIssueCertificate = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (input: IssueCertificateInput) =>
            (await axiosInstance.post("/certificates/", input)).data as Certificate,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success("Certificate issued");
        },
        onError: (error: unknown) => toast.error(certificateErrorMessage(error, "Failed to issue certificate")),
    });
};

export const useCancelCertificate = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, reason }: { id: string; reason: string }) =>
            (await axiosInstance.post(`/certificates/${id}/cancel/`, { reason })).data as Certificate,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success("Certificate cancelled");
        },
        onError: (error: unknown) => toast.error(certificateErrorMessage(error, "Failed to cancel certificate")),
    });
};

export const useReissueCertificate = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, input }: { id: string; input: ReissueInput }) =>
            (await axiosInstance.post(`/certificates/${id}/reissue/`, input)).data as Certificate,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success("Certificate reissued");
        },
        onError: (error: unknown) => toast.error(certificateErrorMessage(error, "Failed to reissue certificate")),
    });
};

export const useCertificateSettings = () => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "settings", user?.id],
        queryFn: async () => (await axiosInstance.get("/certificates/settings/")).data as CertificateSettings,
        enabled: !!user,
    });
};

export const useUpdateCertificateSettings = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (input: { signatory_name: string; signatory_title: string; signature?: File | null }) => {
            const form = new FormData();
            form.append("signatory_name", input.signatory_name);
            form.append("signatory_title", input.signatory_title);
            if (input.signature) form.append("signature", input.signature);
            return (await axiosInstance.patch("/certificates/settings/", form)).data as CertificateSettings;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY, "settings"] });
            toast.success("Certificate settings saved");
        },
        onError: (error: unknown) => toast.error(certificateErrorMessage(error, "Failed to save settings")),
    });
};

/** Downloads a PDF through the authenticated client (the endpoint needs the session). */
export async function downloadPdf(path: string, filename: string) {
    try {
        const response = await axiosInstance.get(path, { responseType: "blob" });
        const url = URL.createObjectURL(response.data as Blob);
        const link = document.createElement("a");
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
    } catch (error) {
        toast.error(certificateErrorMessage(error, "Could not download the PDF"));
    }
}

export const useIdCard = (kind: "student" | "staff", id: string | undefined) => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "id-card", user?.id, kind, id],
        queryFn: async () => (await axiosInstance.get(`/certificates/id-cards/${kind}/${id}/`)).data as IdCardData,
        enabled: !!user && !!id,
        retry: false,
    });
};

// Public verification: no session. A plain axios call keeps the auth
// interceptor (token refresh / login redirect) out of the way.
function publicBaseUrl() {
    if (typeof window !== "undefined") {
        const hostname = window.location.hostname;
        if (hostname.includes(".localhost")) return `http://${hostname.split(".")[0]}.localhost:8000/api`;
    }
    return "http://localhost:8000/api";
}

export const usePublicCertificateVerification = (verificationId: string) =>
    useQuery({
        queryKey: [KEY, "public", verificationId],
        queryFn: async () =>
            (await axios.get(`${publicBaseUrl()}/certificates/verify/certificate/${verificationId}/`))
                .data as PublicCertificateVerification,
        enabled: !!verificationId,
        retry: false,
    });

export const usePublicIdCardVerification = (token: string) =>
    useQuery({
        queryKey: [KEY, "public-id", token],
        queryFn: async () =>
            (await axios.get(`${publicBaseUrl()}/certificates/verify/id/${token}/`)).data as PublicIdCardVerification,
        enabled: !!token,
        retry: false,
    });

export const useRotateIdCard = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ kind, id }: { kind: "student" | "staff"; id: string }) =>
            (await axiosInstance.post(`/certificates/id-cards/${kind}/${id}/rotate/`)).data as { rotated: boolean },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY, "id-card"] });
            toast.success("QR code replaced. Print the card again; old printed codes no longer verify.");
        },
        onError: (error: unknown) => toast.error(certificateErrorMessage(error, "Could not replace the QR code")),
    });
};
