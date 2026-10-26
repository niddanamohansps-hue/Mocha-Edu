"use client";

import { CURRENCY } from "@/lib/currency";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { LoadingState } from "@/components/feedback/LoadingState";
import { Field, FormDialog, SELECT_CLASS, formatMoney, isNonNegativeDecimal } from "@/components/dashboard/transport/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useAllDrivers, useAllVehicles, useDeleteStop, useRouteStops, useSaveRoute, useSaveStop } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { Route, RouteStop } from "@/types/Transport";

// --- A route -------------------------------------------------------------------------------------

export function RouteDialog({ route, onClose }: { route: Route | null | undefined; onClose: () => void }) {
    // undefined = closed, null = a new one
    return route === undefined ? null : <RouteForm key={route?.id ?? "new"} route={route} onClose={onClose} />;
}

function RouteForm({ route, onClose }: { route: Route | null; onClose: () => void }) {
    const save = useSaveRoute();
    const vehicles = useAllVehicles();
    const people = useAllDrivers();
    const [name, setName] = useState(route?.name ?? "");
    const [vehicle, setVehicle] = useState(route?.vehicle ?? "");
    const [driver, setDriver] = useState(route?.driver ?? "");
    const [helper, setHelper] = useState(route?.helper ?? "");
    const [startPoint, setStartPoint] = useState(route?.start_point ?? "");
    const [endPoint, setEndPoint] = useState(route?.end_point ?? "");
    const [fee, setFee] = useState(route ? String(Number(route.monthly_fee)) : "0");
    const [notes, setNotes] = useState(route?.notes ?? "");
    const [active, setActive] = useState(route?.is_active ?? true);
    const [error, setError] = useState<string | null>(null);

    const everyone = people.data?.results ?? [];
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={route ? "Edit route" : "New route"}
            description="A route is one bus run. Stops are optional: add them after saving if fares or pick-up points differ along the route."
            submitLabel={route ? "Save changes" : "Add route"}
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                if (!name.trim()) return setError("Give the route a name.");
                if (!isNonNegativeDecimal(fee, 2)) return setError("The monthly fee must be a number, 0 or more.");
                setError(null);
                save.mutate(
                    {
                        id: route?.id,
                        input: {
                            name: name.trim(), vehicle: vehicle || null, driver: driver || null, helper: helper || null,
                            start_point: startPoint.trim(), end_point: endPoint.trim(), monthly_fee: fee.trim(),
                            notes: notes.trim(), ...(route ? { is_active: active } : {}),
                        },
                    },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the route")) }
                );
            }}
        >
            <Field label="Route name" htmlFor="rt-name"><Input id="rt-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder="e.g. Baneshwor morning" /></Field>
            <Field label="Bus" htmlFor="rt-vehicle" hint="Its seats are the most students this route can carry.">
                <select id="rt-vehicle" className={SELECT_CLASS} value={vehicle} onChange={(e) => setVehicle(e.target.value)}>
                    <option value="">No bus yet</option>
                    {(vehicles.data?.results ?? []).filter((v) => v.is_active || v.id === route?.vehicle).map((v) => (
                        <option key={v.id} value={v.id}>{v.registration_number} ({v.capacity} seats)</option>
                    ))}
                </select>
            </Field>
            <Field label="Driver" htmlFor="rt-driver">
                <select id="rt-driver" className={SELECT_CLASS} value={driver} onChange={(e) => setDriver(e.target.value)}>
                    <option value="">None yet</option>
                    {everyone.filter((p) => p.role === "driver" && (p.is_active || p.id === route?.driver)).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
            </Field>
            <Field label="Helper" htmlFor="rt-helper">
                <select id="rt-helper" className={SELECT_CLASS} value={helper} onChange={(e) => setHelper(e.target.value)}>
                    <option value="">None</option>
                    {everyone.filter((p) => p.role === "helper" && (p.is_active || p.id === route?.helper)).map((p) => <option key={p.id} value={p.id}>{p.full_name}</option>)}
                </select>
            </Field>
            <Field label={`Monthly fee (${CURRENCY})`} htmlFor="rt-fee" hint="What a student pays on this route. A stop can set its own fee to override this.">
                <Input id="rt-fee" inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} />
            </Field>
            <Field label="Starts at (optional)" htmlFor="rt-start" hint="Where the morning run begins, like a depot.">
                <Input id="rt-start" value={startPoint} maxLength={100} onChange={(e) => setStartPoint(e.target.value)} />
            </Field>
            <Field label="Ends at (optional)" htmlFor="rt-end" hint="Usually the school.">
                <Input id="rt-end" value={endPoint} maxLength={100} onChange={(e) => setEndPoint(e.target.value)} />
            </Field>
            <Field label="Notes (optional)" htmlFor="rt-notes"><Input id="rt-notes" value={notes} maxLength={255} onChange={(e) => setNotes(e.target.value)} /></Field>
            {route && (
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                    Running (switch off to stop new students joining)
                </label>
            )}
        </FormDialog>
    );
}

// --- The stops of one route ------------------------------------------------------------------------

export function StopsDialog({ route, onClose }: { route: Route | null; onClose: () => void }) {
    return (
        <Dialog open={!!route} onOpenChange={(open) => !open && onClose()}>
            <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                {route && <StopsBody route={route} />}
            </DialogContent>
        </Dialog>
    );
}

const time = (value: string | null) => (value ? value.slice(0, 5) : "");

