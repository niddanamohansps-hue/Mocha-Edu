"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/feedback/ErrorState";
import { Field, PageHeader, SELECT_CLASS, formatMoney, isNonNegativeDecimal, isPositiveDecimal } from "@/components/dashboard/inventory/shared";
import { inventoryErrorMessage, useAllOf, useCreatePurchase } from "@/hooks/useInventory";
import { usePermissions } from "@/providers/PermissionProvider";
import { InventoryItem, StockLocation, Supplier } from "@/types/Inventory";

interface LineDraft {
    key: number;
    item: string;
    quantity: string;
    unit_cost: string;
}

const MAX_LINES = 200;

/** Quantity x cost in whole paisa-style hundredths using integers, so the total never has float drift. */
function lineTotalHundredths(quantity: string, cost: string) {
    if (!isPositiveDecimal(quantity) || !isNonNegativeDecimal(cost)) return null;
    const [qWhole, qFraction = ""] = quantity.trim().split(".");
    const [cWhole, cFraction = ""] = cost.trim().split(".");
    const q = BigInt(qWhole + qFraction.padEnd(3, "0")); // thousandths
    const c = BigInt(cWhole + cFraction.padEnd(2, "0")); // hundredths
    const product = q * c; // hundred-thousandths
    return (product + BigInt(500)) / BigInt(1000); // hundredths, rounded half up
}

function hundredthsToString(value: bigint) {
    const text = value.toString().padStart(3, "0");
    return `${text.slice(0, -2)}.${text.slice(-2)}`;
}

