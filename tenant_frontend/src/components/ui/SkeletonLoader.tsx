import React from "react";

/**
 * Animated Table Skeleton Loader.
 * Eliminates spinner flickers and layout shift during data fetching.
 */
export function TableSkeleton({
    rows = 5,
    columns = 6,
    className = "",
}: {
    rows?: number;
    columns?: number;
    className?: string;
}) {
    return (
        <div className={`w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden shadow-2xs ${className}`}>
            {/* Header skeleton */}
            <div className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800 px-4 py-3 flex gap-4">
                {Array.from({ length: columns }).map((_, i) => (
                    <div
                        key={i}
                        className="h-3.5 bg-slate-200 dark:bg-slate-700 rounded animate-pulse"
                        style={{ width: `${Math.max(12, Math.min(25, 100 / columns))}%` }}
                    />
                ))}
            </div>

            {/* Row skeletons */}
            <div className="divide-y divide-slate-100 dark:divide-slate-800">
                {Array.from({ length: rows }).map((_, r) => (
                    <div key={r} className="px-4 py-3.5 flex items-center gap-4">
                        {Array.from({ length: columns }).map((_, c) => (
                            <div
                                key={c}
                                className="h-3 bg-slate-100 dark:bg-slate-800 rounded animate-pulse"
                                style={{
                                    width: `${Math.max(10, Math.min(22, 90 / columns)) + ((r + c) % 3) * 3}%`,
                                }}
                            />
                        ))}
                    </div>
                ))}
            </div>
        </div>
    );
}

/**
 * Animated Grid Cards Skeleton Loader.
 */
export function CardSkeleton({
    count = 4,
    className = "",
}: {
    count?: number;
    className?: string;
}) {
    return (
        <div className={`grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 ${className}`}>
            {Array.from({ length: count }).map((_, i) => (
                <div
                    key={i}
                    className="p-5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-3 shadow-2xs"
                >
                    <div className="flex justify-between items-start">
                        <div className="h-4 w-32 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                        <div className="h-4 w-16 bg-slate-100 dark:bg-slate-800 rounded-full animate-pulse" />
                    </div>
                    <div className="h-3 w-48 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                    <div className="pt-2 space-y-1.5">
                        <div className="h-2.5 w-full bg-slate-50 dark:bg-slate-800/60 rounded animate-pulse" />
                        <div className="h-2.5 w-3/4 bg-slate-50 dark:bg-slate-800/60 rounded animate-pulse" />
                    </div>
                </div>
            ))}
        </div>
    );
}

/**
 * Metric Summary Cards Skeleton.
 */
export function MetricSkeleton({
    count = 4,
    className = "",
}: {
    count?: number;
    className?: string;
}) {
    return (
        <div className={`grid grid-cols-2 lg:grid-cols-4 gap-4 ${className}`}>
            {Array.from({ length: count }).map((_, i) => (
                <div
                    key={i}
                    className="p-4 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl space-y-2 shadow-2xs"
                >
                    <div className="h-3 w-20 bg-slate-200 dark:bg-slate-700 rounded animate-pulse" />
                    <div className="h-7 w-14 bg-slate-300 dark:bg-slate-600 rounded animate-pulse" />
                    <div className="h-2.5 w-28 bg-slate-100 dark:bg-slate-800 rounded animate-pulse" />
                </div>
            ))}
        </div>
    );
}
