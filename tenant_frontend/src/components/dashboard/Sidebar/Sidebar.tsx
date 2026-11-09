"use client";

import { useState, useEffect, useMemo, useRef, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
    ChevronLeft,
    ChevronRight,
    X,
    GraduationCap,
    Search,
    Star,
    Settings,
    LogOut,
    PanelLeftClose,
    PanelLeft,
    Sparkles,
} from "lucide-react";
import { SidebarItem, SidebarItemType } from "@/components/dashboard/Sidebar/SidebarItem";
import { cn, getMediaUrl } from "@/lib/utils";
import Logo from "@/components/Logo";
import { getMenuItems } from "@/components/dashboard/Sidebar/MenuItems";
import { usePermissions } from "@/providers/PermissionProvider";
import { useInstitutionProfile } from "@/hooks/useProfile";
import { useFavorites, FavoriteItem } from "@/hooks/useFavorites";
import { useLogout } from "@/hooks/useAuth";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

interface SidebarProps {
    user: any;
    isCollapsed: boolean;
    setIsCollapsed: (value: boolean) => void;
    isMobileMenuOpen: boolean;
    onCloseMobileMenu: () => void;
}

interface FlatNavItem {
    label: string;
    href: string;
    module: string;
    group?: string;
    path: string[];
}

function itemHasRoute(item: SidebarItemType, pathname: string): boolean {
    if (item.href && item.href === pathname) return true;
    if (item.children) {
        return item.children.some(child => itemHasRoute(child, pathname));
    }
    return false;
}

function flattenNavItems(items: SidebarItemType[], parentPath: string[] = []): FlatNavItem[] {
    const list: FlatNavItem[] = [];
    for (const item of items) {
        const currentPath = [...parentPath, item.label];
        if (item.href) {
            list.push({
                label: item.label,
                href: item.href,
                module: parentPath[0] || item.label,
                group: item.group,
                path: currentPath,
            });
        }
        if (item.children && item.children.length > 0) {
            list.push(...flattenNavItems(item.children, currentPath));
        }
    }
    return list;
}