export default function NewPurchasePage() {
    const router = useRouter();
    const { can } = usePermissions();
    const suppliers = useAllOf<Supplier>("suppliers", { is_active: "true" });
    const locations = useAllOf<StockLocation>("locations", { is_active: "true" });
    const items = useAllOf<InventoryItem>("items", { is_active: "true" });
    const create = useCreatePurchase();
    const [supplier, setSupplier] = useState("");
    const [location, setLocation] = useState("");
    const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
    const [reference, setReference] = useState("");
    const [notes, setNotes] = useState("");
    const [lines, setLines] = useState<LineDraft[]>([{ key: 1, item: "", quantity: "", unit_cost: "" }]);
    const [nextKey, setNextKey] = useState(2);
    const [error, setError] = useState<string | null>(null);

    if (!can("receive_stock")) return <ErrorState message="You do not have permission to record purchases." />;

    const update = (key: number, patch: Partial<LineDraft>) =>
        setLines((rows) => rows.map((row) => (row.key === key ? { ...row, ...patch } : row)));
    const total = lines.reduce((sum, line) => sum + (lineTotalHundredths(line.quantity, line.unit_cost) ?? BigInt(0)), BigInt(0));

    const submit = () => {
        if (!supplier || !location || !date) return setError("Choose a supplier, a location and a date.");
        const chosen = lines.map((l) => l.item);
        if (chosen.some((id) => !id)) return setError("Choose an item on every line (or remove the empty line).");
        if (new Set(chosen).size !== chosen.length) return setError("Each item can appear only once in a purchase.");
        for (const [index, line] of lines.entries()) {
            if (!isPositiveDecimal(line.quantity)) return setError(`Line ${index + 1}: enter a quantity above 0.`);
            if (!isNonNegativeDecimal(line.unit_cost)) return setError(`Line ${index + 1}: enter the unit cost (0 or more).`);
        }
        setError(null);
        create.mutate(
            {
                supplier, location, purchase_date: date, reference: reference.trim(), notes: notes.trim(),
                lines: lines.map((l) => ({ item: l.item, quantity: l.quantity.trim(), unit_cost: l.unit_cost.trim() })),
            },
            {
                onSuccess: () => router.push("/dashboard/inventory/purchases"),
                onError: (e) => setError(inventoryErrorMessage(e, "Could not record the purchase")),
            }
        );
    };

    return (
        <form
            className="space-y-6 max-w-3xl"
            onSubmit={(e) => {
                e.preventDefault();
                submit();
            }}
        >
            <PageHeader title="Record purchase" description="All items are received into one location when you save." />

            <div className="grid sm:grid-cols-2 gap-4">
                <Field label="Supplier" htmlFor="p-supplier">
                    <select id="p-supplier" className={SELECT_CLASS} value={supplier} onChange={(e) => setSupplier(e.target.value)}>
                        <option value="">Choose a supplier</option>
                        {(suppliers.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                </Field>
                <Field label="Receive into" htmlFor="p-location">
                    <select id="p-location" className={SELECT_CLASS} value={location} onChange={(e) => setLocation(e.target.value)}>
                        <option value="">Choose a location</option>
                        {(locations.data ?? []).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                    </select>
                </Field>
                <Field label="Purchase date" htmlFor="p-date">
                    <Input id="p-date" type="date" value={date} onChange={(e) => setDate(e.target.value)} />
                </Field>
                <Field label="Invoice / order number" htmlFor="p-reference">
                    <Input id="p-reference" value={reference} maxLength={100} onChange={(e) => setReference(e.target.value)} />
                </Field>
            </div>
            <Field label="Notes" htmlFor="p-notes">
                <Input id="p-notes" value={notes} maxLength={255} onChange={(e) => setNotes(e.target.value)} />
            </Field>

            <div className="space-y-3">
                <h2 className="font-semibold text-slate-800 dark:text-slate-200">Items</h2>
                {lines.map((line, index) => {
                    const item = (items.data ?? []).find((i) => i.id === line.item);
                    const lineTotal = lineTotalHundredths(line.quantity, line.unit_cost);
                    return (
                        <div key={line.key} className="grid grid-cols-12 gap-2 items-end rounded-xl border border-slate-200 dark:border-slate-800 p-3">
                            <div className="col-span-12 sm:col-span-5">
                                <Field label={`Item ${index + 1}`} htmlFor={`l-item-${line.key}`}>
                                    <select id={`l-item-${line.key}`} className={SELECT_CLASS} value={line.item} onChange={(e) => update(line.key, { item: e.target.value })}>
                                        <option value="">Choose an item</option>
                                        {(items.data ?? []).map((i) => <option key={i.id} value={i.id}>{i.name} ({i.sku})</option>)}
                                    </select>
                                </Field>
                            </div>
                            <div className="col-span-5 sm:col-span-2">
                                <Field label={item ? `Qty (${item.unit})` : "Qty"} htmlFor={`l-qty-${line.key}`}>
                                    <Input id={`l-qty-${line.key}`} inputMode="decimal" value={line.quantity} onChange={(e) => update(line.key, { quantity: e.target.value })} />
                                </Field>
                            </div>
                            <div className="col-span-5 sm:col-span-2">
                                <Field label="Unit cost" htmlFor={`l-cost-${line.key}`}>
                                    <Input id={`l-cost-${line.key}`} inputMode="decimal" value={line.unit_cost} onChange={(e) => update(line.key, { unit_cost: e.target.value })} />
                                </Field>
                            </div>
                            <div className="col-span-2 sm:col-span-2 text-right text-sm font-semibold pb-2">
                                {lineTotal === null ? "-" : formatMoney(hundredthsToString(lineTotal))}
                            </div>
                            <div className="col-span-12 sm:col-span-1 text-right">
                                {lines.length > 1 && (
                                    <Button type="button" variant="ghost" size="sm" onClick={() => setLines((rows) => rows.filter((r) => r.key !== line.key))}>
                                        Remove
                                    </Button>
                                )}
                            </div>
                        </div>
                    );
                })}
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <Button
                        type="button"
                        variant="outline"
                        disabled={lines.length >= MAX_LINES}
                        onClick={() => {
                            setLines((rows) => [...rows, { key: nextKey, item: "", quantity: "", unit_cost: "" }]);
                            setNextKey((k) => k + 1);
                        }}
                    >
                        Add another item
                    </Button>
                    <p className="text-sm">Total <strong>{formatMoney(hundredthsToString(total))}</strong></p>
                </div>
            </div>

            {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-3">
                <Button type="submit" disabled={create.isPending}>{create.isPending ? "Saving..." : "Record purchase and receive stock"}</Button>
                <Button asChild variant="outline"><Link href="/dashboard/inventory/purchases">Back</Link></Button>
            </div>
        </form>
    );
}
