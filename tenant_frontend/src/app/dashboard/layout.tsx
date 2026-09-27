"use client";

import { useMe } from "@/hooks/useAuth";
import {
    Menu,
    ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Sidebar } from "@/components/dashboard/Sidebar/Sidebar";
import { cn } from "@/lib/utils";
import { ProfileMenu } from "@/components/dashboard/ProfileMenu";
import { NotificationBell } from "@/components/dashboard/NotificationBell";
import { PermissionProvider } from "@/providers/PermissionProvider";
import PasswordChangeGuard from "@/components/PasswordChangeGuard";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const { data: user, isLoading } = useMe();
    const router = useRouter();
    const pathname = usePathname();

    const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);

    if (isLoading) return null;

    if (!user) {
        router.push("/login");
        return null;
    }

    return (
        <PermissionProvider>
            <PasswordChangeGuard>
                <div className="flex h-screen bg-[#F8FAFC] dark:bg-slate-950 overflow-hidden">

                    {/* Sidebar Container */}
                    <div className={cn(
                        "fixed inset-y-0 left-0 z-50 transition-transform duration-300 transform lg:relative lg:translate-x-0 h-full",
                        isSidebarCollapsed ? "translate-x-0" : "-translate-x-full"
                    )}>
                        <Sidebar
                            user={user}
                            isCollapsed={isSidebarCollapsed}
                            setIsCollapsed={setIsSidebarCollapsed}
                        />
                    </div>

                    {/* Main Content Area */}
                    <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
                        {/* Header */}
                        <header className="h-16 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border-b border-slate-200 dark:border-slate-800 flex items-center justify-between p-6 z-10 transition-all duration-300">
                            <div className="flex items-center gap-4">
                                <button
                                    onClick={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
                                    className="lg:hidden p-2 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg transition-colors"
                                >
                                    <Menu className="h-6 w-6 text-slate-600 dark:text-slate-400" />
                                </button>
                                <div className="flex items-center gap-2 text-sm font-medium text-slate-500">
                                    <span className="hidden sm:inline">Dashboard</span>
                                    <ChevronRight className="h-4 w-4 hidden sm:inline" />
                                    <span className="text-slate-900 dark:text-white capitalize">{pathname.split('/').pop()?.replace(/-/g, ' ')}</span>
                                </div>
                            </div>

                            <div className="flex items-center gap-2 sm:gap-4">
                                <NotificationBell />
                                <ProfileMenu />
                            </div>
                        </header>

                        {/* Main Content Container */}
                        <main className="flex-1 overflow-y-auto bg-[#F8FAFC] dark:bg-slate-950 p-6 transition-all duration-300">
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
