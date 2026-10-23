"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Pill } from "@/components/dashboard/inventory/shared";
import { usePermissions } from "@/providers/PermissionProvider";
import { RUN_STATUS_LABELS, RunStatus } from "@/types/Payroll";

export {
    Field,
    FILTER_SELECT_CLASS,
    FormDialog,
    PageHeader,
    Pager,
    Pill,
    SELECT_CLASS,
    formatDate,
    formatDateTime,
    formatMoney,
    isNonNegativeDecimal,
    isPositiveDecimal,
} from "@/components/dashboard/inventory/shared";

const TABS = [
    { href: "/dashboard/payroll", label: "Payroll runs", permission: "view_payroll", exact: true },
    { href: "/dashboard/payroll/salaries", label: "Salaries", permission: "view_payroll" },
    { href: "/dashboard/payroll/setup", label: "Setup", permission: "view_payroll" },
    { href: "/dashboard/payroll/my-payslips", label: "My payslips", permission: "" },
];

export function PayrollNav() {
    const pathname = usePathname();
    const { can } = usePermissions();
    return (
        <nav className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800" aria-label="Payroll sections">
            {TABS.filter((tab) => !tab.permission || can(tab.permission)).map((tab) => {
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

const STYLES: Record<RunStatus, string> = {
    draft: "bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300",
    calculated: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    approved: "bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
    paid: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    cancelled: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
    return <Pill className={STYLES[status]}>{RUN_STATUS_LABELS[status]}</Pill>;
}

export const MONTHS = [
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December",
];

/** The year/month of the month before today (the one a school normally pays). */
export function previousMonth(today = new Date()) {
    const month = today.getMonth(); // 0-based: this month's number minus one is last month's 1-based number
    return month === 0 ? { year: today.getFullYear() - 1, month: 12 } : { year: today.getFullYear(), month };
}
