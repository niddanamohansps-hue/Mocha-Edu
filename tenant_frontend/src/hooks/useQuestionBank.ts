import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axiosInstance from "@/lib/axios";
import { toast } from "sonner";
import { useMe } from "@/hooks/useAuth";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { PaginatedResponse } from "@/types/Pagination";
import {
    BlueprintRule,
    Chapter,
    Difficulty,
    PaperAccessEntry,
    PaperInput,
    PaperSection,
    PaperStatus,
    PrintablePaper,
    QuestionPaper,
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

// --- Question papers -----------------------------------------------------------------------------

export const usePapers = (filters: { page: number; search: string; status: PaperStatus | "" }) =>
    useScopedQuery<PaginatedResponse<QuestionPaper>>(["papers"], "/question-bank/papers/", { ...filters });

export const usePaper = (id: string) => useScopedQuery<QuestionPaper>(["paper", id], `/question-bank/papers/${id}/`, {}, !!id);

export const usePaperCandidates = (id: string, filters: { search: string; question_type: string; difficulty: string; chapter: string; unused?: string }) =>
    useScopedQuery<PaginatedResponse<Question>>(["paper-candidates", id], `/question-bank/papers/${id}/candidates/`, { ...filters, page_size: 50 }, !!id);

export const usePrintablePaper = (id: string, withAnswers: boolean) =>
    useScopedQuery<PrintablePaper>(["printable", id, withAnswers], `/question-bank/papers/${id}/${withAnswers ? "answer-key" : "printable"}/`, {}, !!id);

export const usePaperAccessLog = (id: string, enabled: boolean) =>
    useScopedQuery<PaperAccessEntry[]>(["paper-log", id], `/question-bank/papers/${id}/access-log/`, {}, !!id && enabled);

export const useSavePaper = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: Partial<PaperInput> }) =>
            (id ? await axiosInstance.patch(`/question-bank/papers/${id}/`, input) : await axiosInstance.post("/question-bank/papers/", input)).data as QuestionPaper,
        "Paper saved",
        "Could not save the paper"
    );

export const useDeletePaper = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/question-bank/papers/${id}/`), "Draft deleted", "Could not delete the paper");

function usePaperAction(verb: string, success: string, failure: string) {
    return useMutate(
        async ({ id, body }: { id: string; body?: Record<string, unknown> }) =>
            (await axiosInstance.post(`/question-bank/papers/${id}/${verb}/`, body ?? {})).data as QuestionPaper,
        success,
        failure
    );
}

export const useSubmitPaper = () => usePaperAction("submit", "Sent for approval", "Could not submit the paper");
export const useApprovePaper = () => usePaperAction("approve", "Paper approved", "Could not approve the paper");
export const useSendBackPaper = () => usePaperAction("send-back", "Sent back to the preparer", "Could not send the paper back");
export const useReleasePaper = () => usePaperAction("release", "Paper released", "Could not release the paper");
export const useWithdrawPaper = () => usePaperAction("withdraw", "Paper withdrawn", "Could not withdraw the paper");
export const useSchedulePaper = () => usePaperAction("schedule", "Release time saved", "Could not save the release time");
export const useAutofillPaper = () => usePaperAction("autofill", "Filled from the blueprint", "Could not fill the paper");
export const useAddPaperQuestion = () => usePaperAction("questions", "Question added", "Could not add the question");

export const useRemovePaperQuestion = () =>
    useMutate(
        async ({ id, item }: { id: string; item: string }) => (await axiosInstance.delete(`/question-bank/papers/${id}/questions/${item}/`)).data as QuestionPaper,
        "Question removed",
        "Could not remove the question"
    );

export const useSaveSection = () =>
    useMutate(
        async ({ id, input }: { id?: string; input: { paper?: string; order?: number; title?: string; instructions?: string } }) =>
            (id ? await axiosInstance.patch(`/question-bank/paper-sections/${id}/`, input) : await axiosInstance.post("/question-bank/paper-sections/", input)).data as PaperSection,
        "Section saved",
        "Could not save the section"
    );

export const useDeleteSection = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/question-bank/paper-sections/${id}/`), "Section deleted", "Could not delete the section");

export const useAddRule = () =>
    useMutate(
        async (input: { section: string; count: number; question_type: string; difficulty: string; chapter: string | null; marks: string | null }) =>
            (await axiosInstance.post("/question-bank/blueprint-rules/", input)).data as BlueprintRule,
        "Blueprint rule added",
        "Could not add the rule"
    );

export const useDeleteRule = () =>
    useMutate(async (id: string) => axiosInstance.delete(`/question-bank/blueprint-rules/${id}/`), "Rule removed", "Could not remove the rule");

export interface PaperChoices {
    examinations: { id: string; name: string; academic_year: string }[];
    subjects: { id: string; name: string; code: string; level_name: string }[];
}

export const usePaperChoices = (enabled: boolean) =>
    useScopedQuery<PaperChoices>(["paper-choices"], "/question-bank/papers/choices/", {}, enabled);
