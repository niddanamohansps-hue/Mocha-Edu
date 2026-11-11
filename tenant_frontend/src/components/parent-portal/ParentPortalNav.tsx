"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
    LayoutDashboard,
    Users,
    CalendarCheck,
    CreditCard,
    GraduationCap,
    Clock,
    Video,
    HeartPulse,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
    { href: "/dashboard/parent-portal", label: "Overview", icon: LayoutDashboard, exact: true },
    { href: "/dashboard/parent-portal/children", label: "My Children", icon: Users },
    { href: "/dashboard/parent-portal/attendance", label: "Attendance", icon: CalendarCheck },
    { href: "/dashboard/parent-portal/fees", label: "Fee Payments", icon: CreditCard },
    { href: "/dashboard/parent-portal/results", label: "Results & Reports", icon: GraduationCap },
    { href: "/dashboard/parent-portal/timetable", label: "Timetable", icon: Clock },
    { href: "/dashboard/parent-portal/ptm", label: "PTM Meetings", icon: Video },
    { href: "/dashboard/parent-portal/health", label: "Health", icon: HeartPulse },
];

export function ParentPortalNav() {
    const pathname = usePathname();

    return (
        <div className="border-b border-slate-200 dark:border-slate-800 -mx-4 sm:-mx-6 px-4 sm:px-6 mb-6">
            <nav className="flex space-x-1 sm:space-x-2 overflow-x-auto no-scrollbar py-2" aria-label="Parent Portal Navigation">
                {NAV_ITEMS.map((item) => {
                    const active = item.exact
                        ? pathname === item.href
                        : pathname === item.href || pathname.startsWith(`${item.href}/`);
                    const Icon = item.icon;

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-2 px-3.5 py-2 text-xs font-semibold rounded-lg whitespace-nowrap transition-all shrink-0",
                                active
                                    ? "bg-sky-50 dark:bg-sky-950/60 text-sky-700 dark:text-sky-300 font-bold border border-sky-200/80 dark:border-sky-800 shadow-2xs"
                                    : "text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-100/70 dark:hover:bg-slate-800/60"
                            )}
                        >
                            <Icon className={cn("w-4 h-4", active ? "text-sky-600 dark:text-sky-400" : "text-slate-400")} />
                            <span>{item.label}</span>
                        </Link>
                    );
                })}
            </nav>
        </div>
    );
}