function StopsBody({ route }: { route: Route }) {
    const { can } = usePermissions();
    const canEdit = can("manage_transport");
    const { data, isLoading } = useRouteStops(route.id);
    const save = useSaveStop();
    const remove = useDeleteStop();
    const stops = data ?? [];

    const [editing, setEditing] = useState<RouteStop | null>(null);
    const [name, setName] = useState("");
    const [sequence, setSequence] = useState("");
    const [pickup, setPickup] = useState("");
    const [drop, setDrop] = useState("");
    const [fee, setFee] = useState("");
    const [error, setError] = useState<string | null>(null);

    const reset = () => {
        setEditing(null); setName(""); setSequence(""); setPickup(""); setDrop(""); setFee(""); setError(null);
    };
    const edit = (stop: RouteStop) => {
        setEditing(stop); setName(stop.name); setSequence(String(stop.sequence)); setPickup(time(stop.pickup_time));
        setDrop(time(stop.drop_time)); setFee(stop.monthly_fee === null ? "" : String(Number(stop.monthly_fee))); setError(null);
    };

    const submit = () => {
        const order = sequence.trim() ? Number(sequence) : Math.max(0, ...stops.map((s) => s.sequence)) + 1;
        if (!name.trim()) return setError("Give the stop a name.");
        if (!Number.isInteger(order) || order < 1) return setError("The order must be a whole number, 1 or more.");
        if (fee.trim() && !isNonNegativeDecimal(fee, 2)) return setError("The monthly fee must be a number, 0 or more, or empty.");
        setError(null);
        save.mutate(
            {
                id: editing?.id,
                input: {
                    route: route.id, name: name.trim(), sequence: order,
                    pickup_time: pickup || null, drop_time: drop || null, monthly_fee: fee.trim() || null,
                },
            },
            { onSuccess: reset, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the stop")) }
        );
    };

    return (
        <div className="space-y-5">
            <DialogHeader>
                <DialogTitle>Stops on {route.name}</DialogTitle>
                <DialogDescription>In the order the bus visits them. A stop with its own fee overrides the route fee of {CURRENCY} {formatMoney(route.monthly_fee)}; one without uses the route fee.</DialogDescription>
            </DialogHeader>

            {isLoading ? (
                <LoadingState className="py-6" />
            ) : stops.length === 0 ? (
                <p className="text-sm text-slate-500">No stops. Students on this route all pay the route fee{canEdit ? "; add stops only if pick-up points or fares differ." : "."}</p>
            ) : (
                <ol className="divide-y divide-slate-100 dark:divide-slate-800 rounded-2xl border border-slate-200 dark:border-slate-800 text-sm">
                    {stops.map((s) => (
                        <li key={s.id} className="px-4 py-2 flex flex-wrap items-center gap-x-3 gap-y-1">
                            <span className="w-6 text-slate-400">{s.sequence}</span>
                            <span className="font-medium">{s.name}</span>
                            <span className="text-xs text-slate-500">
                                {time(s.pickup_time) || "-"} pick-up · {time(s.drop_time) || "-"} drop-off · {CURRENCY} {formatMoney(s.fee)}/month{s.monthly_fee === null ? " (route fee)" : ""} · {s.students} student{s.students === 1 ? "" : "s"}
                            </span>
                            {canEdit && (
                                <span className="ml-auto flex gap-1">
                                    <Button size="sm" variant="ghost" onClick={() => edit(s)}>Edit</Button>
                                    <Button size="sm" variant="ghost" className="text-red-600" disabled={remove.isPending} onClick={() => remove.mutate(s.id)}>Delete</Button>
                                </span>
                            )}
                        </li>
                    ))}
                </ol>
            )}

            {canEdit && (
                <form
                    className="rounded-2xl border border-slate-200 dark:border-slate-800 p-4 space-y-3"
                    onSubmit={(e) => { e.preventDefault(); submit(); }}
                >
                    <p className="text-sm font-medium">{editing ? `Change ${editing.name}` : "Add a stop"}</p>
                    <div className="grid sm:grid-cols-2 gap-3">
                        <Field label="Stop name" htmlFor="st-name"><Input id="st-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} /></Field>
                        <Field label="Order on the route" htmlFor="st-seq" hint="Leave empty to put it last.">
                            <Input id="st-seq" inputMode="numeric" value={sequence} onChange={(e) => setSequence(e.target.value)} />
                        </Field>
                        <Field label="Pick-up time" htmlFor="st-pick"><Input id="st-pick" type="time" value={pickup} onChange={(e) => setPickup(e.target.value)} /></Field>
                        <Field label="Drop-off time" htmlFor="st-drop"><Input id="st-drop" type="time" value={drop} onChange={(e) => setDrop(e.target.value)} /></Field>
                        <Field label={`Own monthly fee (${CURRENCY}, optional)`} htmlFor="st-fee" hint="Leave empty to use the route fee. 0 means no fee at this stop.">
                            <Input id="st-fee" inputMode="decimal" value={fee} onChange={(e) => setFee(e.target.value)} />
                        </Field>
                    </div>
                    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
                    <div className="flex gap-2">
                        <Button type="submit" size="sm" disabled={save.isPending}>{editing ? "Save stop" : "Add stop"}</Button>
                        {editing && <Button type="button" size="sm" variant="ghost" onClick={reset}>Cancel</Button>}
                    </div>
                </form>
            )}
        </div>
    );
}
