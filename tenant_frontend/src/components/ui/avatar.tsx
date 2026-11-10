"use client";

import React, { useState } from "react";
import { cn } from "@/lib/utils";
import { getAvatarStyle, getInitials, AVATAR_PALETTES } from "@/lib/avatar";

export { getAvatarStyle, getInitials, AVATAR_PALETTES };

export type AvatarSize = "xs" | "sm" | "md" | "lg" | "xl" | "2xl" | "3xl" | "card";
export type AvatarShape = "circle" | "rounded" | "square";
export type AvatarStatus = "online" | "offline" | "busy" | "away" | "active" | "inactive";

export interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
    src?: string | null;
    alt?: string;
    name?: string | null;
    initials?: string;
    size?: AvatarSize;
    shape?: AvatarShape;
    status?: AvatarStatus | null;
    border?: boolean;
    className?: string;
}

const SIZE_STYLES: Record<AvatarSize, { container: string; text: string; dot: string }> = {
    xs: { container: "h-6 w-6", text: "text-[10px]", dot: "h-1.5 w-1.5" },
    sm: { container: "h-8 w-8", text: "text-xs", dot: "h-2 w-2" },
    md: { container: "h-9 w-9", text: "text-xs font-bold", dot: "h-2.5 w-2.5" },
    lg: { container: "h-10 w-10", text: "text-sm font-bold", dot: "h-2.5 w-2.5" },
    xl: { container: "h-12 w-12", text: "text-base font-bold", dot: "h-3 w-3" },
    "2xl": { container: "h-16 w-16", text: "text-xl font-bold", dot: "h-3.5 w-3.5" },
    "3xl": { container: "h-20 w-20", text: "text-2xl font-bold", dot: "h-4 w-4" },
    card: { container: "h-24 w-24", text: "text-3xl font-black", dot: "h-4 w-4" },
};

const SHAPE_STYLES: Record<AvatarShape, string> = {
    circle: "rounded-full",
    rounded: "rounded-2xl",
    square: "rounded-md",
};

const STATUS_STYLES: Record<AvatarStatus, string> = {
    online: "bg-emerald-500",
    active: "bg-emerald-500",
    away: "bg-amber-500",
    offline: "bg-slate-400",
    busy: "bg-rose-500",
    inactive: "bg-rose-500",
};

export function Avatar({
    src,
    alt,
    name,
    initials: explicitInitials,
    size = "md",
    shape = "circle",
    status,
    border = true,
    className,
    children,
    ...props
}: AvatarProps) {
    const [imageError, setImageError] = useState(false);

    // If children are passed (composable shadcn pattern), render container with children
    if (children) {
        return (
            <div
                className={cn(
                    "relative inline-flex items-center justify-center shrink-0 overflow-hidden select-none",
                    SIZE_STYLES[size].container,
                    SHAPE_STYLES[shape],
                    className
                )}
                {...props}
            >
                {children}
            </div>
        );
    }

    const effectiveInitials = explicitInitials || getInitials(name);
    const palette = getAvatarStyle(name);
    const sizeConfig = SIZE_STYLES[size];
    const shapeClass = shape === "circle" ? "rounded-full" : (shape === "rounded" ? "rounded-2xl" : "rounded-md");
    const hasValidImage = Boolean(src && !imageError);

    return (
        <div
            className={cn(
                "relative inline-flex items-center justify-center shrink-0 select-none overflow-hidden font-bold transition-transform",
                sizeConfig.container,
                shapeClass,
                hasValidImage
                    ? "bg-slate-100 dark:bg-slate-800"
                    : cn(
                        palette.bg,
                        palette.text,
                        border && (size === "card" ? `border-3 ${palette.border}` : `border ${palette.border}`)
                    ),
                className
            )}
            {...props}
        >
            {hasValidImage ? (
                <img
                    src={src!}
                    alt={alt || name || "Avatar"}
                    onError={() => setImageError(true)}
                    className="h-full w-full object-cover"
                />
            ) : (
                <span className={cn(sizeConfig.text, "leading-none tracking-wider")}>
                    {effectiveInitials}
                </span>
            )}

            {status && (
                <span
                    className={cn(
                        "absolute bottom-0 right-0 rounded-full ring-2 ring-white dark:ring-slate-900",
                        sizeConfig.dot,
                        STATUS_STYLES[status]
                    )}
                    aria-label={`Status: ${status}`}
                />
            )}
        </div>
    );
}

export function AvatarImage({
    src,
    alt = "Avatar",
    className,
    ...props
}: React.ImgHTMLAttributes<HTMLImageElement>) {
    const [hasError, setHasError] = useState(false);
    if (!src || hasError) return null;

    return (
        <img
            src={src}
            alt={alt}
            onError={() => setHasError(true)}
            className={cn("h-full w-full object-cover", className)}
            {...props}
        />
    );
}

export function AvatarFallback({
    className,
    children,
    ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
    return (
        <span
            className={cn(
                "flex h-full w-full items-center justify-center font-bold text-xs bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200",
                className
            )}
            {...props}
        >
            {children}
        </span>
    );
}
