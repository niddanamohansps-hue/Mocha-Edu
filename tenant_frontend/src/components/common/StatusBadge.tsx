import React from "react";
import { StatusBadge as UIStatusBadge, StatusBadgeProps as UIStatusBadgeProps, StatusBadgeVariant } from "@/components/ui/StatusBadge";

export type { StatusBadgeVariant };

export interface StatusBadgeProps extends UIStatusBadgeProps {
    /** Text shown inside the pill, e.g. "Active", the raw status string, or a display label. */
    label?: React.ReactNode;
    /** Color/border classes for this status. */
    className?: string;
    /** Optional icon rendered before the label. */
    icon?: React.ReactNode;
}

/**
 * Domain-agnostic status pill, re-exporting the centralized semantic StatusBadge.
 * Backward-compatible with existing callers passing custom className and icon.
 */
export function StatusBadge(props: StatusBadgeProps) {
    return <UIStatusBadge {...props} />;
}
