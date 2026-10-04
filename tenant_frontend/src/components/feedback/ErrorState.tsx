"use client";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ErrorStateProps {
    /** Primary error message shown to the user. */
    message?: string;
    /** Optional secondary line of detail. */
    description?: string;
    /** When provided, renders a retry button that calls this (e.g. react-query's `refetch`). */
    onRetry?: () => void;
    retryLabel?: string;
    className?: string;
}

/**
 * Standardized API-error block, matching the one existing precedent in the app
 * (app/dashboard/page.tsx's red bordered box) so every feature that starts
 * checking `isError` gets the same look instead of inventing its own.
 */
export function ErrorState({
    message = "Something went wrong. Please try again later.",
    description,
    onRetry,
    retryLabel = "Retry",
    className,
}: ErrorStateProps) {
    return (
        <div
            role="alert"
            className={cn(
                "rounded-3xl border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-500/5 p-10 text-center text-red-600",
                className
            )}
        >
            <p className="font-medium">{message}</p>
            {description ? <p className="text-sm mt-1 text-red-500">{description}</p> : null}
            {onRetry ? (
                <Button
                    variant="outline"
                    size="sm"
                    className="mt-4 border-red-200 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/20"
                    onClick={onRetry}
                >
                    {retryLabel}
                </Button>
            ) : null}
        </div>
    );
}
