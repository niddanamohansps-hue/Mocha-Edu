"use client";

import { LoaderCircle } from "lucide-react";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";

export interface ConfirmationDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title?: React.ReactNode;
    description: React.ReactNode;
    confirmLabel?: string;
    cancelLabel?: string;
    onConfirm: () => void;
    /** Disables both buttons and shows a spinner on the confirm button. */
    isLoading?: boolean;
    /** "destructive" (default) applies the red confirm-button styling used by every
     * delete confirmation in the app today; "default" leaves the confirm button unstyled. */
    variant?: "destructive" | "default";
    /** Optional icon rendered above the title (e.g. the red circular Trash2 icon used on the roles page). */
    icon?: React.ReactNode;
    /** Passed to AlertDialogContent, to reproduce a feature's existing content sizing/rounding. */
    contentClassName?: string;
    /** Passed to AlertDialogFooter. */
    footerClassName?: string;
    /** Additional classes merged onto the confirm button, on top of the variant's base classes. */
    confirmClassName?: string;
    cancelClassName?: string;
}

/**
 * Reusable "are you sure?" dialog built on the existing shadcn AlertDialog
 * primitives. Replaces the ~9 independently hand-rolled delete-confirmation
 * dialogs found across students, staff, institution/roles, and the academics
 * tabs. Domain-agnostic by design: it knows nothing about what is being
 * deleted - all copy/labels/styling are supplied by the caller.
 */
export function ConfirmationDialog({
    open,
    onOpenChange,
    title = "Are you sure?",
    description,
    confirmLabel = "Confirm",
    cancelLabel = "Cancel",
    onConfirm,
    isLoading = false,
    variant = "destructive",
    icon,
    contentClassName,
    footerClassName,
    confirmClassName,
    cancelClassName,
}: ConfirmationDialogProps) {
    return (
        <AlertDialog open={open} onOpenChange={onOpenChange}>
            <AlertDialogContent className={contentClassName}>
                <AlertDialogHeader>
                    {icon}
                    <AlertDialogTitle>{title}</AlertDialogTitle>
                    <AlertDialogDescription>{description}</AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter className={footerClassName}>
                    <AlertDialogCancel disabled={isLoading} className={cancelClassName}>
                        {cancelLabel}
                    </AlertDialogCancel>
                    <AlertDialogAction
                        onClick={onConfirm}
                        disabled={isLoading}
                        className={cn(
                            variant === "destructive" && "bg-red-600 hover:bg-red-700 text-white",
                            confirmClassName
                        )}
                    >
                        {isLoading ? <LoaderCircle className="h-4 w-4 animate-spin" /> : null}
                        {confirmLabel}
                    </AlertDialogAction>
                </AlertDialogFooter>
            </AlertDialogContent>
        </AlertDialog>
    );
}
