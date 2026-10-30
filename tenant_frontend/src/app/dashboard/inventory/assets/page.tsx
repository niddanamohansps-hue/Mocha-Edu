"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
    Laptop,
    Plus,
    Search,
    X,
    MapPin,
    User,
    Calendar,
    ChevronRight,
    Coins,
    ShieldCheck,
    Wrench,
    CheckCircle2,
    SlidersHorizontal,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { AssetFormDialog } from "@/components/dashboard/inventory/AssetDialogs";
import {
    AssetStatusBadge,
    formatDate,
    formatMoney,
} from "@/components/dashboard/inventory/shared";
import { useAllOf, useAssetSummary, useAssets } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    ASSET_CONDITION_LABELS,
    ASSET_STATUS_LABELS,
    AssetCategory,
    AssetFilters,
    AssetStatus,
} from "@/types/Inventory";
import { formatIndianCurrency } from "@/lib/currency";

const PAGE_SIZE = 20;
const STATUSES = Object.keys(ASSET_STATUS_LABELS) as AssetStatus[];

export default function AssetsPage() {
    const { can } = usePermissions();
    const canManage = can("manage_assets");

    const [filters, setFilters] = useState<AssetFilters>({ page: 1, status: "", category: "", search: "" });
    const [searchText, setSearchText] = useState("");
    const [registerOpen, setRegisterOpen] = useState(false);

    const categoriesQuery = useAllOf<AssetCategory>("asset-categories");
    const categories = categoriesQuery.data ?? [];

    const summaryQuery = useAssetSummary();
    const summary = summaryQuery.data;

    const { data, isLoading, isError, refetch } = useAssets(filters);

    if (!can("view_assets")) {
        return <ErrorState message="You do not have permission to view institutional assets." />;
    }

    const rows = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    const change = (patch: Partial<AssetFilters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Laptop className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Fixed Assets & Equipment Registry</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Durable school assets, computer labs, smartboards, custodian assignments, and lifecycle maintenance tracking
                    </p>
                </div>

                {canManage && (
                    <Button
                        onClick={() => setRegisterOpen(true)}
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Register New Asset</span>
                    </Button>
                )}
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Assets */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Registered</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Laptop className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {summary?.total ?? totalCount}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">assets</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Institutional property tagged
                    </p>
                </div>

                {/* Available in Storage */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Available in Storage</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {summary?.by_status?.available ?? 0}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            ready for issue
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        In central warehouse depot
                    </p>
                </div>

                {/* Assigned */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Assigned & Deployed</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <User className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {summary?.by_status?.assigned ?? 0}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">in service</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        With staff or classrooms
                    </p>
                </div>

                {/* Capital Outlay In Service */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Capital Value in Service</span>
                        <div className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                            <Coins className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {formatIndianCurrency(summary?.purchase_cost_in_service || "0")}
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Active asset cost basis
                    </p>
                </div>
            </div>

            {/* 3. Filter Controls Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col md:flex-row items-center justify-between gap-3">
                {/* Search */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search assets by tag code, equipment name, or serial number..."
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter") change({ search: searchText.trim() });
                        }}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                    {searchText && (
                        <button
                            onClick={() => {
                                setSearchText("");
                                change({ search: "" });
                            }}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                {/* Category & Status Dropdowns */}
                <div className="flex items-center gap-2 w-full md:w-auto shrink-0 justify-between sm:justify-start">
                    <div className="w-44">
                        <Select
                            value={filters.category || "all"}
                            onValueChange={(val) => change({ category: val === "all" ? "" : val })}
                        >
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Categories" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Asset Categories</SelectItem>
                                {categories.map((c) => (
                                    <SelectItem key={c.id} value={c.id} className="text-xs">
                                        {c.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <div className="w-40">
                        <Select
                            value={filters.status || "all"}
                            onValueChange={(val) => change({ status: val === "all" ? "" : (val as AssetStatus) })}
                        >
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Statuses" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Lifecycle States</SelectItem>
                                {STATUSES.map((s) => (
                                    <SelectItem key={s} value={s} className="text-xs">
                                        {ASSET_STATUS_LABELS[s]}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    <Button
                        type="button"
                        onClick={() => change({ search: searchText.trim() })}
                        size="sm"
                        className="h-9 px-3 text-xs bg-slate-900 dark:bg-white text-white dark:text-slate-900 font-semibold rounded-lg"
                    >
                        Filter
                    </Button>
                </div>
            </div>

            {/* 4. Table */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load assets. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyState
                    icon={<Laptop className="h-14 w-14 text-slate-200 dark:text-slate-700 mb-3" />}
                    title={filters.search || filters.status || filters.category ? "No assets matched your search" : "No institutional assets registered yet"}
                    titleAs="h3"
                    description={
                        filters.search || filters.status || filters.category
                            ? "Try adjusting your search criteria or clearing your filters."
                            : "Register computers, laboratory apparatus, classroom projectors, and library furniture to track custody."
                    }
                    action={
                        !(filters.search || filters.status || filters.category) && canManage ? (
                            <Button
                                onClick={() => setRegisterOpen(true)}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Register First Asset</span>
                            </Button>
                        ) : undefined
                    }
                />
            ) : (
                <div className="space-y-4">
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Asset Tag & Name
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Category
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Custodian & Location
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Condition
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Lifecycle State
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Capital Cost
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {rows.map((a) => (
                                    <TableRow
                                        key={a.id}
                                        className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                    >
                                        {/* Tag & Name */}
                                        <TableCell className="py-3.5 pl-4">
                                            <div className="font-semibold text-xs text-slate-900 dark:text-slate-100 flex items-center gap-2">
                                                <span>{a.name}</span>
                                                <code className="text-[10px] font-mono text-sky-600 dark:text-sky-400 bg-sky-50 dark:bg-sky-950/60 px-1 py-0.2 rounded border border-sky-200 dark:border-sky-800 font-bold">
                                                    {a.tag}
                                                </code>
                                            </div>
                                            {a.serial_number && (
                                                <div className="text-[10px] text-slate-400 font-mono mt-0.5">
                                                    SN: {a.serial_number}
                                                </div>
                                            )}
                                        </TableCell>

                                        {/* Category */}
                                        <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-400 font-medium">
                                            {a.category_name}
                                        </TableCell>

                                        {/* Custodian & Location */}
                                        <TableCell className="py-3.5">
                                            <div className="space-y-0.5">
                                                {a.current_assignment?.staff_name ? (
                                                    <div className="text-xs font-medium text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                                                        <User className="w-3 h-3 text-slate-400" />
                                                        <span>{a.current_assignment.staff_name}</span>
                                                    </div>
                                                ) : a.location_name ? (
                                                    <div className="text-xs font-medium text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                                        <MapPin className="w-3 h-3 text-slate-400" />
                                                        <span>{a.location_name}</span>
                                                    </div>
                                                ) : (
                                                    <span className="text-xs text-slate-400">Unassigned</span>
                                                )}
                                            </div>
                                        </TableCell>

                                        {/* Condition */}
                                        <TableCell className="py-3.5">
                                            <Badge variant="outline" className="text-[10px] font-medium capitalize border-slate-300">
                                                {ASSET_CONDITION_LABELS[a.condition] || a.condition}
                                            </Badge>
                                        </TableCell>

                                        {/* Status */}
                                        <TableCell className="py-3.5">
                                            <AssetStatusBadge status={a.status} />
                                        </TableCell>

                                        {/* Cost */}
                                        <TableCell className="py-3.5 text-xs font-bold text-slate-900 dark:text-white">
                                            {a.purchase_cost ? formatIndianCurrency(a.purchase_cost) : "—"}
                                        </TableCell>

                                        {/* Actions */}
                                        <TableCell className="py-3.5 pr-4 text-right">
                                            <Link href={`/dashboard/inventory/assets/${a.id}`}>
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    className="h-8 px-2.5 text-xs text-sky-600 hover:text-sky-700 hover:bg-sky-50 dark:hover:bg-sky-950/40 rounded-lg cursor-pointer"
                                                >
                                                    <span>View Asset</span>
                                                    <ChevronRight className="w-3.5 h-3.5 ml-1" />
                                                </Button>
                                            </Link>
                                        </TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableShell>

                    {/* Pagination */}
                    {totalCount > PAGE_SIZE && (
                        <div className="pt-2">
                            <Pagination
                                page={filters.page}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={(p) => setFilters((f) => ({ ...f, page: p }))}
                            />
                        </div>
                    )}
                </div>
            )}

            {/* Register Asset Dialog */}
            <AssetFormDialog
                asset={null}
                open={registerOpen}
                onClose={() => {
                    setRegisterOpen(false);
                    refetch();
                }}
            />
        </div>
    );
}
