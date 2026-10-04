import { cn } from "@/lib/utils";

export interface StatusBadgeProps {
    /** Text shown inside the pill, e.g. "Active", the raw status string, or a display label. */
    label: React.ReactNode;
    /** Color/border classes for this status - fully caller-supplied, since different
     * status systems in this app (fee status, payment status, submission status,
     * account-access status) are semantically different and must not share one
     * hardcoded color mapping. See each feature's own status->class logic. */
    className?: string;
    /** Optional icon rendered before the label. Include its own spacing (e.g. "mr-1" or "h-3 w-3 mr-1"). */
    icon?: React.ReactNode;
}

/**
 * Domain-agnostic status pill. Centralizes the repeated
 * `text-xs font-semibold px-2 py-1 rounded-full` shape that was previously
 * hand-rolled per feature (fees, staff, course-content submissions, ...) -
 * it does not know or decide what colors a given status means. Callers keep
 * owning their own status->color mapping and pass it in via `className`.
 */
export function StatusBadge({ label, className, icon }: StatusBadgeProps) {
    return (
        <span
            className={cn(
                "inline-flex items-center rounded-full px-2 py-1 text-xs font-semibold whitespace-nowrap",
                className
            )}
        >
            {icon}
            {label}
        </span>
    );
}
