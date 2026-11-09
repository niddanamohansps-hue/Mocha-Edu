"use client";

import { LucideIcon, ChevronRight, Star } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";
import { FavoriteItem } from "@/hooks/useFavorites";

export interface SidebarItemType {
    label: string;
    icon?: LucideIcon;
    href?: string;
    children?: SidebarItemType[];
    group?: string;
}

interface SidebarItemProps {
    item: SidebarItemType;
    isCollapsed: boolean;
    level?: number;
    parentModule?: string;
    isOpen?: boolean;
    onToggle?: () => void;
    onNavigate?: () => void;
    isFavorite?: (href: string) => boolean;
    onToggleFavorite?: (item: FavoriteItem) => void;
    onExpandSidebar?: () => void;
}

export function SidebarItem({
    item,
    isCollapsed,
    level = 0,
    parentModule,
    isOpen: controlledIsOpen,
    onToggle,
    onNavigate,
    isFavorite,
    onToggleFavorite,
    onExpandSidebar,
}: SidebarItemProps) {
    const pathname = usePathname();
    const router = useRouter();

    // Local toggle for nested sub-groups (level >= 1, e.g. Examinations sub-clusters)
    const [subOpen, setSubOpen] = useState(false);

    const hasChildren = Boolean(item.children && item.children.length > 0);
    const isLeaf = Boolean(item.href && !hasChildren);
    const isActive = item.href ? pathname === item.href : false;

    // Check if any descendant is active
    const isChildActive = Boolean(
        item.children?.some(child =>
            child.href === pathname ||
            child.children?.some(subChild => subChild.href === pathname)
        )
    );

    // Auto-open nested sub-groups (level >= 1) if an active child is inside
    useEffect(() => {
        if (isChildActive && level > 0) {
            setSubOpen(true);
        }
    }, [isChildActive, level]);

    const isTopLevel = level === 0;
    const isSubGroup = level === 1 && hasChildren;
    const isDeepLeaf = level >= 2;
    const isLevel1Leaf = level === 1 && !hasChildren;

    // Use controlled isOpen for top-level modules (single accordion); local subOpen for level >= 1
    const isOpen = isTopLevel ? Boolean(controlledIsOpen) : subOpen;

    const handleClick = () => {
        if (isCollapsed) {
            if (hasChildren) {
                // Expanding sidebar opens this module
                onExpandSidebar?.();
                onToggle?.();
            } else if (item.href) {
                router.push(item.href);
                onNavigate?.();
            }
            return;
        }

        if (isTopLevel) {
            if (hasChildren) {
                onToggle?.();
            } else if (item.href) {
                router.push(item.href);
                onNavigate?.();
            }
        } else if (isSubGroup) {
            setSubOpen(!subOpen);
        } else if (item.href) {
            router.push(item.href);
            onNavigate?.();
        }
    };

    const isFav = isLeaf && item.href && isFavorite ? isFavorite(item.href) : false;

    const handleFavoriteClick = (e: React.MouseEvent) => {
        e.stopPropagation();
        if (item.href && onToggleFavorite) {
            onToggleFavorite({
                label: item.label,
                href: item.href,
                parent: parentModule || item.group,
            });
        }
    };

    // Collapsed Mode Item with Tooltip
    if (isCollapsed) {
        return (
            <Tooltip delayDuration={100}>
                <TooltipTrigger asChild>
                    <button
                        type="button"
                        onClick={handleClick}
                        className={cn(
                            "w-10 h-10 mx-auto rounded-lg flex items-center justify-center transition-all duration-150 relative group cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
                            isActive || (hasChildren && isChildActive)
                                ? "bg-sky-50 dark:bg-sky-500/15 text-sky-600 dark:text-sky-400 font-semibold shadow-2xs"
                                : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100/80 dark:hover:bg-slate-800/80"
                        )}
                        aria-label={item.label}
                    >
                        {(isActive || (hasChildren && isChildActive)) && (
                            <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-md bg-sky-600 dark:bg-sky-400" />
                        )}
                        {item.icon ? (
                            <item.icon className="h-5 w-5 shrink-0 transition-transform group-hover:scale-105" />
                        ) : (
                            <span className="text-xs font-bold uppercase">{item.label.slice(0, 2)}</span>
                        )}
                    </button>
                </TooltipTrigger>
                <TooltipContent side="right" sideOffset={12} className="flex flex-col gap-0.5 py-1.5 px-2.5">
                    <span className="font-semibold text-xs text-white">{item.label}</span>
                    {hasChildren && (
                        <span className="text-[10px] text-slate-300">
                            {item.children?.length} {item.children?.length === 1 ? "page" : "pages"}
                        </span>
                    )}
                </TooltipContent>
            </Tooltip>
        );
    }

    // Expanded Mode
    return (
        <div className="w-full">
            <button
                type="button"
                onClick={handleClick}
                className={cn(
                    "w-full flex items-center transition-all duration-150 ease-out group relative cursor-pointer select-none text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
                    // Top level item
                    isTopLevel && "gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium",
                    // Sub-group cluster header (e.g. Examinations -> Setup & Rules)
                    isSubGroup && "justify-between gap-2 px-2.5 py-1.5 rounded-md text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300 hover:bg-slate-100/50 dark:hover:bg-slate-800/40 mt-1",
                    // Level 1 leaf link
                    isLevel1Leaf && "gap-2 px-2.5 py-1.5 rounded-md text-[13px] font-normal",
                    // Level 2 deep leaf link
                    isDeepLeaf && "gap-2 px-2 py-1.5 rounded-md text-xs font-normal",
                    // Active / Inactive states for non-subgroup
                    !isSubGroup && (
                        (isActive || (hasChildren && isChildActive && !isOpen))
                            ? "bg-sky-50/80 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 font-medium"
                            : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 hover:bg-slate-100/70 dark:hover:bg-slate-800/60"
                    )
                )}
            >
                {/* Active Indicator Bar on left */}
                {!isSubGroup && (isActive || (hasChildren && isChildActive && !isOpen)) && (
                    <span
                        className={cn(
                            "absolute top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-sky-600 dark:bg-sky-400",
                            isTopLevel ? "left-0" : "-left-3"
                        )}
                    />
                )}

                {/* Icon for top level */}
                {item.icon && isTopLevel && (
                    <item.icon className={cn(
                        "h-[18px] w-[18px] shrink-0 transition-colors",
                        isActive || (hasChildren && isChildActive)
                            ? "text-sky-600 dark:text-sky-400"
                            : "text-slate-400 dark:text-slate-500 group-hover:text-slate-700 dark:group-hover:text-slate-300"
                    )} />
                )}

                {/* Subgroup or leaf bullet */}
                {level > 0 && !isSubGroup && (
                    <span className={cn(
                        "h-1.5 w-1.5 rounded-full shrink-0 transition-colors",
                        isActive
                            ? "bg-sky-600 dark:bg-sky-400 scale-125"
                            : "bg-slate-300 dark:bg-slate-600 group-hover:bg-slate-400"
                    )} />
                )}

                {/* Item Label */}
                <span className={cn(
                    "truncate flex-1",
                    isTopLevel ? "font-medium" : "",
                    isSubGroup ? "font-semibold" : ""
                )}>
                    {item.label}
                </span>

                {/* Favorite Star Button (on hover or if starred) for leaf routes */}
                {isLeaf && onToggleFavorite && (
                    <span
                        role="button"
                        tabIndex={0}
                        onClick={handleFavoriteClick}
                        onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                handleFavoriteClick(e as any);
                            }
                        }}
                        className={cn(
                            "p-1 rounded hover:bg-slate-200/60 dark:hover:bg-slate-700/60 transition-all shrink-0 cursor-pointer",
                            isFav
                                ? "opacity-100"
                                : "opacity-0 group-hover:opacity-100"
                        )}
                        title={isFav ? "Remove from Favorites" : "Pin to Favorites"}
                        aria-label={isFav ? "Remove from Favorites" : "Pin to Favorites"}
                    >
                        <Star className={cn(
                            "h-3.5 w-3.5 transition-transform hover:scale-115",
                            isFav
                                ? "text-amber-500 fill-amber-400"
                                : "text-slate-400 hover:text-amber-500"
                        )} />
                    </span>
                )}

                {/* Chevron indicator for collapsible modules */}
                {hasChildren && (
                    <ChevronRight className={cn(
                        "h-3.5 w-3.5 shrink-0 text-slate-400 dark:text-slate-500 transition-transform duration-200 ease-in-out",
                        isOpen ? "rotate-90 text-slate-600 dark:text-slate-300" : ""
                    )} />
                )}
            </button>

            {/* Accordion Children Panel */}
            {hasChildren && isOpen && (
                <div className={cn(
                    "transition-all duration-200 ease-in-out",
                    isTopLevel && "ml-3 pl-3 border-l border-slate-200/80 dark:border-slate-800/80 my-0.5 space-y-0.5",
                    isSubGroup && "ml-2 pl-2 border-l border-slate-200/60 dark:border-slate-800/60 my-0.5 space-y-0.5"
                )}>
                    {item.children?.map((child, index) => (
                        <SidebarItem
                            key={`${child.label}-${child.href || index}`}
                            item={child}
                            isCollapsed={false}
                            level={level + 1}
                            parentModule={parentModule || item.label}
                            onNavigate={onNavigate}
                            isFavorite={isFavorite}
                            onToggleFavorite={onToggleFavorite}
                            onExpandSidebar={onExpandSidebar}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
