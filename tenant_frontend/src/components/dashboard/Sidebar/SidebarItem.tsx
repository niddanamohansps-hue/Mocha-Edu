"use client";

import { LucideIcon, ChevronDown } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useState, useEffect } from "react";
import { cn } from "@/lib/utils";

export interface SidebarItemType {
    label: string;
    icon?: LucideIcon;
    href?: string;
    children?: SidebarItemType[];
    /** Heading the item is listed under; set by getMenuItems, shown by the sidebar. */
    group?: string;
}

interface SidebarItemProps {
    item: SidebarItemType;
    isCollapsed: boolean;
    level?: number;
}

export function SidebarItem({ item, isCollapsed, level = 0 }: SidebarItemProps) {
    const pathname = usePathname();
    const router = useRouter();
    const [isOpen, setIsOpen] = useState(false);

    const hasChildren = item.children && item.children.length > 0;
    const isActive = item.href ? pathname === item.href : false;
    const isChildActive = item.children?.some(child =>
        child.href === pathname || child.children?.some(subChild => subChild.href === pathname)
    );

    // Auto-expand if a child is active
    useEffect(() => {
        if (isChildActive) {
            setIsOpen(true);
        }
    }, [isChildActive]);

    const handleClick = () => {
        if (hasChildren) {
            if (!isCollapsed) {
                setIsOpen(!isOpen);
            }
        } else if (item.href) {
            router.push(item.href);
        }
    };

    const isSubGroup = level === 1 && hasChildren;
    const isDeepLeaf = level >= 2;
    const isLevel1Leaf = level === 1 && !hasChildren;

    return (
        <div className="w-full">
            <button
                onClick={handleClick}
                className={cn(
                    "w-full flex items-center transition-all duration-200 ease-out group relative cursor-pointer overflow-hidden",
                    level === 0 && "gap-3 px-3.5 py-2.5 rounded-xl text-sm",
                    isSubGroup && "justify-between gap-2 px-3 py-1.5 rounded-lg text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 hover:bg-slate-100/60 dark:hover:bg-slate-800/40",
                    isLevel1Leaf && "gap-2.5 px-3 py-2 rounded-lg text-xs font-medium",
                    isDeepLeaf && "gap-2 px-2.5 py-1.5 rounded-md text-xs font-medium",
                    !isSubGroup && ((isActive || (hasChildren && isChildActive && !isOpen))
                        ? "bg-gradient-to-r from-sky-50 to-teal-50/50 dark:from-sky-500/10 dark:to-teal-500/5 text-sky-600 dark:text-sky-400 font-semibold"
                        : "text-slate-500 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50 hover:text-slate-900 dark:hover:text-white hover:translate-x-0.5"),
                    isDeepLeaf && isActive && "border-l-2 border-sky-500 pl-2 rounded-l-none",
                    isCollapsed && "justify-center px-0"
                )}
                title={isCollapsed ? item.label : undefined}
            >
                {(!isSubGroup && (isActive || (hasChildren && isChildActive && !isOpen))) && (
                    <span className="absolute left-0 top-1/2 -translate-y-1/2 h-2/3 w-1 rounded-r-full bg-gradient-to-b from-sky-500 to-teal-500" />
                )}
                {item.icon && (
                    <item.icon className={cn(
                        "h-5 w-5 shrink-0 transition-transform duration-200 ease-out",
                        isActive ? "text-sky-600 dark:text-sky-400" : "group-hover:scale-110"
                    )} />
                )}

                {!isCollapsed && (
                    <>
                        <span className={cn(
                            "truncate flex-1 text-left",
                            isSubGroup ? "font-semibold" : ""
                        )}>
                            {item.label}
                        </span>
                        {hasChildren && (
                            <div className={cn(
                                "transition-transform duration-200",
                                isOpen ? "rotate-180" : ""
                            )}>
                                <ChevronDown className={cn(
                                    "opacity-50",
                                    level === 0 ? "h-4 w-4" : "h-3.5 w-3.5"
                                )} />
                            </div>
                        )}
                    </>
                )}
            </button>

            {hasChildren && isOpen && !isCollapsed && (
                <div className={cn(
                    "mt-0.5 space-y-0.5 slide-in-from-top-1 animate-in duration-200",
                    level === 0 ? "ml-3 pl-2 border-l border-slate-200 dark:border-slate-800" : "ml-2 pl-2 border-l border-slate-200/80 dark:border-slate-800/80"
                )}>
                    {item.children?.map((child, index) => (
                        <SidebarItem
                            key={index}
                            item={child}
                            isCollapsed={isCollapsed}
                            level={level + 1}
                        />
                    ))}
                </div>
            )}
        </div>
    );
}
