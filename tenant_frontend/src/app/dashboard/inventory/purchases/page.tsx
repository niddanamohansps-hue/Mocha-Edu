"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/feedback/EmptyState";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FILTER_SELECT_CLASS, FormDialog, PageHeader, Pager, Pill, formatDate, formatMoney, formatQuantity } from "@/components/dashboard/inventory/shared";
import { inventoryErrorMessage, useAllOf, useCancelPurchase, usePurchases } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import { Purchase, PurchaseFilters, Supplier } from "@/types/Inventory";

function CancelDialog({ purchase, onClose }: { purchase: Purchase | null; onClose: () => void }) {
    const cancel = useCancelPurchase();
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    if (!purchase) return null;
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title="Cancel this purchase"
            description="The stock it brought in is taken back out. This is refused if any of that stock has already been used."
            submitLabel="Cancel purchase"
            pending={cancel.isPending}
            error={error}
            onSubmit={() => {
                if (!reason.trim()) return setError("A reason is required.");
                setError(null);
                cancel.mutate(
                    { id: purchase.id, reason: reason.trim() },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not cancel the purchase")) }
                );
            }}
        >
            <Field label="Reason" htmlFor="cancel-reason">
                <Input id="cancel-reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
            </Field>
        </FormDialog>
    );
}

export default function PurchasesPage() {
    const { can } = usePermissions();
    const [filters, setFilters] = useState<PurchaseFilters>({ page: 1, supplier: "", status: "", search: "" });
    const [searchText, setSearchText] = useState("");
    const [expanded, setExpanded] = useState<string | null>(null);
    const [cancelling, setCancelling] = useState<Purchase | null>(null);
    const suppliers = useAllOf<Supplier>("suppliers");
    const { data, isLoading, isError, refetch } = usePurchases(filters);

    if (!can("view_inventory")) return <ErrorState message="You do not have permission to view purchases." />;

    const change = (patch: Partial<PurchaseFilters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Purchases"
                description="Stock bought from suppliers. Recording a purchase receives all of its items at once."
                actions={can("receive_stock") && <Button asChild><Link href="/dashboard/inventory/purchases/new">Record purchase</Link></Button>}
            />

            <form className="flex flex-wrap gap-3" onSubmit={(e) => { e.preventDefault(); change({ search: searchText.trim() }); }}>
                <Input className="w-full sm:w-64" placeholder="Search reference, supplier or item" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Supplier" className={FILTER_SELECT_CLASS} value={filters.supplier} onChange={(e) => change({ supplier: e.target.value })}>
                    <option value="">All suppliers</option>
                    {(suppliers.data ?? []).map((s) => (
                        <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                </select>
                <select aria-label="Status" className={FILTER_SELECT_CLASS} value={filters.status} onChange={(e) => change({ status: e.target.value as PurchaseFilters["status"] })}>
                    <option value="">All statuses</option>
                    <option value="received">Received</option>
                    <option value="cancelled">Cancelled</option>
                </select>
                <Button type="submit" variant="outline">Search</Button>
            </form>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load purchases. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyState title="No purchases recorded yet." className="py-16 text-slate-500 text-sm" />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {rows.map((p) => (
                        <div key={p.id} className="p-4 space-y-2">
                            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                                <button type="button" className="text-left" aria-expanded={expanded === p.id} onClick={() => setExpanded(expanded === p.id ? null : p.id)}>
                                    <span className="font-semibold text-slate-800 dark:text-slate-200">{p.supplier_name}</span>
                                    <span className="ml-2 text-xs text-slate-500">
                                        {formatDate(p.purchase_date)}{p.reference ? ` - ${p.reference}` : ""} - into {p.location_name}
                                    </span>
                                </button>
                                {p.status === "cancelled" && <Pill className="bg-red-100 text-red-700 dark:bg-red-500/10 dark:text-red-400">Cancelled</Pill>}
                                <span className="ml-auto text-sm font-bold">{formatMoney(p.total_cost)}</span>
                                {p.status === "received" && can("adjust_stock") && (
                                    <Button size="sm" variant="outline" onClick={() => setCancelling(p)}>Cancel</Button>
                                )}
                            </div>
                            {expanded === p.id && (
                                <div className="text-xs text-slate-600 dark:text-slate-400 space-y-1">
                                    {p.lines.map((line) => (
                                        <p key={line.id}>
                                            {line.item_name} ({line.item_sku}): {formatQuantity(line.quantity)} x {formatMoney(line.unit_cost)} = {formatMoney(line.line_total)}
                                        </p>
                                    ))}
                                    {p.notes && <p>Notes: {p.notes}</p>}
                                    {p.status === "cancelled" && <p>Cancelled: {p.cancellation_reason}</p>}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            <Pager data={data} page={filters.page} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
            <CancelDialog key={cancelling?.id ?? "none"} purchase={cancelling} onClose={() => setCancelling(null)} />
        </div>
    );
}
