"use client";

import { useState, useMemo } from "react";
import {
    Package,
    Plus,
    Search,
    X,
    AlertTriangle,
    Layers,
    MapPin,
    ArrowDownRight,
    ArrowUpRight,
    RotateCcw,
    SlidersHorizontal,
    CheckCircle2,
    ShieldAlert,
    Pencil,
    ChevronDown,
    Building2,
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
    TableHeadNumeric,
    TableCellNumeric,
    TableCellAction,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ItemDialog, STOCK_ACTION_LABELS, StockActionDialog } from "@/components/dashboard/inventory/StockDialogs";
import { formatQuantity } from "@/components/dashboard/inventory/shared";
import { useAllOf, useItems, useStockLevels } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import { InventoryItem, ItemCategory, StockActionKind } from "@/types/Inventory";

const PAGE_SIZE = 20;

const ACTIONS: { action: StockActionKind; permission: string; label: string }[] = [
    { action: "receive", permission: "receive_stock", label: "Receive" },
    { action: "issue", permission: "issue_stock", label: "Issue" },
    { action: "return", permission: "issue_stock", label: "Return" },
    { action: "transfer", permission: "issue_stock", label: "Transfer" },
    { action: "adjust", permission: "adjust_stock", label: "Adjust" },
];

function ItemLocations({ itemId, unit }: { itemId: string; unit: string }) {
    const { data, isLoading } = useStockLevels(itemId);
    if (isLoading) return <span className="text-[10px] text-slate-400">Loading locations...</span>;
    const rows = data?.results ?? [];
    if (rows.length === 0) return <span className="text-[10px] text-slate-400">No stock in warehouse locations.</span>;
    return (
        <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {rows.map((row) => (
                <span
                    key={row.id}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] font-medium text-slate-700 dark:text-slate-300"
                >
                    <MapPin className="w-2.5 h-2.5 text-slate-400" />
                    <span>{row.location_name}:</span>
                    <strong className="text-slate-900 dark:text-white font-bold">{formatQuantity(row.quantity)}</strong>
                    <span className="text-slate-400">{unit}</span>
                </span>
            ))}
        </div>
    );
}

export default function StockPage() {
    const { can } = usePermissions();
    if (!can("view_inventory")) {
        return <ErrorState message="You do not have permission to view stock inventory." />;
    }
    return <StockPageContent />;
}

