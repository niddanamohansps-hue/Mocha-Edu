"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PaginationProps {
    page: number;
    pageSize: number;
    count: number;
    onPageChange: (page: number) => void;
    /** Optional list of selectable page sizes, e.g. [10, 20, 50, 100] */
    pageSizeOptions?: number[];
    /** Callback fired when page size is changed */
    onPageSizeChange?: (pageSize: number) => void;
    className?: string;
}

/**
 * Shared list-pagination control for any screen backed by DRF's standard
 * {count, next, previous, results} envelope. Pass the raw `count`/`page`/
 * `pageSize` rather than `next`/`previous` booleans so this component can
 * compute total pages and render page numbers itself - the one reusable
 * pagination UI for the app.
 */
export function Pagination({
    page,
    pageSize,
    count,
    onPageChange,
    pageSizeOptions,
    onPageSizeChange,
    className,
}: PaginationProps) {
    const totalPages = Math.max(1, Math.ceil(count / pageSize));

    if (count === 0) {
        return (
            <div className={cn("flex items-center justify-between px-3 py-3 text-xs text-slate-500 dark:text-slate-400", className)}>
                <span>No results.</span>
            </div>
        );
    }

    const startRow = (page - 1) * pageSize + 1;
    const endRow = Math.min(page * pageSize, count);

    // Compact page-number list: first, last, current ±1, "..." for gaps -
    // never render hundreds of page buttons for a large dataset.
    const pageNumbers: Array<number | "ellipsis"> = [];
    const addPage = (p: number) => {
        if (!pageNumbers.includes(p)) pageNumbers.push(p);
    };
    addPage(1);
    if (page > 3) pageNumbers.push("ellipsis");
    for (let p = Math.max(2, page - 1); p <= Math.min(totalPages - 1, page + 1); p++) addPage(p);
    if (page < totalPages - 2) pageNumbers.push("ellipsis");
    if (totalPages > 1) addPage(totalPages);

    return (
        <div className={cn("flex flex-col sm:flex-row items-center justify-between gap-3 px-3 py-2.5", className)}>
            <div className="flex items-center gap-3">
                <p className="text-xs text-slate-500 dark:text-slate-400">
                    Showing <span className="font-semibold text-slate-700 dark:text-slate-200">{startRow}</span>
                    {"–"}
                    <span className="font-semibold text-slate-700 dark:text-slate-200">{endRow}</span> of{" "}
                    <span className="font-semibold text-slate-700 dark:text-slate-200">{count}</span>
                </p>

                {pageSizeOptions && onPageSizeChange && (
                    <div className="flex items-center gap-1.5 text-xs text-slate-500">
                        <span className="hidden sm:inline">Rows:</span>
                        <select
                            value={pageSize}
                            onChange={(e) => onPageSizeChange(Number(e.target.value))}
                            className="h-7 px-1.5 py-0.5 text-xs font-medium rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 focus:outline-hidden focus:ring-1 focus:ring-sky-500 cursor-pointer"
                            aria-label="Rows per page"
                        >
                            {pageSizeOptions.map((opt) => (
                                <option key={opt} value={opt}>
                                    {opt}
                                </option>
                            ))}
                        </select>
                    </div>
                )}
            </div>

            <div className="flex items-center gap-1">
                <Button
                    variant="outline"
                    size="icon-sm"
                    disabled={page <= 1}
                    onClick={() => onPageChange(page - 1)}
                    aria-label="Previous page"
                >
                    <ChevronLeft className="h-4 w-4" />
                </Button>

                {pageNumbers.map((entry, idx) =>
                    entry === "ellipsis" ? (
                        <span key={`ellipsis-${idx}`} className="px-1.5 text-xs text-slate-400">
                            {"…"}
                        </span>
                    ) : (
                        <Button
                            key={entry}
                            variant={entry === page ? "default" : "outline"}
                            size="icon-sm"
                            onClick={() => onPageChange(entry)}
                            aria-current={entry === page ? "page" : undefined}
                            className="text-xs font-medium"
                        >
                            {entry}
                        </Button>
                    )
                )}

                <Button
                    variant="outline"
                    size="icon-sm"
                    disabled={page >= totalPages}
                    onClick={() => onPageChange(page + 1)}
                    aria-label="Next page"
                >
                    <ChevronRight className="h-4 w-4" />
                </Button>
            </div>
        </div>
    );
}
