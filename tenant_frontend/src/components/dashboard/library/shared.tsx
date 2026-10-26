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
    { href: "/dashboard/library", label: "Books", exact: true },
    { href: "/dashboard/library/loans", label: "Loans" },
    { href: "/dashboard/library/fines", label: "Fines" },
    { href: "/dashboard/library/setup", label: "Setup" },
];

export function LibraryNav() {
    const pathname = usePathname();
    const { can } = usePermissions();
    if (!can("view_library")) return null;
    return (
        <nav className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800" aria-label="Library sections">
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
