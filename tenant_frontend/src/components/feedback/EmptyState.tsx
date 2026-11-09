import { cn } from "@/lib/utils";
import { FolderOpen } from "lucide-react";

export interface EmptyStateProps {
    /** Icon element, e.g. <GraduationCap className="h-6 w-6" />. Optional. */
    icon?: React.ReactNode;
    /** Primary message, e.g. "No students found." */
    title: string;
    /** Tag the title renders as - use h1/h2/h3 where the state replaces a real
     * page heading (e.g. a "not found" page) so the semantic heading isn't
     * lost. Defaults to "p" (the original, non-heading behavior). */
    titleAs?: "p" | "h1" | "h2" | "h3";
    /** Optional secondary line of detail/guidance. */
    description?: string;
    /** Optional action (e.g. a "Create one" button) rendered below the text. */
    action?: React.ReactNode;
    /** Helpful onboarding tip or next step */
    hint?: string;
    className?: string;
}

/**
 * Standardized "no data" block. Replaces the repeated
 * `flex flex-col items-center justify-center text-slate-400 py-10` + icon + message
 * markup copy-pasted across feature tables.
 */
export function EmptyState({ icon, title, titleAs = "p", description, action, hint, className }: EmptyStateProps) {
    const TitleTag = titleAs;
    return (
        <div
            className={cn(
                "flex flex-col items-center justify-center text-center p-8 sm:p-12 rounded-2xl border border-dashed border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/40",
                className
            )}
        >
            <div className="w-12 h-12 rounded-2xl bg-sky-50 dark:bg-sky-950/60 border border-sky-100 dark:border-sky-900/50 flex items-center justify-center text-sky-600 dark:text-sky-400 mb-3 shadow-2xs">
                {icon || <FolderOpen className="h-6 w-6 stroke-[1.75]" />}
            </div>
            <TitleTag className="text-sm sm:text-base font-semibold text-slate-900 dark:text-white">
                {title}
            </TitleTag>
            {description ? (
                <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 max-w-md mt-1 leading-relaxed">
                    {description}
                </p>
            ) : null}
            {hint ? (
                <div className="mt-3 inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-amber-50 dark:bg-amber-950/40 text-amber-700 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800/80">
                    <span className="font-bold">Tip:</span> {hint}
                </div>
            ) : null}
            {action ? <div className="mt-5">{action}</div> : null}
        </div>
    );
}