export function Sidebar({
    user,
    isCollapsed,
    setIsCollapsed,
    isMobileMenuOpen,
    onCloseMobileMenu,
}: SidebarProps) {
    const pathname = usePathname();
    const router = useRouter();
    const { can } = usePermissions();
    const { mutate: logout } = useLogout();

    const menuItems = useMemo(() => getMenuItems(user, can), [user, can]);
    const flatItems = useMemo(() => flattenNavItems(menuItems), [menuItems]);

    // Single-expanded accordion: only ONE module open at any time
    const [openModule, setOpenModule] = useState<string | null>(null);

    // Search filter state
    const [searchQuery, setSearchQuery] = useState("");
    const searchInputRef = useRef<HTMLInputElement>(null);

    // Favorites hook scoped to user id
    const { favorites, isFavorite, toggleFavorite } = useFavorites(user?.id);

    // Auto-detect and open the parent module of the active route
    useEffect(() => {
        if (!pathname) return;
        const activeModule = menuItems.find(item => itemHasRoute(item, pathname));
        if (activeModule && activeModule.children && activeModule.children.length > 0) {
            setOpenModule(activeModule.label);
        }
    }, [pathname, menuItems]);

    // Accordion toggle handler enforcing single-module open
    const handleToggleModule = useCallback((moduleLabel: string) => {
        setOpenModule(prev => (prev === moduleLabel ? null : moduleLabel));
    }, []);

    // Filter navigation results
    const searchResults = useMemo(() => {
        const q = searchQuery.trim().toLowerCase();
        if (!q) return [];
        return flatItems.filter(item =>
            item.label.toLowerCase().includes(q) ||
            item.path.some(p => p.toLowerCase().includes(q)) ||
            item.href.toLowerCase().includes(q)
        );
    }, [flatItems, searchQuery]);

    const handleSelectSearchResult = (result: FlatNavItem) => {
        // Expand the parent module for this route
        const parent = menuItems.find(item => itemHasRoute(item, result.href));
        if (parent && parent.children && parent.children.length > 0) {
            setOpenModule(parent.label);
        }
        setSearchQuery("");
        router.push(result.href);
        if (isMobileMenuOpen) {
            onCloseMobileMenu();
        }
    };

    const handleKeyDownSearch = (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === "Escape") {
            setSearchQuery("");
            searchInputRef.current?.blur();
        } else if (e.key === "Enter" && searchResults.length > 0) {
            handleSelectSearchResult(searchResults[0]);
        }
    };

    // User profile helpers
    const initials = `${user?.profile?.first_name?.[0] || ""}${user?.profile?.last_name?.[0] || ""}`.toUpperCase() || user?.username?.[0]?.toUpperCase() || "U";
    const displayName = [user?.profile?.first_name, user?.profile?.last_name].filter(Boolean).join(" ") || user?.username || "Account";
    const roleLabel = (user?.active_role || user?.roles?.[0] || "User").replace(/_/g, " ");
    const avatarUrl = getMediaUrl(user?.profile?.profile_image);

    // Reusable Sidebar Core (Header, Search, Favorites, Main Nav, Footer)
    const renderSidebarContent = (isMobile: boolean = false) => {
        const collapsed = !isMobile && isCollapsed;

        return (
            <div className="flex flex-col h-full bg-white dark:bg-slate-900 select-none">
                {/* 1. Header: School Logo & MIS Brand */}
                <div className={cn(
                    "h-16 flex items-center justify-between border-b border-slate-100 dark:border-slate-800 shrink-0 transition-all duration-200",
                    collapsed ? "px-2 justify-center" : "px-4"
                )}>
                    <div className={cn(
                        "flex items-center min-w-0 gap-2.5",
                        collapsed && "justify-center"
                    )}>
                        <InstitutionLogo isCollapsed={collapsed} />
                        {!collapsed && (
                            <div className="flex flex-col min-w-0">
                                <span className="text-[10px] font-bold uppercase tracking-wider text-sky-600 dark:text-sky-400">
                                    School MIS
                                </span>
                            </div>
                        )}
                    </div>

                    {!collapsed && !isMobile && (
                        <button
                            type="button"
                            onClick={() => setIsCollapsed(true)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                            title="Collapse sidebar"
                            aria-label="Collapse sidebar"
                        >
                            <PanelLeftClose className="h-4 w-4" />
                        </button>
                    )}

                    {isMobile && (
                        <button
                            type="button"
                            onClick={onCloseMobileMenu}
                            className="p-2 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 hover:text-sky-600 transition-colors"
                            aria-label="Close menu"
                        >
                            <X className="h-5 w-5" />
                        </button>
                    )}
                </div>

                {/* 2. Navigation Search Filter */}
                {!collapsed ? (
                    <div className="px-3 pt-3 pb-2 shrink-0">
                        <div className="relative">
                            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
                            <input
                                ref={searchInputRef}
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                onKeyDown={handleKeyDownSearch}
                                placeholder="Filter navigation... (Esc)"
                                className="w-full pl-8 pr-7 py-1.5 bg-slate-100/70 dark:bg-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 focus:bg-white dark:focus:bg-slate-900 border border-transparent focus:border-sky-500 rounded-lg text-xs text-slate-800 dark:text-slate-200 placeholder-slate-400 focus:outline-none transition-all"
                            />
                            {searchQuery && (
                                <button
                                    type="button"
                                    onClick={() => setSearchQuery("")}
                                    className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 cursor-pointer"
                                    aria-label="Clear search"
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            )}
                        </div>
                    </div>
                ) : (
                    <div className="py-2 flex justify-center shrink-0">
                        <Tooltip delayDuration={100}>
                            <TooltipTrigger asChild>
                                <button
                                    type="button"
                                    onClick={() => setIsCollapsed(false)}
                                    className="p-2 rounded-lg text-slate-400 hover:text-sky-600 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                                    aria-label="Expand search"
                                >
                                    <Search className="h-4 w-4" />
                                </button>
                            </TooltipTrigger>
                            <TooltipContent side="right" sideOffset={12}>
                                <span className="text-xs font-medium">Search navigation</span>
                            </TooltipContent>
                        </Tooltip>
                    </div>
                )}

                {/* 3. Main Scrollable Container (No visible scrollbar) */}
                <div className="flex-1 overflow-y-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden px-2.5 py-1 space-y-3">
                    {/* Active Search Results Overlay */}
                    {searchQuery.trim().length > 0 ? (
                        <div className="space-y-1">
                            <div className="flex items-center justify-between px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                                <span>Results ({searchResults.length})</span>
                                <span className="text-[10px] lowercase text-slate-400">Esc to clear</span>
                            </div>

                            {searchResults.length === 0 ? (
                                <div className="py-8 text-center text-xs text-slate-400 dark:text-slate-500 space-y-1">
                                    <p>No matching pages found.</p>
                                    <p className="text-[11px] text-slate-400">Try &quot;fees&quot;, &quot;attendance&quot;, or &quot;exams&quot;</p>
                                </div>
                            ) : (
                                <div className="space-y-0.5">
                                    {searchResults.map((result) => {
                                        const isFav = isFavorite(result.href);
                                        const isCurrent = pathname === result.href;
                                        return (
                                            <div
                                                key={result.href}
                                                onClick={() => handleSelectSearchResult(result)}
                                                className={cn(
                                                    "group flex items-center justify-between px-3 py-2 rounded-lg text-xs cursor-pointer transition-colors",
                                                    isCurrent
                                                        ? "bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 font-semibold"
                                                        : "text-slate-600 dark:text-slate-400 hover:bg-slate-100/70 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white"
                                                )}
                                            >
                                                <div className="flex flex-col min-w-0 pr-2">
                                                    <span className="truncate font-medium">{result.label}</span>
                                                    <span className="text-[10px] text-slate-400 dark:text-slate-500 truncate">
                                                        {result.path.slice(0, -1).join(" › ") || result.module}
                                                    </span>
                                                </div>

                                                <button
                                                    type="button"
                                                    onClick={(e) => {
                                                        e.stopPropagation();
                                                        toggleFavorite({
                                                            label: result.label,
                                                            href: result.href,
                                                            parent: result.module,
                                                        });
                                                    }}
                                                    className={cn(
                                                        "p-1 rounded hover:bg-slate-200/60 dark:hover:bg-slate-700/60 transition-all shrink-0 cursor-pointer",
                                                        isFav ? "opacity-100" : "opacity-0 group-hover:opacity-100"
                                                    )}
                                                    title={isFav ? "Unpin" : "Pin"}
                                                >
                                                    <Star className={cn(
                                                        "h-3.5 w-3.5",
                                                        isFav ? "fill-amber-400 text-amber-500" : "text-slate-400 hover:text-amber-500"
                                                    )} />
                                                </button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    ) : (
                        <>
                            {/* 3A. Favorites / Pinned Section */}
                            {!collapsed ? (
                                <div className="space-y-1">
                                    <div className="flex items-center justify-between px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                                        <span className="flex items-center gap-1.5">
                                            <Star className="h-3 w-3 text-amber-500 fill-amber-400" />
                                            <span>Favorites</span>
                                        </span>
                                        {favorites.length > 0 && (
                                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400">
                                                {favorites.length}
                                            </span>
                                        )}
                                    </div>

                                    {favorites.length === 0 ? (
                                        <div className="mx-1 px-3 py-2.5 rounded-lg border border-dashed border-slate-200 dark:border-slate-800 text-center text-[11px] text-slate-400 dark:text-slate-500">
                                            <span>Pin frequent pages with the </span>
                                            <Star className="inline h-3 w-3 text-amber-400 fill-amber-400 mx-0.5" />
                                            <span> icon</span>
                                        </div>
                                    ) : (
                                        <div className="space-y-0.5">
                                            {favorites.map((fav) => {
                                                const isActive = pathname === fav.href;
                                                return (
                                                    <div
                                                        key={fav.href}
                                                        onClick={() => {
                                                            const parent = menuItems.find(item => itemHasRoute(item, fav.href));
                                                            if (parent && parent.children) {
                                                                setOpenModule(parent.label);
                                                            }
                                                            router.push(fav.href);
                                                            if (isMobile) onCloseMobileMenu();
                                                        }}
                                                        className={cn(
                                                            "group flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs cursor-pointer transition-colors relative",
                                                            isActive
                                                                ? "bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 font-semibold before:absolute before:left-0 before:top-1.5 before:bottom-1.5 before:w-[3px] before:rounded-r-full before:bg-sky-600 dark:before:bg-sky-400"
                                                                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100/70 dark:hover:bg-slate-800/60 hover:text-slate-900 dark:hover:text-white"
                                                        )}
                                                    >
                                                        <div className="flex items-center gap-2 min-w-0">
                                                            <span className={cn(
                                                                "h-1.5 w-1.5 rounded-full shrink-0",
                                                                isActive ? "bg-sky-600 dark:bg-sky-400" : "bg-amber-400"
                                                            )} />
                                                            <span className="truncate">{fav.label}</span>
                                                        </div>

                                                        <button
                                                            type="button"
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                toggleFavorite(fav);
                                                            }}
                                                            className="p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-slate-200/60 dark:hover:bg-slate-700/60 text-slate-400 hover:text-rose-500 transition-all shrink-0 cursor-pointer"
                                                            title="Unpin favorite"
                                                        >
                                                            <X className="h-3 w-3" />
                                                        </button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}

                                    <div className="my-2 border-t border-slate-100 dark:border-slate-800/80" />
                                </div>
                            ) : (
                                favorites.length > 0 && (
                                    <div className="space-y-1 mb-2 pb-2 border-b border-slate-100 dark:border-slate-800">
                                        {favorites.slice(0, 3).map((fav) => (
                                            <Tooltip key={fav.href} delayDuration={100}>
                                                <TooltipTrigger asChild>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            router.push(fav.href);
                                                        }}
                                                        className={cn(
                                                            "w-10 h-8 mx-auto rounded-lg flex items-center justify-center transition-all cursor-pointer relative",
                                                            pathname === fav.href
                                                                ? "bg-sky-50 dark:bg-sky-500/15 text-sky-600"
                                                                : "text-slate-400 hover:text-amber-500 hover:bg-slate-100 dark:hover:bg-slate-800"
                                                        )}
                                                    >
                                                        <Star className="h-4 w-4 fill-amber-400 text-amber-500" />
                                                    </button>
                                                </TooltipTrigger>
                                                <TooltipContent side="right" sideOffset={12}>
                                                    <div className="text-xs font-semibold">{fav.label}</div>
                                                    {fav.parent && <div className="text-[10px] text-slate-400">{fav.parent}</div>}
                                                </TooltipContent>
                                            </Tooltip>
                                        ))}
                                    </div>
                                )
                            )}

                            {/* 3B. Main Navigation (Single-Expanded Accordion) */}
                            <nav className="space-y-1">
                                {menuItems.map((item, index) => {
                                    const startsGroup = index > 0 && item.group && item.group !== menuItems[index - 1].group;
                                    return (
                                        <div key={item.label}>
                                            {startsGroup && (
                                                collapsed ? (
                                                    <div className="my-2 mx-1 border-t border-slate-100 dark:border-slate-800" />
                                                ) : (
                                                    <div className="px-2.5 pt-3.5 pb-1">
                                                        <span className="text-[10.5px] font-semibold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                                                            {item.group}
                                                        </span>
                                                    </div>
                                                )
                                            )}

                                            <SidebarItem
                                                item={item}
                                                isCollapsed={collapsed}
                                                isOpen={openModule === item.label}
                                                onToggle={() => handleToggleModule(item.label)}
                                                onNavigate={isMobile ? onCloseMobileMenu : undefined}
                                                isFavorite={isFavorite}
                                                onToggleFavorite={toggleFavorite}
                                                onExpandSidebar={() => setIsCollapsed(false)}
                                            />
                                        </div>
                                    );
                                })}
                            </nav>
                        </>
                    )}
                </div>

                {/* 4. Footer: User profile, Settings, Logout */}
                <div className="border-t border-slate-100 dark:border-slate-800 p-2.5 shrink-0 bg-slate-50/50 dark:bg-slate-900/50">
                    {!collapsed ? (
                        <div className="flex items-center justify-between gap-2">
                            <div
                                onClick={() => {
                                    router.push("/dashboard/admin/profile");
                                    if (isMobile) onCloseMobileMenu();
                                }}
                                className="flex items-center gap-2.5 min-w-0 flex-1 px-1.5 py-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                                title="View Profile"
                            >
                                <div className="h-8 w-8 rounded-lg bg-sky-100 dark:bg-sky-950/80 border border-sky-200 dark:border-sky-800 flex items-center justify-center font-bold text-xs text-sky-700 dark:text-sky-300 shrink-0 overflow-hidden">
                                    {avatarUrl ? (
                                        <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
                                    ) : (
                                        initials
                                    )}
                                </div>
                                <div className="flex flex-col min-w-0 flex-1">
                                    <span className="text-xs font-semibold text-slate-800 dark:text-slate-200 truncate">
                                        {displayName}
                                    </span>
                                    <span className="text-[10px] text-slate-400 capitalize truncate">
                                        {roleLabel}
                                    </span>
                                </div>
                            </div>

                            <div className="flex items-center gap-1 shrink-0">
                                <button
                                    type="button"
                                    onClick={() => {
                                        router.push("/dashboard/admin/profile");
                                        if (isMobile) onCloseMobileMenu();
                                    }}
                                    className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-200/60 dark:hover:bg-slate-800 rounded-lg transition-colors cursor-pointer"
                                    title="Settings"
                                    aria-label="Settings"
                                >
                                    <Settings className="h-4 w-4" />
                                </button>
                                <button
                                    type="button"
                                    onClick={() => logout()}
                                    className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 rounded-lg transition-colors cursor-pointer"
                                    title="Sign out"
                                    aria-label="Sign out"
                                >
                                    <LogOut className="h-4 w-4" />
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="flex flex-col items-center gap-2 py-1">
                            <Tooltip delayDuration={100}>
                                <TooltipTrigger asChild>
                                    <div
                                        onClick={() => router.push("/dashboard/admin/profile")}
                                        className="h-9 w-9 rounded-lg bg-sky-100 dark:bg-sky-950/80 border border-sky-200 dark:border-sky-800 flex items-center justify-center font-bold text-xs text-sky-700 dark:text-sky-300 cursor-pointer overflow-hidden"
                                    >
                                        {avatarUrl ? (
                                            <img src={avatarUrl} alt="Avatar" className="w-full h-full object-cover" />
                                        ) : (
                                            initials
                                        )}
                                    </div>
                                </TooltipTrigger>
                                <TooltipContent side="right" sideOffset={12}>
                                    <div className="font-semibold text-xs">{displayName}</div>
                                    <div className="text-[10px] text-slate-400 capitalize">{roleLabel}</div>
                                </TooltipContent>
                            </Tooltip>

                            <Tooltip delayDuration={100}>
                                <TooltipTrigger asChild>
                                    <button
                                        type="button"
                                        onClick={() => logout()}
                                        className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/50 rounded-lg transition-colors cursor-pointer"
                                        aria-label="Sign out"
                                    >
                                        <LogOut className="h-4 w-4" />
                                    </button>
                                </TooltipTrigger>
                                <TooltipContent side="right" sideOffset={12}>
                                    <span className="text-xs">Sign out</span>
                                </TooltipContent>
                            </Tooltip>
                        </div>
                    )}
                </div>
            </div>
        );
    };

    return (
        <>
            {/* Desktop Sidebar: 260px expanded, 68px collapsed */}
            <aside
                className={cn(
                    "hidden lg:flex lg:flex-col h-full border-r border-slate-200 dark:border-slate-800 transition-all duration-300 ease-in-out relative z-30 shrink-0",
                    isCollapsed ? "w-[68px]" : "w-[260px]"
                )}
            >
                {renderSidebarContent(false)}

                {/* Floating expand/collapse toggle pill on right border */}
                <button
                    type="button"
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className="absolute -right-3 top-20 h-6 w-6 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-full flex items-center justify-center text-slate-400 hover:text-sky-600 dark:hover:text-sky-400 shadow-sm z-40 transition-all hover:scale-110 cursor-pointer"
                    title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                    aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                >
                    {isCollapsed ? <ChevronRight className="h-3.5 w-3.5" /> : <ChevronLeft className="h-3.5 w-3.5" />}
                </button>
            </aside>

            {/* Mobile Off-Canvas Drawer with Backdrop */}
            {isMobileMenuOpen && (
                <div className="lg:hidden fixed inset-0 z-50 flex">
                    {/* Dark backdrop overlay */}
                    <div
                        onClick={onCloseMobileMenu}
                        className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity animate-in fade-in duration-200"
                        aria-hidden="true"
                    />

                    {/* Drawer Content */}
                    <div className="relative w-[280px] max-w-[85vw] h-full shadow-2xl z-50 flex flex-col bg-white dark:bg-slate-900 animate-in slide-in-from-left duration-250">
                        {renderSidebarContent(true)}
                    </div>
                </div>
            )}
        </>
    );
}

function InstitutionLogo({ isCollapsed, compact = false }: { isCollapsed: boolean; compact?: boolean }) {
    const { can } = usePermissions();
    const { data: institution } = useInstitutionProfile(can("view_institution_profile"));
    const logoUrl = getMediaUrl(institution?.logo);

    if (logoUrl) {
        if (compact || isCollapsed) {
            return (
                <img
                    src={logoUrl}
                    alt={institution?.name || "Institution Logo"}
                    className="object-contain w-8 h-8 rounded shrink-0"
                />
            );
        }
        return (
            <div className="flex items-center gap-2 min-w-0">
                <img
                    src={logoUrl}
                    alt={institution?.name || "Institution Logo"}
                    className="object-contain w-7 h-7 rounded shrink-0"
                />
                <span className="font-semibold text-sm text-slate-800 dark:text-slate-100 truncate">
                    {institution?.name || "School"}
                </span>
            </div>
        );
    }

    if (isCollapsed) {
        return (
            <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-sky-500 to-teal-500 flex items-center justify-center text-white shadow-2xs shrink-0">
                <GraduationCap className="h-4.5 w-4.5" />
            </div>
        );
    }

    return (
        <div className="flex items-center gap-2 min-w-0">
            <Logo width={120} height={32} />
        </div>
    );
}