function StockPageContent() {
    const { can } = usePermissions();
    const canManage = can("manage_inventory_items");

    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [category, setCategory] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "active" | "low_stock">("active");

    const [expanded, setExpanded] = useState<string | null>(null);
    const [dialogItem, setDialogItem] = useState<InventoryItem | null>(null);
    const [itemDialogOpen, setItemDialogOpen] = useState(false);
    const [stockAction, setStockAction] = useState<{ item: InventoryItem; action: StockActionKind } | null>(null);

    const categoriesQuery = useAllOf<ItemCategory>("categories");
    const categories = categoriesQuery.data ?? [];

    const { data, isLoading, isError, refetch } = useItems({
        page,
        search: search.trim(),
        category: category || "",
        low_stock: statusFilter === "low_stock",
        is_active: statusFilter === "active" ? "true" : "",
    });

    const items = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    // Metrics
    const metrics = useMemo(() => {
        const total = totalCount;
        const activeItems = items.filter((i) => i.is_active).length;
        const lowStockCount = items.filter((i) => i.low_stock).length;
        const categoryCount = categories.length;
        return { total, activeItems, lowStockCount, categoryCount };
    }, [items, totalCount, categories]);

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Package className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Institutional Inventory & Consumable Stock</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Campus supplies inventory, warehouse room levels, low-stock reorder thresholds, and stock allocation actions
                    </p>
                </div>

                {canManage && (
                    <Button
                        onClick={() => {
                            setDialogItem(null);
                            setItemDialogOpen(true);
                        }}
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Add Stock Item</span>
                    </Button>
                )}
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Items */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Catalog Items</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Package className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.total}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">SKUs tracked</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Across campus storage depots
                    </p>
                </div>

                {/* Active in Service */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Active Stock Items</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.activeItems}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            active supply
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Available for requisition
                    </p>
                </div>

                {/* Low Stock Alerts */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Low Stock Reorder</span>
                        <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                            <AlertTriangle className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.lowStockCount}
                        </span>
                        <span className="text-[11px] text-amber-600 dark:text-amber-400 font-semibold">
                            reorder needed
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Below minimum thresholds
                    </p>
                </div>

                {/* Categories */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Item Categories</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Layers className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.categoryCount}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">classifications</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Stationery, lab, facilities, IT
                    </p>
                </div>
            </div>

            {/* 3. Search and Category Filter Controls */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col md:flex-row items-center justify-between gap-3">
                {/* Search */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search stock item by name or SKU..."
                        value={search}
                        onChange={(e) => {
                            setSearch(e.target.value);
                            setPage(1);
                        }}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                    {search && (
                        <button
                            onClick={() => {
                                setSearch("");
                                setPage(1);
                            }}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                {/* Category & Status Filter Controls */}
                <div className="flex items-center gap-2 w-full md:w-auto shrink-0 justify-between sm:justify-start">
                    {/* Category Selector */}
                    <div className="w-44">
                        <Select
                            value={category || "all"}
                            onValueChange={(val) => {
                                setCategory(val === "all" ? "" : val);
                                setPage(1);
                            }}
                        >
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Categories" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Categories</SelectItem>
                                {categories.map((c) => (
                                    <SelectItem key={c.id} value={c.id} className="text-xs">
                                        {c.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Status Funnel Pills */}
                    <div className="flex items-center gap-1 shrink-0">
                        {[
                            { value: "active", label: "Active" },
                            { value: "low_stock", label: "Low Stock" },
                            { value: "all", label: "All Items" },
                        ].map((opt) => (
                            <button
                                key={opt.value}
                                type="button"
                                onClick={() => {
                                    setStatusFilter(opt.value as any);
                                    setPage(1);
                                }}
                                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                                    statusFilter === opt.value
                                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                        : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                                }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* 4. Table */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load inventory stock. Please try again." onRetry={refetch} />
            ) : items.length === 0 ? (
                <EmptyState
                    icon={<Package className="h-14 w-14 text-slate-200 dark:text-slate-700 mb-3" />}
                    title={search || category ? "No stock items matched your search" : "No consumable stock items configured yet"}
                    titleAs="h3"
                    description={
                        search || category
                            ? "Try adjusting your search terms or selecting a different category."
                            : "Add stationery, laboratory consumables, facilities supplies, and track location quantities and reorder points."
                    }
                    action={
                        !search && !category && canManage ? (
                            <Button
                                onClick={() => {
                                    setDialogItem(null);
                                    setItemDialogOpen(true);
                                }}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Add First Stock Item</span>
                            </Button>
                        ) : undefined
                    }
                />
            ) : (
                <TableShell
                    footer={
                        totalCount > PAGE_SIZE ? (
                            <Pagination
                                page={page}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={setPage}
                            />
                        ) : undefined
                    }
                >
                    <Table>
                        <TableHeader>
                            <TableRow>
                                <TableHead className="pl-4">
                                    SKU &amp; Item Name
                                </TableHead>
                                <TableHead>
                                    Category
                                </TableHead>
                                <TableHeadNumeric>
                                    Available On-Hand
                                </TableHeadNumeric>
                                <TableHeadNumeric>
                                    Reorder Level
                                </TableHeadNumeric>
                                <TableHead>
                                    Stock Health
                                </TableHead>
                                <TableCellAction>
                                    Actions
                                </TableCellAction>
                            </TableRow>
                        </TableHeader>
                        <TableBody striped>
                            {items.map((item) => (
                                <TableRow
                                    key={item.id}
                                >
                                    {/* SKU & Item Name */}
                                    <TableCell className="pl-4">
                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100 flex items-center gap-2">
                                            <span>{item.name}</span>
                                            <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                {item.sku}
                                            </code>
                                        </div>
                                        {/* Sub-locations breakdown */}
                                        <ItemLocations itemId={item.id} unit={item.unit} />
                                    </TableCell>

                                    {/* Category */}
                                    <TableCell className="text-xs text-slate-600 dark:text-slate-400 font-medium">
                                        {item.category_name}
                                    </TableCell>

                                    {/* Available On-Hand */}
                                    <TableCellNumeric>
                                        <span className="text-xs font-bold text-slate-900 dark:text-white">
                                            {formatQuantity(item.on_hand)}
                                        </span>{" "}
                                        <span className="text-[11px] text-slate-400">{item.unit}</span>
                                    </TableCellNumeric>

                                    {/* Reorder Level */}
                                    <TableCellNumeric className="text-xs text-slate-500 font-medium">
                                        {item.reorder_level ? (
                                            <span>{formatQuantity(item.reorder_level)} {item.unit}</span>
                                        ) : (
                                            <span className="text-slate-400">—</span>
                                        )}
                                    </TableCellNumeric>

                                    {/* Stock Health */}
                                    <TableCell>
                                        {item.low_stock ? (
                                            <Badge className="bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300/80 font-semibold text-[11px]">
                                                Low Stock
                                            </Badge>
                                        ) : !item.is_active ? (
                                            <Badge variant="outline" className="text-[11px] text-slate-400 border-slate-300">
                                                Inactive
                                            </Badge>
                                        ) : (
                                            <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                                                Adequate
                                            </Badge>
                                        )}
                                    </TableCell>

                                    {/* Actions */}
                                    <TableCellAction>
                                        <div className="flex items-center justify-end gap-1">
                                            {can("receive_stock") && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => setStockAction({ item, action: "receive" })}
                                                    className="h-8 px-2 text-xs font-semibold text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 cursor-pointer"
                                                >
                                                    <ArrowDownRight className="w-3 h-3 mr-1" />
                                                    <span>Receive</span>
                                                </Button>
                                            )}
                                            {can("issue_stock") && (
                                                <Button
                                                    size="sm"
                                                    variant="outline"
                                                    onClick={() => setStockAction({ item, action: "issue" })}
                                                    className="h-8 px-2 text-xs font-semibold text-sky-600 hover:text-sky-700 hover:bg-sky-50 cursor-pointer"
                                                >
                                                    <ArrowUpRight className="w-3 h-3 mr-1" />
                                                    <span>Issue</span>
                                                </Button>
                                            )}
                                            {canManage && (
                                                <Button
                                                    size="sm"
                                                    variant="ghost"
                                                    onClick={() => {
                                                        setDialogItem(item);
                                                        setItemDialogOpen(true);
                                                    }}
                                                    className="h-8 w-8 p-0 text-slate-500 hover:text-sky-600 rounded-lg cursor-pointer"
                                                    title="Edit item"
                                                >
                                                    <Pencil className="w-3.5 h-3.5" />
                                                </Button>
                                            )}
                                        </div>
                                    </TableCellAction>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableShell>
            )}

            {/* Dialogs */}
            <ItemDialog
                open={itemDialogOpen}
                item={dialogItem}
                onOpenChange={(open) => {
                    setItemDialogOpen(open);
                    if (!open) {
                        setDialogItem(null);
                        refetch();
                    }
                }}
            />

            {stockAction && (
                <StockActionDialog
                    item={stockAction.item}
                    action={stockAction.action}
                    onClose={() => {
                        setStockAction(null);
                        refetch();
                    }}
                />
            )}
        </div>
    );
}
