import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { AnyProfile, InstitutionProfile } from "@/types/Profile";

async function getMyProfile(): Promise<AnyProfile> {
    const { data } = await axiosInstance.get<AnyProfile>("/profiles/me/");
    return data;
}

async function updateMyProfile(payload: Partial<AnyProfile> | FormData): Promise<AnyProfile> {
    const { data } = await axiosInstance.patch<AnyProfile>("/profiles/me/", payload);
    return data;
}

export function useProfile() {
    return useQuery({
        queryKey: ["profile"],
        queryFn: getMyProfile,
        retry: false,
    });
}

export function useUpdateProfile() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: updateMyProfile,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["profile"] });
            toast.success("Profile updated successfully");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.detail || "Update failed");
        }
    });
}

async function checkSubdomain(subdomain: string): Promise<boolean> {
    const { data } = await axiosInstance.get<{ exists: boolean }>(`/organizations/check-domain/?domain=${subdomain}`);
    return data.exists;
}

export function useCheckSubdomain() {
    return useMutation({
        mutationFn: checkSubdomain,
    });
}

async function getInstitutionProfile(): Promise<InstitutionProfile> {
    const { data } = await axiosInstance.get<InstitutionProfile>("/profiles/institution/");
    return data;
}

async function updateInstitutionProfile(payload: Partial<InstitutionProfile> | FormData): Promise<InstitutionProfile> {
    const { data } = await axiosInstance.patch<InstitutionProfile>("/profiles/institution/", payload);
    return data;
}

export function useInstitutionProfile(enabled = true) {
    return useQuery({
        queryKey: ["institution-profile"],
        queryFn: getInstitutionProfile,
        retry: false,
        enabled,
    });
}

export function useUpdateInstitutionProfile() {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: updateInstitutionProfile,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ["institution-profile"] });
            toast.success("Institution settings updated");
        },
        onError: (error: any) => {
            toast.error(error.response?.data?.detail || "Update failed");
        }
    });
}
