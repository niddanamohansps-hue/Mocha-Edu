"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePermissions } from "@/providers/PermissionProvider";

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
    { href: "/dashboard/transport", label: "Routes", exact: true },
    { href: "/dashboard/transport/fleet", label: "Vehicles & drivers" },
    { href: "/dashboard/transport/students", label: "Students" },
    { href: "/dashboard/transport/billing", label: "Billing" },
];

export function TransportNav() {
    const pathname = usePathname();
    const { can } = usePermissions();
    if (!can("view_transport")) return null;
    return (
        <nav className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800" aria-label="Transport sections">
            {TABS.map((tab) => {
                const active = tab.exact ? pathname === tab.href : pathname.startsWith(tab.href);
                return (
                    <Link
                        key={tab.href}
                        href={tab.href}
                        aria-current={active ? "page" : undefined}
                        className={`px-4 py-2 text-sm font-semibold border-b-2 -mb-px transition-colors ${
                            active
                                ? "border-sky-600 text-sky-700 dark:text-sky-400"
                                : "border-transparent text-slate-500 hover:text-slate-800 dark:hover:text-slate-200"
                        }`}
                    >
                        {tab.label}
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
