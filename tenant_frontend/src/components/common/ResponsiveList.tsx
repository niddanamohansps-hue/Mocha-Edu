import { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface ResponsiveColumn<T> {
    /** Stable id, also used as the React key. */
    key: string;
    /** Column heading on wide screens, and the small label on a phone card. */
    header: string;
    /** What to show in the cell. */
    cell: (row: T) => ReactNode;
    /** The one column used as the card title on phones (usually a name). Falls back to the first column. */
    primary?: boolean;
    /** Leave this column out of the phone card (e.g. technical ids that a card does not need). */
    hideOnMobile?: boolean;
    /** Extra classes for the wide-screen cell (alignment, no-wrap...). */
    className?: string;
}

export interface ResponsiveLeading<T> {
    /** Heading content of the leading column on wide screens (e.g. a "select all" checkbox). */
    header: ReactNode;
    /** The leading cell for a row (e.g. a checkbox). It is shown at the left of the row and of the phone card. */
    cell: (row: T) => ReactNode;
}

interface ResponsiveListProps<T> {
    rows: T[];
    columns: ResponsiveColumn<T>[];
    /** A stable key for a row. Receives the row's position too, for data that has no id of its own. */
    rowKey: (row: T, index: number) => string;
    /** Rendered at the end of each row / card, e.g. action buttons. */
    actions?: (row: T) => ReactNode;
    /** Heading for the actions column on wide screens (hidden from screen readers when empty). */
    actionsHeader?: string;
    /** An optional first column, usually a selection checkbox. */
    leading?: ResponsiveLeading<T>;
    /** Extra classes for a row / card, e.g. to highlight the selected ones. */
    rowClassName?: (row: T) => string;
    className?: string;
}

/**
 * One list, two layouts. From the `md` breakpoint (tablet and desktop) it is a normal table; below it
 * (phones) every row becomes a card with the main value as its title and the rest as label/value
 * pairs, so nothing is cut off or needs sideways scrolling. Both are rendered and CSS chooses which
 * one is visible, so it works on the first paint and without JavaScript measuring the screen.
 */
export function ResponsiveList<T>({ rows, columns, rowKey, actions, actionsHeader = "Actions", leading, rowClassName, className }: ResponsiveListProps<T>) {
    const primary = columns.find((c) => c.primary) ?? columns[0];
    const rest = columns.filter((c) => c !== primary && !c.hideOnMobile);

    return (
        <div className={cn("rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 overflow-hidden", className)}>
            {/* Tablet and desktop */}
            <div className="hidden md:block overflow-x-auto">
                <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800/60">
                        <tr className="text-left text-xs font-semibold text-slate-500 uppercase">
                            {leading && (
                                <th scope="col" className="px-4 py-3 w-10">
                                    {leading.header}
                                </th>
                            )}
                            {columns.map((c) => (
                                <th key={c.key} scope="col" className="px-4 py-3">
                                    {c.header}
                                </th>
                            ))}
                            {actions && (
                                <th scope="col" className="px-4 py-3 text-right">
                                    {actionsHeader}
                                </th>
                            )}
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                        {rows.map((row, index) => (
                            <tr key={rowKey(row, index)} className={cn("hover:bg-slate-50/60 dark:hover:bg-slate-800/40", rowClassName?.(row))}>
                                {leading && <td className="px-4 py-3 align-top">{leading.cell(row)}</td>}
                                {columns.map((c) => (
                                    <td key={c.key} className={cn("px-4 py-3 align-top", c.className)}>
                                        {c.cell(row)}
                                    </td>
                                ))}
                                {actions && <td className="px-4 py-3 text-right align-top">{actions(row)}</td>}
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>

            {/* Phones */}
            <ul className="md:hidden divide-y divide-slate-100 dark:divide-slate-800">
                {rows.map((row, index) => (
                    <li key={rowKey(row, index)} className={cn("p-4 space-y-3", rowClassName?.(row))}>
                        <div className="flex items-start gap-3">
                            {leading && <div className="pt-0.5">{leading.cell(row)}</div>}
                            <div className="font-semibold text-slate-900 dark:text-white min-w-0">{primary.cell(row)}</div>
                        </div>
                        {rest.length > 0 && (
                            <dl className="grid grid-cols-[minmax(0,auto)_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-sm">
                                {rest.map((c) => (
                                    <div key={c.key} className="contents">
                                        <dt className="text-slate-500">{c.header}</dt>
                                        <dd className="text-slate-800 dark:text-slate-200 break-words">{c.cell(row)}</dd>
                                    </div>
                                ))}
                            </dl>
                        )}
                        {actions && <div className="flex flex-wrap gap-2">{actions(row)}</div>}
                    </li>
                ))}
            </ul>
        </div>
    );
}
