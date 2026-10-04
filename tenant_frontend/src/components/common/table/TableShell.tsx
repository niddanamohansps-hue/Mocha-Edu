import { cn } from "@/lib/utils";

export interface TableShellProps {
    /** The actual <Table>...</Table> markup - feature-owned, wrapped here in the shared horizontal-scroll container. */
    children: React.ReactNode;
    /** Rendered below the scroll area but still inside the outer card, e.g. a feature-owned <Pagination />. */
    footer?: React.ReactNode;
    className?: string;
}

/**
 * Shared outer presentation for a list/table card: rounded border, overflow
 * clipping, and a horizontal-scroll wrapper around the table itself.
 * Replaces the identical wrapper markup previously duplicated in every
 * table screen. Knows nothing about rows, columns, data, pagination state,
 * or permissions - it only arranges whatever it's given.
 */
export function TableShell({ children, footer, className }: TableShellProps) {
    return (
        <div
            className={cn(
                "rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-sm",
                className
            )}
        >
            <div className="overflow-x-auto">{children}</div>
            {footer}
        </div>
    );
}
