"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Field, FormDialog, SELECT_CLASS, isNonNegativeDecimal } from "@/components/dashboard/inventory/shared";
import { inventoryErrorMessage, useAllOf, useAssetAction, useSaveAsset } from "@/hooks/useInventory";
import { useStaffMembers } from "@/hooks/useStaff";
import { usePermissions } from "@/providers/PermissionProvider";
import {
    ASSET_CONDITION_LABELS,
    Asset,
    AssetActionName,
    AssetCategory,
    AssetCondition,
    StockLocation,
    Supplier,
} from "@/types/Inventory";

const CONDITIONS = Object.keys(ASSET_CONDITION_LABELS) as AssetCondition[];

// --- Register / edit ---------------------------------------------------------------------------

export function AssetFormDialog({ asset, open, onClose }: { asset: Asset | null; open: boolean; onClose: () => void }) {
    return open ? <AssetForm key={asset?.id ?? "new"} asset={asset} onClose={onClose} /> : null;
}

function AssetForm({ asset, onClose }: { asset: Asset | null; onClose: () => void }) {
    const categories = useAllOf<AssetCategory>("asset-categories");
    const suppliers = useAllOf<Supplier>("suppliers", { is_active: "true" });
    const locations = useAllOf<StockLocation>("locations", { is_active: "true" });
    const save = useSaveAsset();
    const [tag, setTag] = useState(asset?.tag ?? "");
    const [name, setName] = useState(asset?.name ?? "");
    const [category, setCategory] = useState(asset?.category ?? "");
    const [serial, setSerial] = useState(asset?.serial_number ?? "");
    const [supplier, setSupplier] = useState(asset?.supplier ?? "");
    const [location, setLocation] = useState(asset?.location ?? "");
    const [purchaseDate, setPurchaseDate] = useState(asset?.purchase_date ?? "");
    const [cost, setCost] = useState(asset?.purchase_cost ?? "");
    const [condition, setCondition] = useState<AssetCondition>(asset?.condition ?? "good");
    const [description, setDescription] = useState(asset?.description ?? "");
    const [error, setError] = useState<string | null>(null);

    const submit = () => {
        if (!tag.trim() || !name.trim() || !category) return setError("Tag, name and category are required.");
        if (cost.trim() && !isNonNegativeDecimal(cost)) return setError("The purchase cost must be a number, 0 or more.");
        setError(null);
        save.mutate(
            {
                id: asset?.id,
                input: {
                    // The tag is fixed once registered, and the location only changes through "Move".
                    ...(asset ? {} : { tag: tag.trim(), location: location || null }),
                    name: name.trim(), category, serial_number: serial.trim(), description: description.trim(),
                    supplier: supplier || null, purchase_date: purchaseDate || null, purchase_cost: cost.trim() || null, condition,
                },
            },
            { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the asset")) }
        );
    };

    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={asset ? "Edit asset" : "Register asset"}
            description="Assets are durable items tracked one by one, such as computers, projectors and furniture."
            submitLabel={asset ? "Save changes" : "Register"}
            pending={save.isPending}
            error={error}
            onSubmit={submit}
            wide
        >
            <div className="grid sm:grid-cols-2 gap-3">
                <Field label="Asset tag" htmlFor="a-tag" hint={asset ? "The tag cannot be changed." : undefined}>
                    <Input id="a-tag" value={tag} disabled={!!asset} maxLength={50} onChange={(e) => setTag(e.target.value)} />
                </Field>
                <Field label="Name" htmlFor="a-name">
                    <Input id="a-name" value={name} maxLength={200} onChange={(e) => setName(e.target.value)} />
                </Field>
                <Field label="Category" htmlFor="a-category">
                    <select id="a-category" className={SELECT_CLASS} value={category} onChange={(e) => setCategory(e.target.value)}>
                        <option value="">Choose a category</option>
                        {(categories.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                    </select>
                </Field>
                <Field label="Serial number" htmlFor="a-serial">
                    <Input id="a-serial" value={serial} maxLength={100} onChange={(e) => setSerial(e.target.value)} />
                </Field>
                <Field label="Supplier" htmlFor="a-supplier">
                    <select id="a-supplier" className={SELECT_CLASS} value={supplier} onChange={(e) => setSupplier(e.target.value)}>
                        <option value="">None</option>
                        {(suppliers.data ?? []).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                </Field>
                {!asset && (
                    <Field label="Kept at" htmlFor="a-location">
                        <select id="a-location" className={SELECT_CLASS} value={location} onChange={(e) => setLocation(e.target.value)}>
                            <option value="">Not set</option>
                            {(locations.data ?? []).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                        </select>
                    </Field>
                )}
                <Field label="Purchase date" htmlFor="a-date">
                    <Input id="a-date" type="date" value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
                </Field>
                <Field label="Purchase cost" htmlFor="a-cost">
                    <Input id="a-cost" inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} />
                </Field>
                <Field label="Condition" htmlFor="a-condition">
                    <select id="a-condition" className={SELECT_CLASS} value={condition} onChange={(e) => setCondition(e.target.value as AssetCondition)}>
                        {CONDITIONS.map((c) => <option key={c} value={c}>{ASSET_CONDITION_LABELS[c]}</option>)}
                    </select>
                </Field>
            </div>
            <Field label="Description" htmlFor="a-description">
                <Textarea id="a-description" value={description} onChange={(e) => setDescription(e.target.value)} />
            </Field>
        </FormDialog>
    );
}

// --- Lifecycle actions -------------------------------------------------------------------------

export const ASSET_ACTION_LABELS: Record<AssetActionName, string> = {
    assign: "Assign",
    return: "Take back",
    move: "Move",
    repair: "Send to repair",
    "complete-repair": "Repair finished",
    lost: "Mark lost",
    found: "Mark found",
    dispose: "Dispose",
};

const ACTION_HELP: Partial<Record<AssetActionName, string>> = {
    dispose: "Disposal is final: the asset stays in the register but can never be used again.",
    lost: "A lost asset is taken off whoever held it. You can mark it found later.",
    repair: "Anyone holding the asset is relieved of it while it is in repair.",
};

export function AssetActionDialog({ asset, action, onClose }: { asset: Asset | null; action: AssetActionName | null; onClose: () => void }) {
    return asset && action ? <AssetActionForm key={`${asset.id}-${action}`} asset={asset} action={action} onClose={onClose} /> : null;
}

function StaffPicker({ value, onChange }: { value: string; onChange: (id: string) => void }) {
    const [search, setSearch] = useState("");
    const { data } = useStaffMembers({ pageSize: 50, search, isActive: true });
    const rows = data?.results ?? [];
    return (
        <div className="space-y-2">
            <Input aria-label="Search staff" placeholder="Search staff by name or ID" value={search} onChange={(e) => setSearch(e.target.value)} />
            <select id="aa-staff" className={SELECT_CLASS} value={value} onChange={(e) => onChange(e.target.value)}>
                <option value="">No staff member</option>
                {rows.map((s) => (
                    <option key={s.id} value={s.id}>
                        {s.profile_details.first_name} {s.profile_details.last_name} ({s.employee_id})
                    </option>
                ))}
            </select>
        </div>
    );
}

function AssetActionForm({ asset, action, onClose }: { asset: Asset; action: AssetActionName; onClose: () => void }) {
    const { can } = usePermissions();
    const locations = useAllOf<StockLocation>("locations", { is_active: "true" });
    const run = useAssetAction();
    const [staff, setStaff] = useState("");
    const [location, setLocation] = useState("");
    const [note, setNote] = useState("");
    const [reason, setReason] = useState("");
    const [cost, setCost] = useState("");
    const [condition, setCondition] = useState<AssetCondition | "">("");
    const [error, setError] = useState<string | null>(null);

    const needsReason = action === "repair" || action === "lost" || action === "dispose";
    const hasLocation = action === "assign" || action === "return" || action === "move" || action === "found";
    const hasCondition = action === "return" || action === "complete-repair";

    const submit = () => {
        if (action === "assign" && !staff && !location && !note.trim()) return setError("Say who or where the asset is assigned to.");
        if (action === "move" && !location) return setError("Choose a location.");
        if (needsReason && !reason.trim()) return setError("A reason is required.");
        if (action === "complete-repair" && cost.trim() && !isNonNegativeDecimal(cost)) return setError("The repair cost must be a number, 0 or more.");
        setError(null);
        const body: Record<string, unknown> = {};
        if (action === "assign") Object.assign(body, { staff: staff || null, location: location || null, note: note.trim() });
        if (action === "return" || action === "found") Object.assign(body, { location: location || null, note: note.trim() });
        if (action === "move") Object.assign(body, { location, note: note.trim() });
        if (needsReason) body.reason = reason.trim();
        if (action === "return" && condition) body.condition = condition;
        if (action === "complete-repair") Object.assign(body, { cost: cost.trim() || null, notes: note.trim(), ...(condition ? { condition } : {}) });
        run.mutate({ id: asset.id, action, body }, { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not update the asset")) });
    };

    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={`${ASSET_ACTION_LABELS[action]}: ${asset.name}`}
            description={ACTION_HELP[action] ?? `${asset.tag}`}
            submitLabel={ASSET_ACTION_LABELS[action]}
            pending={run.isPending}
            error={error}
            onSubmit={submit}
        >
            {action === "assign" && can("view_staff") && (
                <Field label="Staff member" htmlFor="aa-staff">
                    <StaffPicker value={staff} onChange={setStaff} />
                </Field>
            )}
            {hasLocation && (
                <Field label={action === "assign" ? "Place of use" : action === "move" ? "Move to" : "Now kept at"} htmlFor="aa-location">
                    <select id="aa-location" className={SELECT_CLASS} value={location} onChange={(e) => setLocation(e.target.value)}>
                        <option value="">{action === "move" ? "Choose a location" : "Not set / unchanged"}</option>
                        {(locations.data ?? []).map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
                    </select>
                </Field>
            )}
            {needsReason && (
                <Field label="Reason" htmlFor="aa-reason">
                    <Input id="aa-reason" value={reason} maxLength={255} onChange={(e) => setReason(e.target.value)} />
                </Field>
            )}
            {action === "complete-repair" && (
                <Field label="Repair cost (optional)" htmlFor="aa-cost">
                    <Input id="aa-cost" inputMode="decimal" value={cost} onChange={(e) => setCost(e.target.value)} />
                </Field>
            )}
            {hasCondition && (
                <Field label="Condition now" htmlFor="aa-condition">
                    <select id="aa-condition" className={SELECT_CLASS} value={condition} onChange={(e) => setCondition(e.target.value as AssetCondition | "")}>
                        <option value="">Unchanged ({ASSET_CONDITION_LABELS[asset.condition]})</option>
                        {CONDITIONS.map((c) => <option key={c} value={c}>{ASSET_CONDITION_LABELS[c]}</option>)}
                    </select>
                </Field>
            )}
            {action !== "repair" && action !== "lost" && action !== "dispose" && (
                <Field label={action === "assign" ? "Note (e.g. a class or club)" : "Note (optional)"} htmlFor="aa-note">
                    <Input id="aa-note" value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} />
                </Field>
            )}
        </FormDialog>
    );
}
