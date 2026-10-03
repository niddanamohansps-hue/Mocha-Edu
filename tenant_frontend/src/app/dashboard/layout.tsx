"use client";

import { useMe } from "@/hooks/useAuth";
import {
    Menu,
    ChevronRight,
} from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/dashboard/Sidebar/Sidebar";
import { ProfileMenu } from "@/components/dashboard/ProfileMenu";
import { NotificationBell } from "@/components/dashboard/NotificationBell";
import { PermissionProvider } from "@/providers/PermissionProvider";
import PasswordChangeGuard from "@/components/PasswordChangeGuard";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { data: user, isLoading } = useMe();
    const router = useRouter();
    const pathname = usePathname();

    // Two independent concerns that used to share one boolean:
    // - isCollapsed: desktop-only narrow (icon-only) vs. wide sidebar.
    // - isMobileMenuOpen: mobile-only off-canvas drawer visibility.
    // Conflating them meant collapsing the desktop sidebar could also
    // hide/show the mobile drawer (and vice versa) depending on viewport.
    const [isCollapsed, setIsCollapsed] = useState(false);
    const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

    // Close the mobile drawer automatically whenever the route changes -
    // otherwise it stays open over the newly-navigated page.
    useEffect(() => {
        setIsMobileMenuOpen(false);
    }, [pathname]);

    if (isLoading) return null;

    if (!user) {
        router.push("/login");
        return null;
    }

    return (
        <PermissionProvider>
            <PasswordChangeGuard>
                <div className="flex h-screen bg-[#F8FAFC] dark:bg-slate-950 overflow-hidden">

                    {/* Sidebar handles both the persistent desktop <aside> and
                        the full-screen mobile takeover menu internally. */}
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
                                    <span className="text-slate-900 dark:text-white capitalize truncate">{pathname.split('/').pop()?.replace(/-/g, ' ')}</span>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 sm:gap-4 shrink-0">
                                <NotificationBell />
                                <ProfileMenu />
                            </div>
                        </header>

                        {/* Main Content Container */}
                        <main className="flex-1 overflow-y-auto bg-[#F8FAFC] dark:bg-slate-950 p-3 sm:p-6 transition-all duration-300">
                            <div className="max-w-9xl mx-auto animate-in fade-in slide-in-from-bottom-4 duration-500">
                                {children}
                            </div>
                        </main>
                    </div>
                </div>
            </PasswordChangeGuard>
        </PermissionProvider>
    );
}
