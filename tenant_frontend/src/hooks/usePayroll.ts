import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { PaginatedResponse } from "@/types/Pagination";
import {
    ComponentInput,
    PayrollAdjustment,
    PayrollRun,
    PayrollSettings,
    PaymentMethod,
    PayStructure,
    Payslip,
    PayslipDetail,
    RunStatus,
    RunSummary,
    SalaryComponent,
    StaffComponentAssignment,
    StaffSalary,
} from "@/types/Payroll";

const KEY = "payroll";
const errorMessage = inventoryErrorMessage; // the same DRF error shapes

function stripEmpty(params: Record<string, unknown>) {
    return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null));
}

function useScopedQuery<T>(parts: unknown[], path: string, params: Record<string, unknown> = {}, enabled = true) {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, ...parts, user?.id, params],
        queryFn: async () => (await axiosInstance.get(path, { params: stripEmpty(params) })).data as T,
        enabled: !!user && enabled,
    });
}

function useMutate<TInput, TResult = unknown>(run: (input: TInput) => Promise<TResult>, success: string, failure: string) {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: run,
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success(success);
        },
        onError: (error: unknown) => toast.error(errorMessage(error, failure)),
    });
}

// --- Runs ----------------------------------------------------------------------------------------

export const useRuns = (filters: { page: number; status: RunStatus | "" }) =>
    useScopedQuery<PaginatedResponse<PayrollRun>>(["runs"], "/payroll/runs/", { ...filters });

export const useRun = (id: string) => useScopedQuery<PayrollRun>(["run", id], `/payroll/runs/${id}/`, {}, !!id);

export const useRunSummary = (id: string, enabled: boolean) =>
    useScopedQuery<RunSummary>(["run-summary", id], `/payroll/runs/${id}/summary/`, {}, !!id && enabled);

export const useRunPayslips = (id: string, params: { page: number; search: string; problems: boolean }) =>
    useScopedQuery<PaginatedResponse<Payslip>>(["run-payslips", id], `/payroll/runs/${id}/payslips/`, {
        page: params.page, search: params.search, problems: params.problems ? "true" : "",
    }, !!id);

export const useRunAdjustments = (id: string) =>
    useScopedQuery<PaginatedResponse<PayrollAdjustment>>(["run-adjustments", id], `/payroll/runs/${id}/adjustments/`, {}, !!id);

export const useCreateRun = () =>
    useMutate(
        async (input: { year: number; month: number; notes?: string }) =>
            (await axiosInstance.post("/payroll/runs/", input)).data as PayrollRun,
        "Payroll started",
        "Could not start the payroll"
    );

type RunAction = "calculate" | "approve" | "pay" | "cancel";
const RUN_ACTION_DONE: Record<RunAction, string> = {
    calculate: "Payroll calculated",
    approve: "Payroll approved",
    pay: "Payment recorded",
    cancel: "Payroll cancelled",
};

export const useRunAction = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async ({ id, action, body }: { id: string; action: RunAction; body?: Record<string, unknown> }) =>
            (await axiosInstance.post(`/payroll/runs/${id}/${action}/`, body ?? {})).data as PayrollRun,
        onSuccess: (_data, variables) => {
            queryClient.invalidateQueries({ queryKey: [KEY] });
            toast.success(RUN_ACTION_DONE[variables.action]);
        },
        onError: (error: unknown) => toast.error(errorMessage(error, "That did not work")),
    });
};

export const useAddAdjustment = () =>
    useMutate(
        async (input: { run: string; staff: string; kind: string; name: string; amount: string; reason: string }) =>
            (await axiosInstance.post("/payroll/adjustments/", input)).data as PayrollAdjustment,
        "Adjustment added",
        "Could not add the adjustment"
    );

export const useRemoveAdjustment = () =>
    useMutate(async (id: string) => (await axiosInstance.delete(`/payroll/adjustments/${id}/`)).data, "Adjustment removed", "Could not remove it");

// --- Payslips -------------------------------------------------------------------------------------

export const usePayslip = (id: string) => useScopedQuery<PayslipDetail>(["payslip", id], `/payroll/payslips/${id}/`, {}, !!id);

export const useMyPayslips = (page: number) =>
    useScopedQuery<PaginatedResponse<Payslip>>(["my-payslips"], "/payroll/my-payslips/", { page });

