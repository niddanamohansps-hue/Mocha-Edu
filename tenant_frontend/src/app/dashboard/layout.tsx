"use client";

import { useMe } from "@/hooks/useAuth";
import {
    Menu,
    ChevronRight,
    Search,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/dashboard/Sidebar/Sidebar";
import { ProfileMenu } from "@/components/dashboard/ProfileMenu";
import { NotificationBell } from "@/components/dashboard/NotificationBell";
import { PermissionProvider } from "@/providers/PermissionProvider";
import { AcademicYearProvider } from "@/providers/AcademicYearProvider";
import { AcademicYearSelector } from "@/components/dashboard/AcademicYearSelector";
import { QuickActionMenu } from "@/components/dashboard/QuickActionMenu";
import PasswordChangeGuard from "@/components/PasswordChangeGuard";
import { CommandPalette } from "@/components/dashboard/CommandPalette";
import { MobileBottomNav } from "@/components/parent-portal/MobileBottomNav";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { data: user, isLoading } = useMe();
    const router = useRouter();
    const pathname = usePathname();

    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
    const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

    // Close the mobile drawer automatically whenever the route changes
    useEffect(() => {
        setIsMobileMenuOpen(false);
    }, [pathname]);

    // Global Ctrl+K / Cmd+K listener
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "k") {
                e.preventDefault();
                setIsCommandPaletteOpen((prev) => !prev);
            }
        };
        window.addEventListener("keydown", handleKeyDown);
        return () => window.removeEventListener("keydown", handleKeyDown);
    }, []);

    if (isLoading) return null;

    if (!user) {
        router.push("/login");
        return null;
    }

    const isParentPortal = pathname?.startsWith("/dashboard/parent-portal");

    return (
        <PermissionProvider>
            <AcademicYearProvider>
                <PasswordChangeGuard>
                    <div className="flex h-screen bg-[#F8FAFC] dark:bg-slate-950 overflow-hidden">
                        {/* Sidebar handles both persistent desktop and mobile menu */}
                        <Sidebar
                            user={user}
                            isCollapsed={isCollapsed}
                            setIsCollapsed={setIsCollapsed}
                            isMobileMenuOpen={isMobileMenuOpen}
                            onCloseMobileMenu={() => setIsMobileMenuOpen(false)}
                        />

                        {/* Main Content Area */}
                        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                            {/* Header */}
                            <header className="relative h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-4 sm:px-6 z-10 transition-all duration-300">
                                <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-sky-500/30 via-teal-500/30 to-transparent" />
                                
                                <div className="flex items-center gap-2 sm:gap-4 min-w-0">
                                    <button
                                        onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
                                        className="lg:hidden p-2 hover:bg-sky-50 dark:hover:bg-slate-800 hover:text-sky-600 rounded-lg transition-all duration-200 ease-out hover:scale-105 shrink-0"
                                        aria-label="Toggle menu"
                                    >
                                        <Menu className="h-6 w-6 text-slate-600 dark:text-slate-400" />
                                    </button>
                                    <div className="flex items-center gap-2 text-sm font-medium text-slate-500 min-w-0">
                                        <span className="hidden sm:inline shrink-0">Dashboard</span>
                                        <ChevronRight className="h-4 w-4 hidden sm:inline shrink-0" />
                                        <span className="text-slate-900 dark:text-white capitalize truncate">
                                            {pathname.split("/").pop()?.replace(/-/g, " ")}
                                        </span>
                                    </div>
                                </div>

                                {/* Quick Command Search Button */}
                                <button
                                    onClick={() => setIsCommandPaletteOpen(true)}
                                    className="hidden md:flex items-center gap-2.5 px-3 py-1.5 text-xs text-slate-500 dark:text-slate-400 bg-slate-100/80 dark:bg-slate-800/80 hover:bg-slate-200/80 dark:hover:bg-slate-700/80 rounded-xl border border-slate-200/60 dark:border-slate-700/60 transition shadow-2xs cursor-pointer"
                                    title="Press Ctrl + K to search"
                                >
                                    <Search className="h-3.5 w-3.5 text-indigo-500 shrink-0" />
                                    <span className="text-slate-600 dark:text-slate-300">Search students, staff or commands...</span>
                                    <kbd className="px-1.5 py-0.5 text-[10px] font-mono bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded text-slate-400">
                                        Ctrl K
                                    </kbd>
                                </button>

                                <div className="flex items-center gap-2 sm:gap-4 shrink-0">
                                    <button
                                        onClick={() => setIsCommandPaletteOpen(true)}
                                        className="md:hidden p-2 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition"
                                        aria-label="Search"
                                    >
                                        <Search className="h-5 w-5" />
                                    </button>
                                    <AcademicYearSelector />
                                    <QuickActionMenu />
                                    <NotificationBell />
                                    <ProfileMenu />
                                </div>
                            </header>

                            {/* Main Content Container */}
                            <main className={`flex-1 overflow-y-auto bg-[#F8FAFC] dark:bg-slate-950 p-3 sm:p-6 transition-all duration-300 ${
                                isParentPortal ? "pb-20 md:pb-6" : ""
                            }`}>
                                <div className="max-w-9xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
                                    {children}
                                </div>
                            </main>

                            {/* Mobile Bottom Navigation for Parent Portal */}
                            {isParentPortal && <MobileBottomNav />}
                        </div>

                        {/* Global Command Palette */}
                        <CommandPalette
                            isOpen={isCommandPaletteOpen}
                            onClose={() => setIsCommandPaletteOpen(false)}
                        />
                    </div>
                </PasswordChangeGuard>
            </AcademicYearProvider>
        </PermissionProvider>
    );
}
