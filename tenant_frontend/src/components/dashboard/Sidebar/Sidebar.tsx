"use client";

import {
    ChevronLeft,
    ChevronRight,
    X,
    GraduationCap,
} from "lucide-react";
import { SidebarItem } from "@/components/dashboard/Sidebar/SidebarItem";
import { cn } from "@/lib/utils";
import Logo from "@/components/Logo";
import { getMenuItems } from "@/components/dashboard/Sidebar/MenuItems";
import { usePermissions } from "@/providers/PermissionProvider";
import { useInstitutionProfile } from "@/hooks/useProfile";
import { getMediaUrl } from "@/lib/utils";

interface SidebarProps {
    user: any;
    isCollapsed: boolean;
    setIsCollapsed: (value: boolean) => void;
    isMobileMenuOpen: boolean;
    onCloseMobileMenu: () => void;
}

export function Sidebar({ user, isCollapsed, setIsCollapsed, isMobileMenuOpen, onCloseMobileMenu }: SidebarProps) {
    const { can } = usePermissions();
    const menuItems = getMenuItems(user, can);

    return (
        <>
            {/* Desktop sidebar - persistent, collapsible narrow/wide. Hidden
                entirely below lg: the mobile full-screen menu takes over there. */}
            <aside className={cn(
                "hidden lg:flex lg:flex-col h-full bg-white dark:bg-slate-900 border-r border-slate-200 dark:border-slate-800 transition-all duration-300 ease-in-out relative",
                isCollapsed ? "w-20" : "w-72"
            )}>
                <div className={cn(
                    "h-20 flex items-center px-6 border-b border-slate-100 dark:border-slate-800 transition-all duration-300",
                    isCollapsed && "justify-center px-0"
                )}>
                    <InstitutionLogo isCollapsed={isCollapsed} />
                </div>

                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className="absolute -right-3 bottom-24 h-6 w-6 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full flex items-center justify-center text-slate-500 hover:text-sky-600 shadow-sm z-40 transition-colors cursor-pointer"
                >
                    {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
                </button>

                <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto scrollbar-thin scrollbar-thumb-slate-200 dark:scrollbar-thumb-slate-800">
                    {menuItems.map((item, index) => (
                        <SidebarItem key={index} item={item} isCollapsed={isCollapsed} />
                    ))}
                </nav>
            </aside>

            {/* Mobile full-screen menu - a solid, opaque takeover instead of a
                partial-width drawer with a translucent backdrop. Only mounted
                while open, so there's nothing behind it to keep in sync. */}
            {isMobileMenuOpen && (
                <div className="lg:hidden fixed inset-0 z-50 bg-white dark:bg-slate-900 flex flex-col animate-in fade-in duration-200">
                    <div className="h-16 flex items-center justify-between px-4 border-b border-slate-100 dark:border-slate-800 shrink-0">
                        <div className="flex items-center gap-2">
                            <span className="p-1.5 rounded-lg bg-gradient-to-br from-sky-500 to-teal-500 shadow-sm">
                                <GraduationCap className="h-5 w-5 text-white" />
                            </span>
                            <InstitutionLogo isCollapsed={false} compact />
                        </div>
                        <button
                            onClick={onCloseMobileMenu}
                            className="p-2 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-sky-600 hover:bg-sky-50 dark:hover:bg-slate-700 transition-colors"
                            aria-label="Close menu"
                        >
                            <X className="h-5 w-5" />
                        </button>
                    </div>

                    <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
                        {menuItems.map((item, index) => (
                            <SidebarItem key={index} item={item} isCollapsed={false} />
                        ))}
                    </nav>
                </div>
            )}
        </>
    );
}

function InstitutionLogo({ isCollapsed, compact = false }: { isCollapsed: boolean; compact?: boolean }) {
    const { data: institution } = useInstitutionProfile();
    const logoUrl = getMediaUrl(institution?.logo);

    if (logoUrl) {
        if (compact) {
            return (
                <img
                    src={logoUrl}
                    alt={institution?.name || "Institution Logo"}
                    className="object-contain w-8 h-8 rounded"
                />
            );
        }
        return (
            <img
                src={logoUrl}
                alt={institution?.name || "Institution Logo"}
                className={cn("object-contain w-30 h-15", isCollapsed && "w-10 h-10")}
            />
        );
    }

    if (compact) {
        return <span className="font-bold text-lg text-slate-900 dark:text-white">{institution?.name || "Menu"}</span>;
    }

    return <Logo width={isCollapsed ? 50 : 150} height={isCollapsed ? 50 : 40} />;
}
