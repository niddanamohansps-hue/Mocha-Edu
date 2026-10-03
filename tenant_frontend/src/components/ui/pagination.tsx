"use client";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PaginationProps {
    page: number;
    pageSize: number;
    count: number;
    onPageChange: (page: number) => void;
    className?: string;
}

/**
 * Shared list-pagination control for any screen backed by DRF's standard
 * {count, next, previous, results} envelope. Pass the raw `count`/`page`/
 * `pageSize` rather than `next`/`previous` booleans so this component can
 * compute total pages and render page numbers itself - the one reusable
 * pagination UI for the app (see the pagination-audit task: no other
 * pagination component existed before this).
 */
export function Pagination({ page, pageSize, count, onPageChange, className }: PaginationProps) {
    const totalPages = Math.max(1, Math.ceil(count / pageSize));

    if (count === 0) {
        return (
            <div className={cn("flex items-center justify-between px-2 py-3 text-sm text-slate-500 dark:text-slate-400", className)}>
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
        <div className={cn("flex flex-col sm:flex-row items-center justify-between gap-3 px-2 py-3", className)}>
            <p className="text-sm text-slate-500 dark:text-slate-400">
                Showing <span className="font-medium text-slate-700 dark:text-slate-300">{startRow}</span>
                {"–"}
                <span className="font-medium text-slate-700 dark:text-slate-300">{endRow}</span> of{" "}
                <span className="font-medium text-slate-700 dark:text-slate-300">{count}</span>
            </p>

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
                        <span key={`ellipsis-${idx}`} className="px-2 text-sm text-slate-400">
                            {"…"}
                        </span>
                    ) : (
                        <Button
                            key={entry}
                            variant={entry === page ? "default" : "outline"}
                            size="icon-sm"
                            onClick={() => onPageChange(entry)}
                            aria-current={entry === page ? "page" : undefined}
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
