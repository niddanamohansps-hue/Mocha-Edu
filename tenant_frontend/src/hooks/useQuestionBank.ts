import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { PaginatedResponse } from "@/types/Pagination";
import {
    Chapter,
    Difficulty,
    MyScope,
    Question,
    QuestionHistory,
    QuestionInput,
    QuestionStatus,
    QuestionType,
    ReviewDecision,
    SubjectReviewer,
    Topic,
} from "@/types/QuestionBank";

const KEY = "question-bank";
const errorMessage = inventoryErrorMessage; // the same DRF error shapes

function stripEmpty(params: Record<string, unknown>) {
    return Object.fromEntries(Object.entries(params).filter(([, v]) => v !== "" && v !== undefined && v !== null && v !== false));
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

export const useMyScope = () => useScopedQuery<MyScope>(["scope"], "/question-bank/my-scope/");

// --- Questions -----------------------------------------------------------------------------------

export interface QuestionFilters {
    page: number;
    search: string;
    subject: string;
    status: QuestionStatus | "";
    question_type: QuestionType | "";
    difficulty: Difficulty | "";
    mine: boolean;
    to_review: boolean;
}

export const useQuestions = (filters: QuestionFilters) =>
    useScopedQuery<PaginatedResponse<Question>>(["questions"], "/question-bank/questions/", {
        ...filters, mine: filters.mine ? "true" : "", to_review: filters.to_review ? "true" : "",
    });

export const useQuestion = (id: string) => useScopedQuery<Question>(["question", id], `/question-bank/questions/${id}/`, {}, !!id);

export const useQuestionHistory = (id: string) =>
    useScopedQuery<QuestionHistory>(["history", id], `/question-bank/questions/${id}/history/`, {}, !!id);

export const useSaveQuestion = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<QuestionInput> }) =>
            (id ? await axiosInstance.patch(`/question-bank/questions/${id}/`, input) : await axiosInstance.post("/question-bank/questions/", input)).data as Question,
        "Question saved",
        "Could not save the question"
    );

export const useDeleteQuestion = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/question-bank/questions/${id}/`), "Draft deleted", "Could not delete the draft");

export const useSubmitQuestion = () =>
    useMutate(async (id: string) => (await axiosInstance.post(`/question-bank/questions/${id}/submit/`, {})).data as Question, "Sent for review", "Could not submit");

export const useArchiveQuestion = () =>
    useMutate(async (id: string) => (await axiosInstance.post(`/question-bank/questions/${id}/archive/`, {})).data as Question, "Archived", "Could not archive");

export const useReviewQuestion = () =>
    useMutate(
        async ({ id, decision, comment }: { id: string; decision: ReviewDecision; comment: string }) =>
            (await axiosInstance.post(`/question-bank/questions/${id}/review/`, { decision, comment })).data as Question,
        "Decision saved",
        "Could not save the decision"
    );

// --- Setup ---------------------------------------------------------------------------------------

export const useChapters = (subject: string) =>
    useScopedQuery<Chapter[]>(["chapters", subject], "/question-bank/chapters/", { subject }, !!subject);

export const useSaveChapter = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: { subject?: string; name: string; order: number } }) =>
            (id ? await axiosInstance.patch(`/question-bank/chapters/${id}/`, input) : await axiosInstance.post("/question-bank/chapters/", input)).data as Chapter,
        "Chapter saved",
        "Could not save the chapter"
    );

export const useDeleteChapter = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/question-bank/chapters/${id}/`), "Chapter deleted", "Could not delete the chapter");

export const useSaveTopic = () =>
    useMutate(
        async (input: { chapter: string; name: string; order: number }) => (await axiosInstance.post("/question-bank/topics/", input)).data as Topic,
        "Topic added",
        "Could not add the topic"
    );

export const useDeleteTopic = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/question-bank/topics/${id}/`), "Topic deleted", "Could not delete the topic");

export const useReviewers = () => useScopedQuery<SubjectReviewer[]>(["reviewers"], "/question-bank/reviewers/");

export const useAddReviewer = () =>
    useMutate(
        async (input: { subject: string; staff: string }) => (await axiosInstance.post("/question-bank/reviewers/", input)).data as SubjectReviewer,
        "Reviewer added",
        "Could not add the reviewer"
    );

export const useRemoveReviewer = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/question-bank/reviewers/${id}/`), "Reviewer removed", "Could not remove the reviewer");
