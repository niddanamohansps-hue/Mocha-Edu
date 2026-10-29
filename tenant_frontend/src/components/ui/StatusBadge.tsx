import React from "react";

export type BadgeVariant = "success" | "warning" | "danger" | "info" | "neutral" | "purple";

interface StatusBadgeProps {
    status?: string;
    variant?: BadgeVariant;
    label?: string;
    showDot?: boolean;
    className?: string;
}

/**
 * Universal Semantic Status Badge for EduSekai School ERP.
 * Standardizes color semantics across all 25 modules.
 */
export function StatusBadge({
    status,
    variant,
    label,
    showDot = true,
    className = "",
}: StatusBadgeProps) {
    const text = label || status || "";
    const normalized = (status || "").toLowerCase().trim();

    // Auto-detect variant based on semantic keywords if not explicitly specified
    let effectiveVariant: BadgeVariant = variant || "neutral";

    if (!variant) {
        if (
            [
                "active",
                "paid",
                "present",
                "completed",
                "approved",
                "published",
                "cleared",
                "departed",
                "admitted",
                "enrolled",
            ].includes(normalized)
        ) {
            effectiveVariant = "success";
        } else if (
            [
                "pending",
                "draft",
                "partial",
                "late",
                "in_progress",
                "in progress",
                "review",
                "buffer",
            ].includes(normalized)
        ) {
            effectiveVariant = "warning";
        } else if (
            [
                "inactive",
                "unpaid",
                "absent",
                "cancelled",
                "rejected",
                "overdue",
                "failed",
                "blocked",
                "withdrawn",
            ].includes(normalized)
        ) {
            effectiveVariant = "danger";
        } else if (
            [
                "booked",
                "scheduled",
                "issued",
                "checked_in",
                "in_transit",
                "in transit",
            ].includes(normalized)
        ) {
            effectiveVariant = "info";
        } else if (["special", "vip", "honor", "passed"].includes(normalized)) {
            effectiveVariant = "purple";
        }
    }

    const variantStyles: Record<BadgeVariant, { bg: string; dot: string }> = {
        success: {
            bg: "bg-emerald-50 text-emerald-700 border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/40",
            dot: "bg-emerald-500",
        },
        warning: {
            bg: "bg-amber-50 text-amber-700 border-amber-200/80 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/40",
            dot: "bg-amber-500",
        },
        danger: {
            bg: "bg-rose-50 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/40",
            dot: "bg-rose-500",
        },
        info: {
            bg: "bg-indigo-50 text-indigo-700 border-indigo-200/80 dark:bg-indigo-950/40 dark:text-indigo-300 dark:border-indigo-800/40",
            dot: "bg-indigo-500",
        },
        purple: {
            bg: "bg-purple-50 text-purple-700 border-purple-200/80 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800/40",
            dot: "bg-purple-500",
        },
        neutral: {
            bg: "bg-slate-100 text-slate-700 border-slate-200/80 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
            dot: "bg-slate-400",
        },
    };

    const style = variantStyles[effectiveVariant];

    return (
        <span
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold uppercase tracking-wider border shadow-2xs whitespace-nowrap ${style.bg} ${className}`}
        >
            {showDot && (
                <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${style.dot}`} />
            )}
            <span className="capitalize">{text.replace(/_/g, " ")}</span>
        </span>
    );
}

