"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { AssetFormDialog } from "@/components/dashboard/inventory/AssetDialogs";
import { AssetStatusBadge, FILTER_SELECT_CLASS, PageHeader, Pager, formatMoney } from "@/components/dashboard/inventory/shared";
import { useAllOf, useAssetSummary, useAssets } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import { ASSET_STATUS_LABELS, AssetCategory, AssetFilters, AssetStatus } from "@/types/Inventory";

const STATUSES = Object.keys(ASSET_STATUS_LABELS) as AssetStatus[];

function SummaryCards() {
    const { data } = useAssetSummary();
    if (!data) return null;
    return (
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <div className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 md:col-span-1">
                <p className="text-xs text-slate-500">Total</p>
                <p className="text-2xl font-bold">{data.total}</p>
            </div>
            {STATUSES.map((s) => (
                <div key={s} className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4">
                    <p className="text-xs text-slate-500">{ASSET_STATUS_LABELS[s]}</p>
                    <p className="text-2xl font-bold">{data.by_status[s] ?? 0}</p>
                </div>
            ))}
            <p className="col-span-2 md:col-span-6 text-xs text-slate-500">
                Purchase cost of assets still in service: <strong>{formatMoney(data.purchase_cost_in_service)}</strong>
            </p>
        </div>
    );
}

export default function AssetsPage() {
    const { can } = usePermissions();
    const [filters, setFilters] = useState<AssetFilters>({ page: 1, status: "", category: "", search: "" });
    const [searchText, setSearchText] = useState("");
    const [registerOpen, setRegisterOpen] = useState(false);
    const categories = useAllOf<AssetCategory>("asset-categories");
    const { data, isLoading, isError, refetch } = useAssets(filters);

    if (!can("view_assets")) return <ErrorState message="You do not have permission to view assets." />;

    const change = (patch: Partial<AssetFilters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Assets"
                description="Durable items tracked one by one: who has them, where they are and what state they are in."
                actions={can("manage_assets") && <Button onClick={() => setRegisterOpen(true)}>Register asset</Button>}
            />
            <SummaryCards />

            <FilterBar onSubmit={() => change({ search: searchText.trim() })}>
                <Input aria-label="Search tag, name or serial number" className="w-full sm:w-64" placeholder="Search tag, name or serial number" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Status" className={FILTER_SELECT_CLASS} value={filters.status} onChange={(e) => change({ status: e.target.value as AssetStatus | "" })}>
                    <option value="">All statuses</option>
                    {STATUSES.map((s) => <option key={s} value={s}>{ASSET_STATUS_LABELS[s]}</option>)}
                </select>
                <select aria-label="Category" className={FILTER_SELECT_CLASS} value={filters.category} onChange={(e) => change({ category: e.target.value })}>
                    <option value="">All categories</option>
                    {(categories.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load assets. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={filters.search || filters.status || filters.category ? "No assets match your search." : "No assets registered yet."}
                    hint={filters.search || filters.status || filters.category ? "Try a different word or clear the filters." : "Assets are things like computers, projectors and furniture that you keep track of one by one."}
                    action={!(filters.search || filters.status || filters.category) && can("manage_assets") ? <Button onClick={() => setRegisterOpen(true)}>Register your first asset</Button> : undefined}
                />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {rows.map((a) => (
                        <Link key={a.id} href={`/dashboard/inventory/assets/${a.id}`} className="block p-4 transition-colors hover:bg-slate-50 dark:hover:bg-slate-800/50">
                            <div className="flex flex-wrap items-center gap-2">
                                <span className="font-semibold text-slate-800 dark:text-slate-200">{a.name}</span>
                                <AssetStatusBadge status={a.status} />
                            </div>
                            <p className="text-xs text-slate-500 mt-1">
                                {a.tag} - {a.category_name}
                                {a.location_name ? ` - at ${a.location_name}` : ""}
                                {a.current_assignment ? ` - with ${a.current_assignment.staff_name || a.current_assignment.location_name || a.current_assignment.note}` : ""}
                            </p>
                        </Link>
                    ))}
                </div>
            )}

            <Pager data={data} page={filters.page} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
            <AssetFormDialog asset={null} open={registerOpen} onClose={() => setRegisterOpen(false)} />
        </div>
    );
}
