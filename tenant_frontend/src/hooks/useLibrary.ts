import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { PaginatedResponse } from "@/types/Pagination";
import {
    Book,
    BookCategory,
    BookCopy,
    BookInput,
    ClosedLoanResult,
    CopyStatus,
    Fine,
    FineStatus,
    LibrarySettings,
    LibrarySummary,
    Loan,
    LoanState,
} from "@/types/Library";

const KEY = "library";
const errorMessage = inventoryErrorMessage; // the same DRF error shapes
const EVERYTHING = 100; // option lists: the largest page the server allows

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
            if (success) toast.success(success);
        },
        onError: (error: unknown) => toast.error(errorMessage(error, failure)),
    });
}

// --- Summary and settings ------------------------------------------------------------------------

export const useLibrarySummary = () => useScopedQuery<LibrarySummary>(["summary"], "/library/summary/");

export const useLibrarySettings = () => useScopedQuery<LibrarySettings>(["settings"], "/library/settings/");

export const useUpdateLibrarySettings = () =>
    useMutate(
        async (input: Partial<Omit<LibrarySettings, "is_default" | "currency">>) =>
            (await axiosInstance.patch("/library/settings/", input)).data as LibrarySettings,
        "Settings saved",
        "Could not save the settings"
    );

// --- Categories ----------------------------------------------------------------------------------

export const useCategories = () => useScopedQuery<BookCategory[]>(["categories"], "/library/categories/");

export const useSaveCategory = () =>
    useMutate(
        async ({ id, name }: { id?: string; name: string }) =>
            (id ? await axiosInstance.patch(`/library/categories/${id}/`, { name }) : await axiosInstance.post("/library/categories/", { name })).data as BookCategory,
        "Category saved",
        "Could not save the category"
    );

export const useDeleteCategory = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/library/categories/${id}/`), "Category deleted", "Could not delete the category");

// --- Books and copies ----------------------------------------------------------------------------

export const useBooks = (params: { page: number; search: string; category: string; available: boolean }) =>
    useScopedQuery<PaginatedResponse<Book>>(["books"], "/library/books/", {
        page: params.page, search: params.search, category: params.category, available: params.available ? "true" : "",
    });

export const useSaveBook = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<BookInput> }) =>
            (id ? await axiosInstance.patch(`/library/books/${id}/`, input) : await axiosInstance.post("/library/books/", input)).data as Book,
        "Book saved",
        "Could not save the book"
    );

export const useDeleteBook = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/library/books/${id}/`), "Book deleted", "Could not delete the book");

export const useCopies = (book: string) =>
    useScopedQuery<PaginatedResponse<BookCopy>>(["copies", book], "/library/copies/", { book, page_size: EVERYTHING }, !!book);

/** Copies a librarian can lend now, found by accession number or title. */
export const useAvailableCopies = (search: string) =>
    useScopedQuery<PaginatedResponse<BookCopy>>(["copies", "available"], "/library/copies/", { status: "available", search, page_size: 30 });

export const useSaveCopy = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: { book?: string; accession_number?: string; status?: CopyStatus; notes?: string } }) =>
            (id ? await axiosInstance.patch(`/library/copies/${id}/`, input) : await axiosInstance.post("/library/copies/", input)).data as BookCopy,
        "Copy saved",
        "Could not save the copy"
    );

export const useDeleteCopy = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/library/copies/${id}/`), "Copy deleted", "Could not delete the copy");

// --- Loans ---------------------------------------------------------------------------------------

export const useLoans = (params: { page: number; search: string; state: LoanState }) =>
    useScopedQuery<PaginatedResponse<Loan>>(["loans"], "/library/loans/", { ...params });

export const useIssueBook = () =>
    useMutate(
        async (input: { copy: string; student?: string; staff?: string }) =>
            (await axiosInstance.post("/library/loans/", input)).data as Loan,
        "Book issued",
        "Could not issue the book"
    );

export const useReturnBook = () =>
    useMutate(
        async (id: string) => (await axiosInstance.post(`/library/loans/${id}/return/`, {})).data as ClosedLoanResult,
        "",
        "Could not take the book back"
    );

export const useReportLost = () =>
    useMutate(
        async (id: string) => (await axiosInstance.post(`/library/loans/${id}/lost/`, {})).data as ClosedLoanResult,
        "",
        "Could not record the loss"
    );

export const useRenewLoan = () =>
    useMutate(
        async (id: string) => (await axiosInstance.post(`/library/loans/${id}/renew/`, {})).data as Loan,
        "Loan renewed",
        "Could not renew the loan"
    );

// --- Fines ---------------------------------------------------------------------------------------

export const useFines = (params: { page: number; search: string; status: FineStatus | "" }) =>
    useScopedQuery<PaginatedResponse<Fine>>(["fines"], "/library/fines/", { ...params });

export const useBillFine = () =>
    useMutate(async (id: string) => (await axiosInstance.post(`/library/fines/${id}/bill/`, {})).data as Fine, "Fine added to Fees", "Could not bill the fine");

export const useCollectFine = () =>
    useMutate(async (id: string) => (await axiosInstance.post(`/library/fines/${id}/collect/`, {})).data as Fine, "Payment recorded", "Could not record the payment");

export const useWaiveFine = () =>
    useMutate(
        async ({ id, reason }: { id: string; reason: string }) => (await axiosInstance.post(`/library/fines/${id}/waive/`, { reason })).data as Fine,
        "Fine waived",
        "Could not waive the fine"
    );
