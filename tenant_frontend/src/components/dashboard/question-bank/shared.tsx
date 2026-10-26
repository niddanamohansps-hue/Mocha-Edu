"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Pill } from "@/components/dashboard/inventory/shared";
import { usePermissions } from "@/providers/PermissionProvider";
import { PAPER_STATUS_LABELS, PaperStatus, QuestionStatus, STATUS_LABELS } from "@/types/QuestionBank";

export {
    Field,
    FILTER_SELECT_CLASS,
    FormDialog,
    PageHeader,
    Pager,
    Pill,
    SELECT_CLASS,
    formatDate,
    formatDateTime,
} from "@/components/dashboard/inventory/shared";

const TABS = [
    { href: "/dashboard/question-bank", label: "Questions", exact: true, show: () => true },
    { href: "/dashboard/question-bank/review", label: "To review", show: (can: (p: string) => boolean) => can("review_questions") },
    {
        href: "/dashboard/question-bank/papers", label: "Papers",
        show: (can: (p: string) => boolean) => can("prepare_papers") || can("approve_papers") || can("view_examinations"),
    },
    { href: "/dashboard/question-bank/setup", label: "Chapters & reviewers", show: () => true },
];

export function QuestionBankNav() {
    const pathname = usePathname();
    const { can } = usePermissions();
    return (
        <nav className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800" aria-label="Question bank sections">
            {TABS.filter((tab) => tab.show(can)).map((tab) => {
                const active = tab.exact ? pathname === tab.href : pathname.startsWith(tab.href);
                return (
                    <Link
                        key={tab.href}
                        href={tab.href}
                        aria-current={active ? "page" : undefined}
                        className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                            active
                                ? "border-sky-600 text-sky-700 dark:text-sky-400"
                                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                        }`}
                    >
                        {tab.label}
                    </Link>
                );
            })}
        </nav>
    );
}

const STATUS_STYLES: Record<QuestionStatus, string> = {
    draft: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    submitted: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    changes_requested: "bg-orange-100 text-orange-700 dark:bg-orange-500/10 dark:text-orange-400",
    approved: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    rejected: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
    archived: "bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400",
};

export function StatusBadge({ status }: { status: QuestionStatus }) {
    return <Pill className={STATUS_STYLES[status]}>{STATUS_LABELS[status]}</Pill>;
}

/** Any of the question bank permissions opens the module. */
export function useCanUseBank() {
    const { can } = usePermissions();
    return can("view_question_bank") || can("create_questions") || can("review_questions") || can("manage_question_bank");
}

const PAPER_STYLES: Record<PaperStatus, string> = {
    draft: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    submitted: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    approved: "bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
    released: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    withdrawn: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
};

export function PaperStatusBadge({ status }: { status: PaperStatus }) {
    return <Pill className={PAPER_STYLES[status]}>{PAPER_STATUS_LABELS[status]}</Pill>;
}
