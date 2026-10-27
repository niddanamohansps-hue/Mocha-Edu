"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import { PageHeader } from "@/components/common/PageLayout";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { usePermissions } from "@/providers/PermissionProvider";
import { AssetCondition, AssetStatus, ASSET_CONDITION_LABELS, ASSET_STATUS_LABELS } from "@/types/Inventory";

export { PageHeader };

export const SELECT_CLASS =
    "w-full rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm";
export const FILTER_SELECT_CLASS = "rounded-xl border border-slate-200 dark:border-slate-800 bg-transparent px-3 py-2 text-sm";

/** Show a decimal string without trailing zeros: "12.500" -> "12.5", "0.000" -> "0". */
export function formatQuantity(value: string | null | undefined) {
    if (value === null || value === undefined || value === "") return "-";
    return value.includes(".") ? value.replace(/\.?0+$/, "") || "0" : value;
}

/** Money as the API sent it, grouped in thousands: "85000.00" -> "85,000.00". */
export function formatMoney(value: string | null | undefined) {
    if (value === null || value === undefined || value === "") return "-";
    const [whole, fraction] = value.split(".");
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return fraction ? `${grouped}.${fraction}` : grouped;
}

export function formatDate(value: string | null | undefined) {
    return value ? new Date(value).toLocaleDateString() : "-";
}

export function formatDateTime(value: string | null | undefined) {
    return value ? new Date(value).toLocaleString() : "-";
}

export function isPositiveDecimal(value: string, maxDecimals = 3) {
    return new RegExp(`^\\d+(\\.\\d{1,${maxDecimals}})?$`).test(value.trim()) && Number(value) > 0;
}

export function isNonNegativeDecimal(value: string, maxDecimals = 2) {
    return new RegExp(`^\\d+(\\.\\d{1,${maxDecimals}})?$`).test(value.trim());
}

const TABS = [
    { href: "/dashboard/inventory", label: "Stock", permission: "view_inventory", exact: true },
    { href: "/dashboard/inventory/movements", label: "Movements", permission: "view_inventory" },
    { href: "/dashboard/inventory/purchases", label: "Purchases", permission: "view_inventory" },
    { href: "/dashboard/inventory/assets", label: "Assets", permission: "view_assets" },
    { href: "/dashboard/inventory/setup", label: "Setup", permission: "view_inventory" },
];

export function InventoryNav() {
    const pathname = usePathname();
    const { can } = usePermissions();
    return (
        <nav className="flex flex-wrap gap-1 border-b border-slate-200 dark:border-slate-800" aria-label="Inventory sections">
            {TABS.filter((tab) => can(tab.permission)).map((tab) => {
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

export function Pager({
    data,
    page,
    onPage,
}: {
    data?: { next: string | null; previous: string | null } | null;
    page: number;
    onPage: (page: number) => void;
}) {
    if (!data || (!data.next && !data.previous)) return null;
    return (
        <div className="flex flex-wrap items-center justify-between gap-2 pt-2">
            <Button variant="outline" size="sm" disabled={!data.previous} onClick={() => onPage(Math.max(1, page - 1))}>
                Previous
            </Button>
            <span className="text-xs text-slate-500">Page {page}</span>
            <Button variant="outline" size="sm" disabled={!data.next} onClick={() => onPage(page + 1)}>
                Next
            </Button>
        </div>
    );
}

export function Field({ label, htmlFor, hint, children }: { label: string; htmlFor: string; hint?: string; children: ReactNode }) {
    return (
        <div className="space-y-1.5">
            <Label htmlFor={htmlFor}>{label}</Label>
            {children}
            {hint && <p className="text-xs text-slate-500">{hint}</p>}
        </div>
    );
}

/** A modal form. The caller owns the fields and validation; `error` shows the first problem. */
export function FormDialog({
    open,
    onOpenChange,
    title,
    description,
    submitLabel,
    pending,
    error,
    onSubmit,
    children,
    wide,
}: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    title: string;
    description?: string;
    submitLabel: string;
    pending?: boolean;
    error?: string | null;
    onSubmit: () => void;
    children: ReactNode;
    wide?: boolean;
}) {
    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className={`${wide ? "sm:max-w-2xl" : "sm:max-w-md"} max-h-[90vh] overflow-y-auto`}>
                <form
                    onSubmit={(e) => {
                        e.preventDefault();
                        onSubmit();
                    }}
                    className="space-y-4"
                >
                    <DialogHeader>
                        <DialogTitle>{title}</DialogTitle>
                        {description && <DialogDescription>{description}</DialogDescription>}
                    </DialogHeader>
                    {children}
                    {error && (
                        <p role="alert" className="text-sm text-red-600 whitespace-pre-line">
                            {error}
                        </p>
                    )}
                    <DialogFooter>
                        <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={pending}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={pending}>
                            {pending ? "Saving..." : submitLabel}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

const ASSET_STATUS_STYLES: Record<AssetStatus, string> = {
    available: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400",
    assigned: "bg-sky-100 text-sky-700 dark:bg-sky-500/10 dark:text-sky-400",
    in_repair: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400",
    lost: "bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400",
    disposed: "bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400",
};

export function Pill({ className, children }: { className: string; children: ReactNode }) {
    return <span className={`inline-block rounded-full px-2.5 py-0.5 text-[11px] font-bold ${className}`}>{children}</span>;
}

export function AssetStatusBadge({ status }: { status: AssetStatus }) {
    return <Pill className={ASSET_STATUS_STYLES[status]}>{ASSET_STATUS_LABELS[status]}</Pill>;
}

export function ConditionLabel({ condition }: { condition: AssetCondition }) {
    return <span>{ASSET_CONDITION_LABELS[condition]}</span>;
}

export function LowStockBadge() {
    return <Pill className="bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400">Low stock</Pill>;
}
