"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, FormDialog, SELECT_CLASS, isNonNegativeDecimal, isPositiveDecimal } from "@/components/dashboard/inventory/shared";
import { inventoryErrorMessage, useAllOf, useSaveItem, useStockAction, useStockLevels } from "@/hooks/useInventory";
import { InventoryItem, ItemCategory, StockActionKind, StockLocation } from "@/types/Inventory";

// --- Create / edit an item ------------------------------------------------------------------------

export function ItemDialog({ item, open, onOpenChange }: { item: InventoryItem | null; open: boolean; onOpenChange: (open: boolean) => void }) {
    // The form is remounted for every open (see the `key` below), so its state always starts from `item`.
    return open ? <ItemForm key={item?.id ?? "new"} item={item} onOpenChange={onOpenChange} /> : null;
}

function ItemForm({ item, onOpenChange }: { item: InventoryItem | null; onOpenChange: (open: boolean) => void }) {
    const categories = useAllOf<ItemCategory>("categories");
    const save = useSaveItem();
    const [sku, setSku] = useState(item?.sku ?? "");
    const [name, setName] = useState(item?.name ?? "");
    const [category, setCategory] = useState(item?.category ?? "");
    const [unit, setUnit] = useState(item?.unit ?? "");
    const [reorder, setReorder] = useState(item ? item.reorder_level : "0");
    const [description, setDescription] = useState(item?.description ?? "");
    const [active, setActive] = useState(item?.is_active ?? true);
    const [error, setError] = useState<string | null>(null);

    const submit = () => {
        if (!sku.trim() || !name.trim() || !category || !unit.trim()) return setError("SKU, name, category and unit are required.");
        if (!isNonNegativeDecimal(reorder, 3)) return setError("The reorder level must be a number (up to 3 decimals), 0 or more.");
        setError(null);
        save.mutate(
            {
                id: item?.id,
                input: {
                    sku: sku.trim(), name: name.trim(), category, unit: unit.trim(), reorder_level: reorder.trim(),
                    description: description.trim(), is_active: active,
                },
            },
            { onSuccess: () => onOpenChange(false), onError: (e) => setError(inventoryErrorMessage(e, "Could not save the item")) }
        );
    };

    return (
        <FormDialog
            open
            onOpenChange={onOpenChange}
            title={item ? "Edit item" : "Add item"}
            description="Items are things the school uses up, such as chalk, paper or lab supplies."
            submitLabel={item ? "Save changes" : "Add item"}
            pending={save.isPending}
            error={error}
            onSubmit={submit}
        >
            <div className="grid grid-cols-2 gap-3">
                <Field label="SKU" htmlFor="item-sku">
                    <Input id="item-sku" value={sku} maxLength={50} onChange={(e) => setSku(e.target.value)} />
                </Field>
                <Field label="Unit" htmlFor="item-unit" hint="e.g. pcs, box, kg">
                    <Input id="item-unit" value={unit} maxLength={20} onChange={(e) => setUnit(e.target.value)} />
                </Field>
            </div>
            <Field label="Name" htmlFor="item-name">
                <Input id="item-name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Category" htmlFor="item-category">
                <select id="item-category" className={SELECT_CLASS} value={category} onChange={(e) => setCategory(e.target.value)}>
                    <option value="">Choose a category</option>
                    {(categories.data ?? []).map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                </select>
            </Field>
            <Field label="Reorder level" htmlFor="item-reorder" hint="Alert when the total falls to this amount. 0 turns it off.">
                <Input id="item-reorder" inputMode="decimal" value={reorder} onChange={(e) => setReorder(e.target.value)} />
            </Field>
            <Field label="Description" htmlFor="item-description">
                <Textarea id="item-description" value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
            {item && (
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                    Active (inactive items cannot receive or issue stock)
                </label>
            )}
        </FormDialog>
    );
}

// --- Receive / issue / return / adjust / write off / transfer ------------------------------------

export const STOCK_ACTION_LABELS: Record<StockActionKind, string> = {
    receive: "Receive stock",
    issue: "Issue stock",
    return: "Record a return",
    adjust: "Adjust count",
    "write-off": "Write off",
    transfer: "Transfer",
};

export function StockActionDialog({
    item,
    action,
    onClose,
}: {
    item: InventoryItem | null;
    action: StockActionKind | null;
    onClose: () => void;
}) {
    return item && action ? <StockActionForm key={`${item.id}-${action}`} item={item} action={action} onClose={onClose} /> : null;
}

function StockActionForm({ item, action, onClose }: { item: InventoryItem; action: StockActionKind; onClose: () => void }) {
    const locations = useAllOf<StockLocation>("locations", { is_active: "true" });
    const levels = useStockLevels(item.id);
    const run = useStockAction();
    const [location, setLocation] = useState("");
    const [toLocation, setToLocation] = useState("");
    const [quantity, setQuantity] = useState("");
    const [unitCost, setUnitCost] = useState("");
    const [reference, setReference] = useState("");
    const [reason, setReason] = useState("");
    const [issuedTo, setIssuedTo] = useState("");
    const [direction, setDirection] = useState<"in" | "out">("out");
    const [error, setError] = useState<string | null>(null);

    const onHand = new Map((levels.data?.results ?? []).map((l) => [l.location, l.quantity]));
    const needsReason = action === "adjust" || action === "write-off";

    const submit = () => {
        if (!location) return setError(action === "transfer" ? "Choose where the stock comes from." : "Choose a location.");
        if (action === "transfer" && (!toLocation || toLocation === location)) return setError("Choose a different destination.");
        if (!isPositiveDecimal(quantity)) return setError("Enter a quantity above 0 (up to 3 decimals).");
        if (action === "receive" && unitCost && !isNonNegativeDecimal(unitCost)) return setError("The unit cost must be a number, 0 or more.");
        if (needsReason && !reason.trim()) return setError("A reason is required.");
        if (action === "issue" && !issuedTo.trim()) return setError("Say who the stock is issued to.");
        setError(null);

        const base = { action, item: item.id, quantity: quantity.trim() };
        const body =
            action === "transfer"
                ? { ...base, from_location: location, to_location: toLocation, reason: reason.trim(), reference: reference.trim() }
                : {
                      ...base,
                      location,
                      reference: reference.trim(),
                      ...(action === "receive" ? { unit_cost: unitCost.trim() || undefined, reason: reason.trim() } : {}),
                      ...(action === "issue" || action === "return" ? { issued_to_note: issuedTo.trim() } : {}),
                      ...(action === "return" ? { reason: reason.trim() } : {}),
                      ...(action === "adjust" ? { direction, reason: reason.trim() } : {}),
                      ...(action === "write-off" ? { reason: reason.trim() } : {}),
                  };
        run.mutate(body, { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not update the stock")) });
    };

    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={`${STOCK_ACTION_LABELS[action]}: ${item.name}`}
            description={`${item.sku} - ${item.on_hand} ${item.unit} on hand in total`}
            submitLabel={STOCK_ACTION_LABELS[action]}
            pending={run.isPending}
            error={error}
            onSubmit={submit}
        >
            <Field label={action === "transfer" ? "From" : "Location"} htmlFor="sa-location">
                <select id="sa-location" className={SELECT_CLASS} value={location} onChange={(e) => setLocation(e.target.value)}>
                    <option value="">Choose a location</option>
                    {(locations.data ?? []).map((l) => (
                        <option key={l.id} value={l.id}>
                            {l.name}{onHand.has(l.id) ? ` (${onHand.get(l.id)} ${item.unit})` : ""}
                        </option>
                    ))}
                </select>
            </Field>
            {action === "transfer" && (
                <Field label="To" htmlFor="sa-to">
                    <select id="sa-to" className={SELECT_CLASS} value={toLocation} onChange={(e) => setToLocation(e.target.value)}>
                        <option value="">Choose a location</option>
                        {(locations.data ?? []).filter((l) => l.id !== location).map((l) => (
                            <option key={l.id} value={l.id}>{l.name}</option>
                        ))}
                    </select>
                </Field>
            )}
            {action === "adjust" && (
                <Field label="Direction" htmlFor="sa-direction">
                    <select id="sa-direction" className={SELECT_CLASS} value={direction} onChange={(e) => setDirection(e.target.value as "in" | "out")}>
                        <option value="out">Take away (count is lower)</option>
                        <option value="in">Add (count is higher)</option>
                    </select>
                </Field>
            )}
            <Field label={`Quantity (${item.unit})`} htmlFor="sa-quantity">
                <Input id="sa-quantity" inputMode="decimal" value={quantity} onChange={(e) => setQuantity(e.target.value)} />
            </Field>
            {action === "receive" && (
                <Field label="Unit cost (optional)" htmlFor="sa-cost">
                    <Input id="sa-cost" inputMode="decimal" value={unitCost} onChange={(e) => setUnitCost(e.target.value)} />
                </Field>
            )}
            {(action === "issue" || action === "return") && (
                <Field label={action === "issue" ? "Issued to" : "Returned by"} htmlFor="sa-issued" hint="A person, class or department.">
                    <Input id="sa-issued" value={issuedTo} maxLength={255} onChange={(e) => setIssuedTo(e.target.value)} />
                </Field>
            )}
            {action !== "issue" && (
                <Field label={needsReason ? "Reason" : "Reason (optional)"} htmlFor="sa-reason">
                    <Input id="sa-reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
                </Field>
            )}
            <Field label="Reference (optional)" htmlFor="sa-reference" hint="An invoice, slip or requisition number.">
                <Input id="sa-reference" value={reference} maxLength={100} onChange={(e) => setReference(e.target.value)} />
            </Field>
        </FormDialog>
    );
}
