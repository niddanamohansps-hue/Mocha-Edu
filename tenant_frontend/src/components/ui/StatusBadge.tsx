import React from "react";
import { cn } from "@/lib/utils";

export type StatusBadgeVariant =
    | "success"
    | "active"
    | "warning"
    | "pending"
    | "danger"
    | "error"
    | "destructive"
    | "inactive"
    | "info"
    | "information"
    | "neutral"
    | "purple";

export interface StatusBadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
    /** The status string used for display or semantic auto-detection (e.g. "active", "paid", "pending"). */
    status?: string;
    /** Semantic variant. Overrides auto-detection. */
    variant?: StatusBadgeVariant;
    /** Custom label or ReactNode. If omitted, uses status or children. */
    label?: React.ReactNode;
    /** Whether to display a pulsing/status indicator dot. Defaults to true unless an icon is provided. */
    showDot?: boolean;
    /** Optional leading icon. */
    icon?: React.ReactNode;
    /** Additional CSS classes. Can override variant background and text colors. */
    className?: string;
    /** Children can be used as the badge label. */
    children?: React.ReactNode;
}

const VARIANT_STYLES: Record<string, { bg: string; dot: string }> = {
    success: {
        bg: "bg-emerald-50 text-emerald-700 border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/40",
        dot: "bg-emerald-500",
    },
    active: {
        bg: "bg-emerald-50 text-emerald-700 border-emerald-200/80 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800/40",
        dot: "bg-emerald-500",
    },
    warning: {
        bg: "bg-amber-50 text-amber-700 border-amber-200/80 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/40",
        dot: "bg-amber-500",
    },
    pending: {
        bg: "bg-amber-50 text-amber-700 border-amber-200/80 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800/40",
        dot: "bg-amber-500",
    },
    danger: {
        bg: "bg-rose-50 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/40",
        dot: "bg-rose-500",
    },
    error: {
        bg: "bg-rose-50 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/40",
        dot: "bg-rose-500",
    },
    destructive: {
        bg: "bg-rose-50 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/40",
        dot: "bg-rose-500",
    },
    inactive: {
        bg: "bg-rose-50 text-rose-700 border-rose-200/80 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800/40",
        dot: "bg-rose-500",
    },
    info: {
        bg: "bg-sky-50 text-sky-700 border-sky-200/80 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-800/40",
        dot: "bg-sky-500",
    },
    information: {
        bg: "bg-sky-50 text-sky-700 border-sky-200/80 dark:bg-sky-950/40 dark:text-sky-300 dark:border-sky-800/40",
        dot: "bg-sky-500",
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

/**
 * Universal Semantic Status Badge for EduSekai School ERP.
 * Standardizes status semantics across all modules while supporting custom icons and overrides.
 */
export function StatusBadge({
    status,
    variant,
    label,
    showDot,
    icon,
    className,
    children,
    ...props
}: StatusBadgeProps) {
    const displayContent = label ?? children ?? status ?? "";
    const normalized = (typeof status === "string" ? status : typeof displayContent === "string" ? displayContent : "")
        .toLowerCase()
        .trim();

    // Auto-detect variant based on semantic keywords if not explicitly specified
    let effectiveVariant: string = variant || "neutral";

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
                "verified",
                "resolved",
                "success",
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
                "under_review",
                "processing",
                "warning",
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
                "suspended",
                "error",
                "danger",
                "destructive",
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
                "new",
                "info",
                "information",
            ].includes(normalized)
        ) {
            effectiveVariant = "info";
        } else if (["special", "vip", "honor", "passed", "promoted"].includes(normalized)) {
            effectiveVariant = "purple";
        }
    }

    const style = VARIANT_STYLES[effectiveVariant] || VARIANT_STYLES.neutral;
    const shouldShowDot = showDot !== undefined ? showDot : !icon;

    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold tracking-wide border shadow-2xs whitespace-nowrap transition-colors",
                style.bg,
                className
            )}
            {...props}
        >
            {icon && <span className="shrink-0">{icon}</span>}
            {shouldShowDot && (
                <span className={cn("h-1.5 w-1.5 rounded-full shrink-0", style.dot)} />
            )}
            <span className="capitalize">
                {typeof displayContent === "string" ? displayContent.replace(/_/g, " ") : displayContent}
            </span>
        </span>
    );
}

// Re-export type
export type BadgeVariant = StatusBadgeVariant;
