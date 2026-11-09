import React, { useEffect } from "react";
import { X } from "lucide-react";

interface SlideOverDrawerProps {
    isOpen: boolean;
    onClose: () => void;
    title: string;
    subtitle?: string;
    children: React.ReactNode;
    footer?: React.ReactNode;
    widthClass?: string;
}

/**
 * Modern Slide-Over Drawer (Sheet) Component.
 * Slides smoothly in from the right edge, maintaining background context.
 */
export function SlideOverDrawer({
    isOpen,
    onClose,
    title,
    subtitle,
    children,
    footer,
    widthClass = "max-w-xl",
}: SlideOverDrawerProps) {
    // Close on Escape key press
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === "Escape" && isOpen) {
                onClose();
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, [isOpen, onClose]);

    // Prevent background scrolling when open
    useEffect(() => {
        if (isOpen) {
            document.body.style.overflow = "hidden";
        } else {
            document.body.style.overflow = "";
        }
        return () => {
            document.body.style.overflow = "";
        };
    }, [isOpen]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-hidden">
            {/* Backdrop */}
            <div
                onClick={onClose}
                className="fixed inset-0 bg-slate-950/40 backdrop-blur-xs transition-opacity duration-300"
                aria-hidden="true"
            />

            <div className="fixed inset-y-0 right-0 flex max-w-full pl-10">
                <div
                    className={`w-screen ${widthClass} bg-white dark:bg-slate-900 border-l border-slate-200 dark:border-slate-800 shadow-2xl flex flex-col justify-between transform transition-transform duration-300 ease-in-out`}
                >
                    {/* Header */}
                    <div className="p-5 border-b border-slate-100 dark:border-slate-800 flex items-start justify-between bg-slate-50/50 dark:bg-slate-800/40">
                        <div>
                            <h2 className="text-base font-bold text-slate-900 dark:text-white">
                                {title}
                            </h2>
                            {subtitle && (
                                <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                    {subtitle}
                                </p>
                            )}
                        </div>
                        <button
                            type="button"
                            onClick={onClose}
                            className="h-9 w-9 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 cursor-pointer shrink-0"
                            aria-label="Close drawer"
                        >
                            <X className="h-4.5 w-4.5" />
                        </button>
                    </div>

                    {/* Scrollable Body Content */}
                    <div className="flex-1 overflow-y-auto p-5 space-y-4">
                        {children}
                    </div>

                    {/* Sticky Footer */}
                    {footer && (
                        <div className="p-4 border-t border-slate-100 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-800/40 flex justify-end gap-2">
                            {footer}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

