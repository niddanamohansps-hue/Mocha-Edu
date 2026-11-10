import { cn } from "@/lib/utils";

export interface TableShellProps {
    /** The actual <Table>...</Table> markup - feature-owned, wrapped here in the shared horizontal-scroll container. */
    children: React.ReactNode;
    /** Optional top header section (e.g. title, tab filters, or quick actions). */
    header?: React.ReactNode;
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
export function TableShell({ children, header, footer, className }: TableShellProps) {
    return (
        <div
            className={cn(
                "rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden shadow-2xs",
                className
            )}
        >
            {header && (
                <div className="border-b border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50">
                    {header}
                </div>
            )}
            <div className="overflow-x-auto">{children}</div>
            {footer}
        </div>
    );
}
