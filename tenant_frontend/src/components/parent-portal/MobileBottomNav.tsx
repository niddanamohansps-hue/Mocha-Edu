"use client";

import React from "react";
import Link from "next/navigation";
import { usePathname } from "next/navigation";
import {
    Home,
    CalendarCheck,
    Receipt,
    CheckCircle2,
    Calendar,
} from "lucide-react";

/**
 * Mobile-First Bottom Navigation Bar for Parent Portal.
 * Visible on mobile viewports (< 768px) to provide a consumer-grade app feel.
 */
export function MobileBottomNav() {
    const pathname = usePathname();

    const navItems = [
        {
            label: "Home",
            href: "/dashboard/parent-portal",
            icon: Home,
            exact: true,
        },
        {
            label: "PTM Meetings",
            href: "/dashboard/parent-portal/ptm",
            icon: CalendarCheck,
        },
        {
            label: "Pay Fees",
            href: "/dashboard/parent-portal/fees",
            icon: Receipt,
        },
        {
            label: "Attendance",
            href: "/dashboard/parent-portal/attendance",
            icon: CheckCircle2,
        },
    ];

    return (
        <div className="md:hidden fixed bottom-0 inset-x-0 z-40 bg-white/95 dark:bg-slate-900/95 backdrop-blur-md border-t border-slate-200 dark:border-slate-800 pb-safe shadow-lg">
            <div className="grid grid-cols-4 h-15">
                {navItems.map((item) => {
                    const isActive = item.exact
                        ? pathname === item.href
                        : pathname.startsWith(item.href);
                    const Icon = item.icon;

                    return (
                        <a
                            key={item.href}
                            href={item.href}
                            className={`flex flex-col items-center justify-center gap-1 transition-colors relative ${
                                isActive
                                    ? "text-indigo-600 dark:text-indigo-400 font-bold"
                                    : "text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 font-medium"
                            }`}
                        >
                            {isActive && (
                                <span className="absolute top-0 w-8 h-0.5 bg-indigo-600 dark:bg-indigo-400 rounded-full" />
                            )}
                            <Icon className={`h-5 w-5 ${isActive ? "scale-110" : ""}`} />
                            <span className="text-[10px] tracking-tight">{item.label}</span>
                        </a>
                    );
                })}
            </div>
        </div>
    );
}
