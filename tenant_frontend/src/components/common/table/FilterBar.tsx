"use client";

import React, { useEffect, useState, useId } from "react";
import { Search, X, RotateCcw } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface FilterBarProps {
    /** Current search text */
    searchValue?: string;
    /** Callback fired immediately on change */
    onSearchChange?: (value: string) => void;
    /** Optional debounced callback */
    onSearchDebounced?: (value: string) => void;
    /** Debounce delay in ms (defaults to 300) */
    debounceMs?: number;
    /** Search input placeholder text */
    searchPlaceholder?: string;
    /** Accessible label for search input */
    searchAriaLabel?: string;
    /** Width class for the search input (defaults to "w-full sm:w-72") */
    searchClassName?: string;
    /** Filter controls (selects, dropdowns, date pickers) */
    children?: React.ReactNode;
    /** Whether any filter is currently different from default */
    hasActiveFilters?: boolean;
    /** Callback to reset all filters and search to default */
    onReset?: () => void;
    /** Text for the reset action (defaults to "Reset") */
    resetLabel?: string;
    /** Right-aligned actions (e.g. Export, Primary Action, View switcher) */
    actions?: React.ReactNode;
    className?: string;
}

export function FilterBar({
    searchValue = "",
    onSearchChange,
    onSearchDebounced,
    debounceMs = 300,
    searchPlaceholder = "Search...",
    searchAriaLabel = "Search records",
    searchClassName = "w-full sm:w-72",
    children,
    hasActiveFilters = false,
    onReset,
    resetLabel = "Reset",
    actions,
    className,
}: FilterBarProps) {
    const inputId = useId();
    const [localQuery, setLocalQuery] = useState(searchValue);

    useEffect(() => {
        setLocalQuery(searchValue);
    }, [searchValue]);

    useEffect(() => {
        if (!onSearchDebounced) return;
        const handler = setTimeout(() => {
            onSearchDebounced(localQuery);
        }, debounceMs);
        return () => clearTimeout(handler);
    }, [localQuery, onSearchDebounced, debounceMs]);

    const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = e.target.value;
        setLocalQuery(val);
        onSearchChange?.(val);
    };

    const handleClear = () => {
        setLocalQuery("");
        onSearchChange?.("");
        onSearchDebounced?.("");
    };

    const showSearch = onSearchChange !== undefined || onSearchDebounced !== undefined;

    return (
        <div
            className={cn(
                "flex flex-col md:flex-row md:items-center justify-between gap-3 p-3 sm:p-3.5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-2xs",
                className
            )}
        >
            {/* Left: Search & Filter Controls */}
            <div className="flex flex-wrap items-center gap-2.5 flex-1 min-w-0">
                {showSearch && (
                    <div className={cn("relative shrink-0", searchClassName)}>
                        <Search
                            className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none"
                            aria-hidden="true"
                        />
                        <Input
                            id={inputId}
                            type="search"
                            role="searchbox"
                            aria-label={searchAriaLabel}
                            placeholder={searchPlaceholder}
                            value={localQuery}
                            onChange={handleInputChange}
                            onKeyDown={(e) => {
                                if (e.key === "Escape") handleClear();
                            }}
                            className="pl-8.5 pr-8 h-9 text-xs rounded-xl border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:bg-white dark:focus:bg-slate-900"
                        />
                        {localQuery && (
                            <button
                                type="button"
                                onClick={handleClear}
                                aria-label="Clear search"
                                className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded-md text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                            >
                                <X className="h-3.5 w-3.5" />
                            </button>
                        )}
                    </div>
                )}

                {/* Filter Controls Slot */}
                {children}

                {/* Reset Button */}
                {hasActiveFilters && onReset && (
                    <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={onReset}
                        className="h-9 px-2.5 text-xs text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 gap-1 rounded-xl"
                    >
                        <RotateCcw className="h-3 w-3" />
                        <span>{resetLabel}</span>
                    </Button>
                )}
            </div>

            {/* Right: Actions Slot */}
            {actions && (
                <div className="flex items-center gap-2 shrink-0 self-end md:self-auto">
                    {actions}
                </div>
            )}
        </div>
    );
}
