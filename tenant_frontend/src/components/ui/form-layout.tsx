"use client";

import React from "react";
import { cn } from "@/lib/utils";
import { Label } from "@/components/ui/label";

/**
 * FormSection: Groups related fields with standardized section spacing (28-32px),
 * an uppercase header, optional subtitle, and subtle separator line.
 */
export function FormSection({
    title,
    description,
    action,
    children,
    className,
}: {
    title?: string;
    description?: string;
    action?: React.ReactNode;
    children: React.ReactNode;
    className?: string;
}) {
    return (
        <div className={cn("space-y-4 mb-7 last:mb-0", className)}>
            {title && (
                <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-slate-800">
                    <div>
                        <h4 className="text-[11.5px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                            {title}
                        </h4>
                        {description && (
                            <p className="text-xs text-slate-400 mt-0.5">{description}</p>
                        )}
                    </div>
                    {action && <div>{action}</div>}
                </div>
            )}
            <div className="space-y-4">{children}</div>
        </div>
    );
}

/**
 * FormGrid: Standard 2-column responsive layout.
 * Desktop: 2 equal-width columns (gap-x-5 gap-y-4.5)
 * Mobile: 1 column
 */
export function FormGrid({
    children,
    className,
}: {
    children: React.ReactNode;
    className?: string;
}) {
    return (
        <div className={cn("grid grid-cols-1 md:grid-cols-2 gap-x-5 gap-y-4.5 items-start", className)}>
            {children}
        </div>
    );
}

/**
 * FormGrid3: Standard 3-column responsive layout for compact triplets.
 * Desktop: 3 equal-width columns (gap-x-4 gap-y-4.5)
 * Mobile: 1 column
 */
export function FormGrid3({
    children,
    className,
}: {
    children: React.ReactNode;
    className?: string;
}) {
    return (
        <div className={cn("grid grid-cols-1 sm:grid-cols-3 gap-x-4 gap-y-4.5 items-start", className)}>
            {children}
        </div>
    );
}

/**
 * FormFieldWrapper: Standard field container with 6-8px label spacing,
 * uniform required asterisk indicator, helper text, and accessible inline error.
 */
export function FormFieldWrapper({
    label,
    htmlFor,
    required = false,
    error,
    helpText,
    children,
    className,
    colSpan,
}: {
    label?: React.ReactNode;
    htmlFor?: string;
    required?: boolean;
    error?: string;
    helpText?: string;
    children: React.ReactNode;
    className?: string;
    colSpan?: "full" | 1 | 2;
}) {
    return (
        <div
            className={cn(
                "space-y-1.5 min-w-0 w-full",
                colSpan === "full" && "col-span-full",
                colSpan === 2 && "md:col-span-2",
                className
            )}
        >
            {label && (
                <div className="flex items-center justify-between gap-2">
                    <Label htmlFor={htmlFor} required={required}>
                        {label}
                    </Label>
                    {helpText && !error && (
                        <span className="text-[11px] text-slate-400 font-normal">{helpText}</span>
                    )}
                </div>
            )}
            <div className="relative w-full">{children}</div>
            {error && (
                <p className="text-xs text-rose-500 font-medium mt-1 animate-in fade-in duration-150">
                    {error}
                </p>
            )}
        </div>
    );
}
