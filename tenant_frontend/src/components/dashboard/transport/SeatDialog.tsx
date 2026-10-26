"use client";

import { CURRENCY } from "@/lib/currency";
import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Field, FormDialog, SELECT_CLASS, formatMoney } from "@/components/dashboard/transport/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useStudents } from "@/hooks/useStudents";
import { useAllRoutes, useAssignSeat, useRouteStops } from "@/hooks/useTransport";
import { SEAT_MODE_LABELS, SeatMode } from "@/types/Transport";

/** `open` false = closed. With `student` the person is fixed (moving them); without it the form searches. */
export function SeatDialog({ open, onClose, student }: { open: boolean; onClose: () => void; student?: { id: string; name: string } }) {
    return open ? <SeatForm key={student?.id ?? "new"} onClose={onClose} student={student} /> : null;
}

function SeatForm({ onClose, student }: { onClose: () => void; student?: { id: string; name: string } }) {
    const assign = useAssignSeat();
    const routes = useAllRoutes();
    const [search, setSearch] = useState("");
    const { data: students } = useStudents({ pageSize: 50, search, status: "active" });
    const [person, setPerson] = useState(student?.id ?? "");
    const [route, setRoute] = useState("");
    const [stop, setStop] = useState("");
    const [mode, setMode] = useState<SeatMode>("both");
    const [note, setNote] = useState("");
    const [from, setFrom] = useState(() => new Date().toISOString().slice(0, 10));
    const [error, setError] = useState<string | null>(null);
    const stops = useRouteStops(route);

    const chosen = (routes.data?.results ?? []).find((r) => r.id === route);
    const hasStops = (stops.data ?? []).length > 0;
    const stopsReady = !!route && !stops.isLoading;

    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={student ? `Move ${student.name}` : "Give a seat"}
            description="A student who already has a seat is moved: the old seat ends the day before the new one starts."
            submitLabel={student ? "Move student" : "Give seat"}
            pending={assign.isPending}
            error={error}
            onSubmit={() => {
                if (!person) return setError("Choose the student.");
                if (!route) return setError("Choose the route.");
                if (!stopsReady) return setError("Wait a moment while the stops load.");
                if (hasStops && !stop) return setError("Choose the stop where the student gets on.");
                if (!from) return setError("Choose the date it starts.");
                setError(null);
                assign.mutate(
                    { student: person, route, stop: hasStops ? stop : null, start_date: from, mode, pickup_note: hasStops ? "" : note.trim() },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not give the seat")) }
                );
            }}
        >
            {!student && (
                <Field label="Student" htmlFor="seat-search">
                    <div className="space-y-2">
                        <Input id="seat-search" placeholder="Search by name or ID" value={search} onChange={(e) => setSearch(e.target.value)} />
                        <select aria-label="Student" className={SELECT_CLASS} value={person} onChange={(e) => setPerson(e.target.value)}>
                            <option value="">Choose a student</option>
                            {(students?.results ?? []).map((s) => (
                                <option key={s.id} value={s.id}>{s.full_name} ({s.enrollment_id})</option>
                            ))}
                        </select>
                    </div>
                </Field>
            )}
            <Field label="Route" htmlFor="seat-route" hint={chosen ? `${CURRENCY} ${formatMoney(chosen.monthly_fee)} a month unless the stop has its own fee.` : undefined}>
                <select id="seat-route" className={SELECT_CLASS} value={route} onChange={(e) => { setRoute(e.target.value); setStop(""); }}>
                    <option value="">Choose a route</option>
                    {(routes.data?.results ?? []).filter((r) => r.is_active).map((r) => (
                        <option key={r.id} value={r.id}>
                            {r.name} ({r.capacity === null ? "no bus" : `${r.seats_taken}/${r.capacity} seats`})
                        </option>
                    ))}
                </select>
            </Field>
            {stopsReady && hasStops && (
                <Field label="Stop" htmlFor="seat-stop" hint="Where the student gets on and off.">
                    <select id="seat-stop" className={SELECT_CLASS} value={stop} onChange={(e) => setStop(e.target.value)}>
                        <option value="">Choose a stop</option>
                        {(stops.data ?? []).map((s) => (
                            <option key={s.id} value={s.id}>{s.sequence}. {s.name} ({CURRENCY} {formatMoney(s.fee)}/month)</option>
                        ))}
                    </select>
                </Field>
            )}
            {stopsReady && !hasStops && (
                <Field label="Pick-up note (optional)" htmlFor="seat-note" hint="This route has no stops. Say where the student is picked up.">
                    <Input id="seat-note" value={note} maxLength={255} onChange={(e) => setNote(e.target.value)} placeholder="e.g. near the temple" />
                </Field>
            )}
            <Field label="Rides" htmlFor="seat-mode">
                <select id="seat-mode" className={SELECT_CLASS} value={mode} onChange={(e) => setMode(e.target.value as SeatMode)}>
                    {(Object.keys(SEAT_MODE_LABELS) as SeatMode[]).map((m) => <option key={m} value={m}>{SEAT_MODE_LABELS[m]}</option>)}
                </select>
            </Field>
            <Field label="Starts from" htmlFor="seat-from"><Input id="seat-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></Field>
        </FormDialog>
    );
}
