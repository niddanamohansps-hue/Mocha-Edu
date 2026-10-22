"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ItemDialog, STOCK_ACTION_LABELS, StockActionDialog } from "@/components/dashboard/inventory/StockDialogs";
import { FILTER_SELECT_CLASS, LowStockBadge, PageHeader, Pager, Pill, formatQuantity } from "@/components/dashboard/inventory/shared";
import { useAllOf, useItems, useStockLevels } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import { InventoryItem, ItemCategory, StockActionKind } from "@/types/Inventory";

const ACTIONS: { action: StockActionKind; permission: string }[] = [
    { action: "receive", permission: "receive_stock" },
    { action: "issue", permission: "issue_stock" },
    { action: "return", permission: "issue_stock" },
    { action: "transfer", permission: "issue_stock" },
    { action: "adjust", permission: "adjust_stock" },
    { action: "write-off", permission: "adjust_stock" },
];

function ItemLocations({ itemId, unit }: { itemId: string; unit: string }) {
    const { data, isLoading } = useStockLevels(itemId);
    if (isLoading) return <p className="text-xs text-slate-500">Loading locations...</p>;
    const rows = data?.results ?? [];
    if (rows.length === 0) return <p className="text-xs text-slate-500">No stock in any location.</p>;
    return (
        <ul className="text-xs text-slate-600 dark:text-slate-400 flex flex-wrap gap-x-4 gap-y-1">
            {rows.map((row) => (
                <li key={row.id}>
                    {row.location_name}: <strong>{formatQuantity(row.quantity)}</strong> {unit}
                </li>
            ))}
        </ul>
    );
}

export default function StockPage() {
    const { can } = usePermissions();
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [category, setCategory] = useState("");
    const [lowStock, setLowStock] = useState(false);
    const [active, setActive] = useState<"" | "true" | "false">("true");
    const [expanded, setExpanded] = useState<string | null>(null);
    const [dialogItem, setDialogItem] = useState<InventoryItem | null>(null);
    const [itemDialogOpen, setItemDialogOpen] = useState(false);
    const [stockAction, setStockAction] = useState<{ item: InventoryItem; action: StockActionKind } | null>(null);

    const categories = useAllOf<ItemCategory>("categories");
    const { data, isLoading, isError, refetch } = useItems({ page, search, category, low_stock: lowStock, is_active: active });
    if (!can("view_inventory")) return <ErrorState message="You do not have permission to view stock." />;

    const items = data?.results ?? [];
    const canManage = can("manage_inventory_items");
    const allowedActions = ACTIONS.filter((a) => can(a.permission));
    const filtered = !!(search || category || lowStock || active !== "true");

    return (
        <div className="space-y-6">
            <PageHeader
                title="Stock"
                description="Supplies the school uses up. Quantities are the total across all locations."
                actions={
                    canManage && (
                        <Button onClick={() => { setDialogItem(null); setItemDialogOpen(true); }}>Add item</Button>
                    )
                }
            />

            <FilterBar
                onSubmit={() => {
                    setPage(1);
                    setSearch(searchText.trim());
                }}
            >
                <Input aria-label="Search name or SKU" className="w-full sm:w-64" placeholder="Search name or SKU" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Category" className={FILTER_SELECT_CLASS} value={category} onChange={(e) => { setPage(1); setCategory(e.target.value); }}>
                    <option value="">All categories</option>
                    {(categories.data ?? []).map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                </select>
                <select aria-label="Active" className={FILTER_SELECT_CLASS} value={active} onChange={(e) => { setPage(1); setActive(e.target.value as "" | "true" | "false"); }}>
                    <option value="true">Active items</option>
                    <option value="false">Inactive items</option>
                    <option value="">All items</option>
                </select>
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={lowStock} onChange={(e) => { setPage(1); setLowStock(e.target.checked); }} />
                    Low stock only
                </label>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load the stock list. Please try again." onRetry={refetch} />
            ) : items.length === 0 ? (
                <EmptyHint
                    title={filtered ? "No items match your search." : "No items yet."}
                    hint={filtered ? "Try a different word or clear the filters." : "Items are supplies you use up, like paper or chalk. First add a category and a location on the Setup tab, then add your first item here."}
                    action={!filtered && canManage ? <Button onClick={() => { setDialogItem(null); setItemDialogOpen(true); }}>Add your first item</Button> : undefined}
                />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {items.map((item) => (
                        <div key={item.id} className="p-4 space-y-2">
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                                <button
                                    type="button"
                                    className="text-left"
                                    aria-expanded={expanded === item.id}
                                    onClick={() => setExpanded(expanded === item.id ? null : item.id)}
                                >
                                    <span className="font-semibold text-slate-800 dark:text-slate-200">{item.name}</span>
                                    <span className="ml-2 text-xs text-slate-500">{item.sku} - {item.category_name}</span>
                                </button>
                                {item.low_stock && <LowStockBadge />}
                                {!item.is_active && <Pill className="bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400">Inactive</Pill>}
                                <span className="ml-auto text-sm">
                                    <strong>{formatQuantity(item.on_hand)}</strong> {item.unit}
                                    {Number(item.reorder_level) > 0 && (
                                        <span className="text-xs text-slate-500"> (reorder at {formatQuantity(item.reorder_level)})</span>
                                    )}
                                </span>
                            </div>
                            {expanded === item.id && <ItemLocations itemId={item.id} unit={item.unit} />}
                            {(allowedActions.length > 0 || canManage) && item.is_active && (
                                <div className="flex flex-wrap gap-2">
                                    {allowedActions.map(({ action }) => (
                                        <Button key={action} size="sm" variant="outline" onClick={() => setStockAction({ item, action })}>
                                            {STOCK_ACTION_LABELS[action]}
                                        </Button>
                                    ))}
                                    {canManage && (
                                        <Button size="sm" variant="ghost" onClick={() => { setDialogItem(item); setItemDialogOpen(true); }}>
                                            Edit item
                                        </Button>
                                    )}
                                </div>
                            )}
                            {canManage && !item.is_active && (
                                <Button size="sm" variant="ghost" onClick={() => { setDialogItem(item); setItemDialogOpen(true); }}>
                                    Edit item
                                </Button>
                            )}
                        </div>
                    ))}
                </div>
            )}

            <Pager data={data} page={page} onPage={setPage} />

            <ItemDialog item={dialogItem} open={itemDialogOpen} onOpenChange={setItemDialogOpen} />
            <StockActionDialog item={stockAction?.item ?? null} action={stockAction?.action ?? null} onClose={() => setStockAction(null)} />
        </div>
    );
}
