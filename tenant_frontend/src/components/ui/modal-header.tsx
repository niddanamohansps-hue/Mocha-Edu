"use client";

import React from "react";
import { X } from "lucide-react";
import { DialogClose, DialogTitle } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export interface ModalHeaderProps {
    /** Primary entity title (e.g. Student Name, "Edit Enquiry", etc.) */
    title: React.ReactNode;
    /** Optional status badge placed immediately next to title (e.g. <Badge>[Rejected]</Badge>) */
    badge?: React.ReactNode;
    /** Optional secondary subtitle or description text */
    subtitle?: React.ReactNode;
    /** Optional metadata breadcrumbs (e.g. "APP-2026-0012 · Class 4 · Academic Year") */
    metadata?: React.ReactNode;
    /** Optional leading icon before title */
    icon?: React.ReactNode;
    /** Optional actions rendered to the left of the close button */
    actions?: React.ReactNode;
    /** Explicit close callback. If omitted, uses standard Radix DialogClose */
    onClose?: () => void;
    /** Whether to show the standard 36x36px close button (defaults to true) */
    showCloseButton?: boolean;
    className?: string;
}

/**
 * Standardized Modal / Popup Header following Global MIS UI/UX Standards:
 * - Left Section: Title + Status Badge + Subtitle / Metadata
 * - Right Section: Action Buttons + Standard 36x36px Close Button
 * - Minimum height: 72px, fixed at top, independent of body scrolling
 */
export function ModalHeader({
    title,
    badge,
    subtitle,
    metadata,
    icon,
    actions,
    onClose,
    showCloseButton = true,
    className,
}: ModalHeaderProps) {
    return (
        <div
            className={cn(
                "px-6 py-4.5 border-b border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 shrink-0 flex items-start justify-between gap-4 min-h-[72px] z-20",
                className
            )}
        >
            {/* Left Section: Title, Badge, Subtitle & Metadata */}
            <div className="flex-1 min-w-0 pr-2">
                <div className="flex items-center gap-2.5 flex-wrap">
                    {icon && <div className="shrink-0 text-sky-600 dark:text-sky-400">{icon}</div>}
                    <DialogTitle asChild>
                        <h2 className="text-lg sm:text-xl font-bold text-slate-900 dark:text-white truncate tracking-tight">
                            {title}
                        </h2>
                    </DialogTitle>
                    {badge && <div className="shrink-0">{badge}</div>}
                </div>

                {(subtitle || metadata) && (
                    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 dark:text-slate-400 mt-1 font-medium">
                        {subtitle && <span>{subtitle}</span>}
                        {subtitle && metadata && <span>·</span>}
                        {metadata}
                    </div>
                )}
            </div>

            {/* Right Section: Action Buttons & Standardized 36x36px Close Button */}
            <div className="flex items-center gap-2 shrink-0 self-start pt-0.5">
                {actions}

                {showCloseButton && (
                    onClose ? (
                        <button
                            type="button"
                            onClick={onClose}
                            className="h-9 w-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 cursor-pointer"
                            aria-label="Close"
                        >
                            <X className="h-4.5 w-4.5" />
                        </button>
                    ) : (
                        <DialogClose asChild>
                            <button
                                type="button"
                                className="h-9 w-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 cursor-pointer"
                                aria-label="Close"
                            >
                                <X className="h-4.5 w-4.5" />
                            </button>
                        </DialogClose>
                    )
                )}
            </div>
        </div>
    );
}
