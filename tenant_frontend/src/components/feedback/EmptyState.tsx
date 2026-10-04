import { cn } from "@/lib/utils";

export interface EmptyStateProps {
    /** Icon element, e.g. <GraduationCap className="h-12 w-12 mb-2 opacity-20" />. Optional. */
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
    className?: string;
}

/**
 * Standardized "no data" block. Replaces the repeated
 * `flex flex-col items-center justify-center text-slate-400 py-10` + icon + message
 * markup copy-pasted across feature tables.
 */
export function EmptyState({ icon, title, titleAs = "p", description, action, className }: EmptyStateProps) {
    const TitleTag = titleAs;
    return (
        <div
            className={cn(
                "flex flex-col items-center justify-center text-slate-400 py-10",
                className
            )}
        >
            {icon}
            <TitleTag className="font-medium">{title}</TitleTag>
            {description ? <p className="text-sm mt-1">{description}</p> : null}
            {action ? <div className="mt-4">{action}</div> : null}
        </div>
    );
}
