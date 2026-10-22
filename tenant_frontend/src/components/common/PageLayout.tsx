import { FormEvent, ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * The top of a page: what it is, a one-line "what is this for", and the main buttons.
 * On a phone the buttons go under the title and fill the width so they are easy to tap.
 */
export function PageHeader({ title, description, actions }: { title: string; description?: string; actions?: ReactNode }) {
    return (
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 sm:gap-4">
            <div className="min-w-0">
                <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white">{title}</h1>
                {description && <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-2xl">{description}</p>}
            </div>
            {actions && (
                <div className="flex flex-col sm:flex-row sm:flex-wrap gap-2 [&>*]:w-full sm:[&>*]:w-auto">{actions}</div>
            )}
        </div>
    );
}

/**
 * A search / filter row. On a phone each control takes the full width, one under the other; from
 * the `sm` breakpoint they sit side by side and wrap. Put inputs, selects and a submit button inside.
 */
export function FilterBar({
    onSubmit,
    children,
    className,
}: {
    onSubmit?: (event: FormEvent<HTMLFormElement>) => void;
    children: ReactNode;
    className?: string;
}) {
    return (
        <form
            role="search"
            onSubmit={(event) => {
                event.preventDefault();
                onSubmit?.(event);
            }}
            className={cn(
                "grid grid-cols-1 gap-3 sm:flex sm:flex-wrap sm:items-center [&_select]:w-full sm:[&_select]:w-auto [&_input[type=text]]:w-full sm:[&_input[type=text]]:w-64",
                className
            )}
        >
            {children}
        </form>
    );
}

/** What to show when a list is empty: say what the page is for and what to do next. */
export function EmptyHint({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
    return (
        <div className="rounded-2xl border border-dashed border-slate-300 dark:border-slate-700 px-6 py-12 text-center space-y-3">
            <p className="font-semibold text-slate-700 dark:text-slate-200">{title}</p>
            {hint && <p className="text-sm text-slate-500 max-w-md mx-auto">{hint}</p>}
            {action && <div className="pt-1 flex justify-center">{action}</div>}
        </div>
    );
}
