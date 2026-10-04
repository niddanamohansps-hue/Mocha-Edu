"use client";

import { LoaderCircle } from "lucide-react";
import { cn } from "@/lib/utils";

const SIZE_CLASSES = {
    sm: "h-6 w-6",
    md: "h-8 w-8",
    lg: "h-12 w-12",
} as const;

export interface LoadingStateProps {
    /** Spinner size. Defaults to "lg" (matches the existing full-page loading look). */
    size?: keyof typeof SIZE_CLASSES;
    /** Optional visible label under the spinner. */
    message?: string;
    /** Applied to the outer container (e.g. to set a min-height for a page-level spinner). */
    className?: string;
    /** Applied to the spinner icon itself (e.g. to change its color). */
    iconClassName?: string;
}

/**
 * Centered loading spinner. Replaces the ad hoc `{isLoading && <LoaderCircle .../>}`
 * blocks repeated across feature pages with varying sizes/colors.
 */
export function LoadingState({
    size = "lg",
    message,
    className,
    iconClassName,
}: LoadingStateProps) {
    return (
        <div
            role="status"
            aria-live="polite"
            className={cn("flex flex-col items-center justify-center gap-3", className)}
        >
            <LoaderCircle
                className={cn(SIZE_CLASSES[size], "animate-spin text-sky-600", iconClassName)}
            />
            {message ? (
                <p className="text-sm text-slate-500 dark:text-slate-400">{message}</p>
            ) : (
                <span className="sr-only">Loading…</span>
            )}
        </div>
    );
}
