"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePermissions } from "@/providers/PermissionProvider";
import { Compass, Bus, Users, Receipt } from "lucide-react";

export {
    Field,
    FILTER_SELECT_CLASS,
    FormDialog,
    PageHeader,
    Pager,
    Pill,
    SELECT_CLASS,
    formatDate,
    formatMoney,
    isNonNegativeDecimal,
} from "@/components/dashboard/inventory/shared";

const TABS = [
    { href: "/dashboard/transport", label: "Routes & Schedules", icon: Compass, exact: true },
    { href: "/dashboard/transport/fleet", label: "Fleet & Crew", icon: Bus },
    { href: "/dashboard/transport/students", label: "Student Roster", icon: Users },
    { href: "/dashboard/transport/billing", label: "Monthly Billing", icon: Receipt },
];

export function TransportNav() {
    const pathname = usePathname();
    const { can } = usePermissions();
    if (!can("view_transport")) return null;
    return (
        <nav className="flex items-center gap-1 border-b border-slate-200/80 dark:border-slate-800 pb-px overflow-x-auto scrollbar-none" aria-label="Transport sections">
            {TABS.map((tab) => {
                const active = tab.exact ? pathname === tab.href : pathname.startsWith(tab.href);
                const Icon = tab.icon;
                return (
                    <Link
                        key={tab.href}
                        href={tab.href}
                        aria-current={active ? "page" : undefined}
                        className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold border-b-2 transition-all cursor-pointer whitespace-nowrap ${
                            active
                                ? "border-sky-600 text-sky-600 dark:text-sky-400 bg-sky-50/50 dark:bg-sky-950/20 rounded-t-lg"
                                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 hover:border-slate-300"
                        }`}
                    >
                        <Icon className={`w-3.5 h-3.5 ${active ? "text-sky-600 dark:text-sky-400" : "text-slate-400"}`} />
                        <span>{tab.label}</span>
                    </Link>
                );
            })}
        </nav>
    );
}

/** "2026-10-31" -> days from today, as words a person can act on. */
export function expiryText(daysLeft: number) {
    if (daysLeft < 0) return `expired ${-daysLeft} day${daysLeft === -1 ? "" : "s"} ago`;
    if (daysLeft === 0) return "expires today";
    return `expires in ${daysLeft} day${daysLeft === 1 ? "" : "s"}`;
}

/** The current month as YYYY-MM, which is what the billing API takes. */
export function monthValue(date = new Date()) {
    return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}
