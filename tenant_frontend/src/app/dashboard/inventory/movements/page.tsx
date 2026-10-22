"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FILTER_SELECT_CLASS, FormDialog, PageHeader, Pager, Pill, formatDateTime, formatQuantity } from "@/components/dashboard/inventory/shared";
import { inventoryErrorMessage, useAllOf, useMovements, useReverseMovement } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import { MOVEMENT_LABELS, MovementFilters, MovementKind, StockLocation, StockMovement } from "@/types/Inventory";

function ReverseDialog({ movement, onClose }: { movement: StockMovement | null; onClose: () => void }) {
    const reverse = useReverseMovement();
    const [reason, setReason] = useState("");
    const [error, setError] = useState<string | null>(null);
    if (!movement) return null;
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title="Reverse this movement"
            description={`${MOVEMENT_LABELS[movement.kind]} ${formatQuantity(movement.quantity_delta)} of ${movement.item_name}. A new opposite entry is added; the original stays in the history.`}
            submitLabel="Reverse movement"
            pending={reverse.isPending}
            error={error}
            onSubmit={() => {
                if (!reason.trim()) return setError("A reason is required.");
                setError(null);
                reverse.mutate(
                    { id: movement.id, reason: reason.trim() },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not reverse the movement")) }
                );
            }}
        >
            <Field label="Reason" htmlFor="rev-reason">
                <Input id="rev-reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
            </Field>
        </FormDialog>
    );
}

// Transfers and reversals cannot be reversed; neither can stock that came in with a purchase (cancel the purchase).
const NOT_REVERSIBLE: MovementKind[] = ["transfer_in", "transfer_out", "reversal"];

export default function MovementsPage() {
    const { can } = usePermissions();
    const [filters, setFilters] = useState<MovementFilters>({ page: 1, item: "", location: "", kind: "", search: "" });
    const [searchText, setSearchText] = useState("");
    const [reversing, setReversing] = useState<StockMovement | null>(null);
    const locations = useAllOf<StockLocation>("locations");
    const { data, isLoading, isError, refetch } = useMovements(filters);

    if (!can("view_inventory")) return <ErrorState message="You do not have permission to view stock movements." />;

    const change = (patch: Partial<MovementFilters>) => setFilters((f) => ({ ...f, page: 1, ...patch }));
    const rows = data?.results ?? [];
    const canReverse = can("adjust_stock");

    return (
        <div className="space-y-6">
            <PageHeader title="Movements" description="Every change to stock, newest first. Entries are never edited or deleted." />

            <FilterBar onSubmit={() => change({ search: searchText.trim() })}>
                <Input aria-label="Search item, reference or reason" className="w-full sm:w-64" placeholder="Search item, reference or reason" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Kind" className={FILTER_SELECT_CLASS} value={filters.kind} onChange={(e) => change({ kind: e.target.value as MovementKind | "" })}>
                    <option value="">All kinds</option>
                    {(Object.keys(MOVEMENT_LABELS) as MovementKind[]).map((k) => (
                        <option key={k} value={k}>{MOVEMENT_LABELS[k]}</option>
                    ))}
                </select>
                <select aria-label="Location" className={FILTER_SELECT_CLASS} value={filters.location} onChange={(e) => change({ location: e.target.value })}>
                    <option value="">All locations</option>
                    {(locations.data ?? []).map((l) => (
                        <option key={l.id} value={l.id}>{l.name}</option>
                    ))}
                </select>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load movements. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint title="No stock movements yet." hint="Every time stock is received, issued or corrected it is listed here. Start on the Stock tab by receiving some stock." />
            ) : (
                <div className="rounded-2xl border border-slate-200 dark:border-slate-800 divide-y divide-slate-100 dark:divide-slate-800 overflow-hidden">
                    {rows.map((m) => {
                        const positive = Number(m.quantity_delta) > 0;
                        const reversible = canReverse && !m.reversed && !NOT_REVERSIBLE.includes(m.kind);
                        return (
                            <div key={m.id} className="p-4 flex flex-wrap items-center gap-x-4 gap-y-2">
                                <div className="min-w-0 flex-1">
                                    <p className="font-semibold text-slate-800 dark:text-slate-200">
                                        {m.item_name}
                                        <span className="ml-2 text-xs font-normal text-slate-500">{m.location_name}</span>
                                    </p>
                                    <p className="text-xs text-slate-500 mt-0.5">
                                        {MOVEMENT_LABELS[m.kind]} - {formatDateTime(m.created_at)}
                                        {m.reference ? ` - ref ${m.reference}` : ""}
                                        {m.issued_to_note ? ` - to ${m.issued_to_note}` : ""}
                                        {m.reason ? ` - ${m.reason}` : ""}
                                        {m.unit_cost ? ` - cost ${m.unit_cost} each` : ""}
                                    </p>
                                </div>
                                {m.reversed && <Pill className="bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400">Reversed</Pill>}
                                <div className="text-right text-sm">
                                    <p className={positive ? "font-bold text-emerald-600" : "font-bold text-red-600"}>
                                        {positive ? "+" : ""}{formatQuantity(m.quantity_delta)}
                                    </p>
                                    <p className="text-xs text-slate-500">balance {formatQuantity(m.balance_after)}</p>
                                </div>
                                {reversible && (
                                    <Button size="sm" variant="outline" onClick={() => setReversing(m)}>Reverse</Button>
                                )}
                            </div>
                        );
                    })}
                </div>
            )}

            <Pager data={data} page={filters.page} onPage={(page) => setFilters((f) => ({ ...f, page }))} />
            <ReverseDialog key={reversing?.id ?? "none"} movement={reversing} onClose={() => setReversing(null)} />
        </div>
    );
}