export const useMyPayslip = (id: string | null) =>
    useScopedQuery<PayslipDetail>(["my-payslip", id], `/payroll/my-payslips/${id}/`, {}, !!id);

/** Fetch a protected file with the login cookie and open it (PDF) or save it (CSV). */
export async function openProtectedFile(path: string, filename: string, mode: "open" | "save") {
    try {
        const response = await axiosInstance.get(path, { responseType: "blob" });
        const url = URL.createObjectURL(response.data as Blob);
        if (mode === "open") {
            window.open(url, "_blank", "noopener");
        } else {
            const link = document.createElement("a");
            link.href = url;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            link.remove();
        }
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
        toast.error("Could not open the file. Please try again.");
        throw error;
    }
}

// --- Salaries and components -----------------------------------------------------------------------

export const useSalaries = (filters: { page: number; search: string }) =>
    useScopedQuery<PaginatedResponse<StaffSalary>>(["salaries"], "/payroll/salaries/", { ...filters });

export const useSalaryHistory = (staffId: string | null) =>
    useScopedQuery<PaginatedResponse<StaffSalary>>(["salary-history", staffId], "/payroll/salaries/history/", { staff: staffId }, !!staffId);

export const useStructure = (staffId: string | null) =>
    useScopedQuery<PayStructure>(["structure", staffId], "/payroll/salaries/structure/", { staff: staffId }, !!staffId);

export const useStaffComponents = (staffId: string | null) =>
    useScopedQuery<PaginatedResponse<StaffComponentAssignment>>(["staff-components", staffId], "/payroll/staff-components/", { staff: staffId, open: "true" }, !!staffId);

export const useSetSalary = () =>
    useMutate(
        async (input: { staff: string; basic_amount: string; effective_from: string; note?: string }) =>
            (await axiosInstance.post("/payroll/salaries/", input)).data as StaffSalary,
        "Salary saved",
        "Could not save the salary"
    );

export const useAssignComponent = () =>
    useMutate(
        async (input: { staff: string; component: string; effective_from: string; value?: string | null }) =>
            (await axiosInstance.post("/payroll/staff-components/", input)).data as StaffComponentAssignment,
        "Component added",
        "Could not add the component"
    );

export const useEndComponent = () =>
    useMutate(
        async ({ id, effective_to }: { id: string; effective_to: string }) =>
            (await axiosInstance.post(`/payroll/staff-components/${id}/end/`, { effective_to })).data,
        "Component ended",
        "Could not end the component"
    );

export const useComponents = (params: { page?: number } = {}) =>
    useScopedQuery<PaginatedResponse<SalaryComponent>>(["components"], "/payroll/components/", { page: params.page ?? 1 });

export const useAllComponents = () => {
    const { data: user } = useMe();
    return useQuery({
        queryKey: [KEY, "all-components", user?.id],
        queryFn: async () => {
            const rows: SalaryComponent[] = [];
            for (let page = 1; page <= 20; page++) {
                const data = (await axiosInstance.get("/payroll/components/", { params: { page } })).data as PaginatedResponse<SalaryComponent>;
                rows.push(...data.results);
                if (!data.next) break;
            }
            return rows;
        },
        enabled: !!user,
    });
};

export const useSaveComponent = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<ComponentInput> }) =>
            (id ? await axiosInstance.patch(`/payroll/components/${id}/`, input) : await axiosInstance.post("/payroll/components/", input)).data as SalaryComponent,
        "Component saved",
        "Could not save the component"
    );

export const useDeleteComponent = () =>
    useMutate(async (id: string) => (await axiosInstance.delete(`/payroll/components/${id}/`)).data, "Component deleted", "Could not delete it");

// --- Settings ---------------------------------------------------------------------------------------

export const usePayrollSettings = () => useScopedQuery<PayrollSettings>(["settings"], "/payroll/settings/");

export const useUpdatePayrollSettings = () =>
    useMutate(
        async (input: Partial<Pick<PayrollSettings, "round_to_whole_rupee" | "require_separate_approver">>) =>
            (await axiosInstance.patch("/payroll/settings/", input)).data as PayrollSettings,
        "Settings saved",
        "Could not save the settings"
    );

export type { PaymentMethod };
