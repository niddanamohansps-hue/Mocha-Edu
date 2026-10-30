"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { usePermissions } from "@/providers/PermissionProvider";
import { RUN_STATUS_LABELS, RunStatus } from "@/types/Payroll";
import { Banknote, Users, Settings, FileText } from "lucide-react";

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
    { href: "/dashboard/payroll", label: "Payroll Runs", icon: Banknote, permission: "view_payroll", exact: true },
    { href: "/dashboard/payroll/salaries", label: "Staff Salary Profiles", icon: Users, permission: "view_payroll" },
    { href: "/dashboard/payroll/setup", label: "Salary Components", icon: Settings, permission: "view_payroll" },
    { href: "/dashboard/payroll/my-payslips", label: "My Payslips", icon: FileText, permission: "" },
];

export function PayrollNav() {
    const pathname = usePathname();
    const { can } = usePermissions();
    return (
        <nav className="flex items-center gap-1 border-b border-slate-200/80 dark:border-slate-800 pb-px overflow-x-auto scrollbar-none" aria-label="Payroll sections">
            {TABS.filter((tab) => !tab.permission || can(tab.permission)).map((tab) => {
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

export function RunStatusBadge({ status }: { status: RunStatus }) {
    switch (status) {
        case "paid":
            return (
                <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                    Paid & Disbursed
                </Badge>
            );
        case "approved":
            return (
                <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 font-semibold text-[11px]">
                    Approved for Payout
                </Badge>
            );
        case "calculated":
            return (
                <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-[11px]">
                    Calculated (Pending Sign-off)
                </Badge>
            );
        case "draft":
            return (
                <Badge variant="outline" className="text-[11px] text-slate-500 border-slate-300">
                    Draft Cycle
                </Badge>
            );
        case "cancelled":
            return (
                <Badge className="bg-rose-50 text-rose-700 dark:bg-rose-950/60 dark:text-rose-300 border border-rose-300/80 font-semibold text-[11px]">
                    Cancelled
                </Badge>
            );
        default:
            return <Badge variant="outline" className="text-[11px]">{status}</Badge>;
    }
}

export const MONTHS = [
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December",
];

/** The year/month of the month before today (the one a school normally pays). */
export function previousMonth(today = new Date()) {
    const month = today.getMonth(); // 0-based: this month's number minus one is last month's 1-based number
    return month === 0 ? { year: today.getFullYear() - 1, month: 12 } : { year: today.getFullYear(), month };
}
