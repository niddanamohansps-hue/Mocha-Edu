"use client";

import { useState } from "react";
import { Input } from "@/components/ui/input";
import { Field, FormDialog, SELECT_CLASS } from "@/components/dashboard/transport/shared";
import { inventoryErrorMessage } from "@/hooks/useInventory";
import { useSaveDriver, useSaveVehicle } from "@/hooks/useTransport";
import { Driver, DriverRole, Vehicle } from "@/types/Transport";

// --- A vehicle -----------------------------------------------------------------------------------

export function VehicleDialog({ vehicle, onClose }: { vehicle: Vehicle | null | undefined; onClose: () => void }) {
    // undefined = closed, null = a new one
    return vehicle === undefined ? null : <VehicleForm key={vehicle?.id ?? "new"} vehicle={vehicle} onClose={onClose} />;
}

function VehicleForm({ vehicle, onClose }: { vehicle: Vehicle | null; onClose: () => void }) {
    const save = useSaveVehicle();
    const [registration, setRegistration] = useState(vehicle?.registration_number ?? "");
    const [name, setName] = useState(vehicle?.name ?? "");
    const [model, setModel] = useState(vehicle?.make_model ?? "");
    const [capacity, setCapacity] = useState(vehicle ? String(vehicle.capacity) : "");
    const [insurance, setInsurance] = useState(vehicle?.insurance_expiry ?? "");
    const [fitness, setFitness] = useState(vehicle?.fitness_expiry ?? "");
    const [notes, setNotes] = useState(vehicle?.notes ?? "");
    const [active, setActive] = useState(vehicle?.is_active ?? true);
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={vehicle ? "Edit vehicle" : "New vehicle"}
            submitLabel={vehicle ? "Save changes" : "Add vehicle"}
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                const seats = Number(capacity);
                if (!registration.trim()) return setError("Enter the registration number.");
                if (!Number.isInteger(seats) || seats < 1) return setError("Seats must be a whole number, 1 or more.");
                setError(null);
                save.mutate(
                    {
                        id: vehicle?.id,
                        input: {
                            registration_number: registration.trim(), name: name.trim(), make_model: model.trim(), capacity: seats,
                            insurance_expiry: insurance || null, fitness_expiry: fitness || null, notes: notes.trim(),
                            ...(vehicle ? { is_active: active } : {}),
                        },
                    },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save the vehicle")) }
                );
            }}
        >
            <Field label="Registration number" htmlFor="vh-reg"><Input id="vh-reg" value={registration} maxLength={30} onChange={(e) => setRegistration(e.target.value)} /></Field>
            <Field label="Seats for students" htmlFor="vh-cap"><Input id="vh-cap" inputMode="numeric" value={capacity} onChange={(e) => setCapacity(e.target.value)} /></Field>
            <Field label="Name (optional)" htmlFor="vh-name"><Input id="vh-name" value={name} maxLength={100} onChange={(e) => setName(e.target.value)} placeholder="e.g. Bus 3" /></Field>
            <Field label="Make and model (optional)" htmlFor="vh-model"><Input id="vh-model" value={model} maxLength={100} onChange={(e) => setModel(e.target.value)} /></Field>
            <Field label="Insurance expires" htmlFor="vh-ins"><Input id="vh-ins" type="date" value={insurance} onChange={(e) => setInsurance(e.target.value)} /></Field>
            <Field label="Fitness certificate expires" htmlFor="vh-fit"><Input id="vh-fit" type="date" value={fitness} onChange={(e) => setFitness(e.target.value)} /></Field>
            <Field label="Notes (optional)" htmlFor="vh-notes"><Input id="vh-notes" value={notes} maxLength={255} onChange={(e) => setNotes(e.target.value)} /></Field>
            {vehicle && (
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                    In service (switch off for a vehicle that is sold or retired)
                </label>
            )}
        </FormDialog>
    );
}

// --- A driver or helper --------------------------------------------------------------------------

export function DriverDialog({ driver, onClose }: { driver: Driver | null | undefined; onClose: () => void }) {
    return driver === undefined ? null : <DriverForm key={driver?.id ?? "new"} driver={driver} onClose={onClose} />;
}

function DriverForm({ driver, onClose }: { driver: Driver | null; onClose: () => void }) {
    const save = useSaveDriver();
    const [name, setName] = useState(driver?.full_name ?? "");
    const [role, setRole] = useState<DriverRole>(driver?.role ?? "driver");
    const [phone, setPhone] = useState(driver?.phone ?? "");
    const [licence, setLicence] = useState(driver?.license_number ?? "");
    const [expiry, setExpiry] = useState(driver?.license_expiry ?? "");
    const [notes, setNotes] = useState(driver?.notes ?? "");
    const [active, setActive] = useState(driver?.is_active ?? true);
    const [error, setError] = useState<string | null>(null);
    return (
        <FormDialog
            open
            onOpenChange={(open) => !open && onClose()}
            title={driver ? "Edit person" : "New driver or helper"}
            submitLabel={driver ? "Save changes" : "Add person"}
            pending={save.isPending}
            error={error}
            onSubmit={() => {
                if (!name.trim()) return setError("Enter the name.");
                setError(null);
                save.mutate(
                    {
                        id: driver?.id,
                        input: {
                            full_name: name.trim(), role, phone: phone.trim(), license_number: licence.trim(),
                            license_expiry: expiry || null, notes: notes.trim(), ...(driver ? { is_active: active } : {}),
                        },
                    },
                    { onSuccess: onClose, onError: (e) => setError(inventoryErrorMessage(e, "Could not save")) }
                );
            }}
        >
            <Field label="Full name" htmlFor="dr-name"><Input id="dr-name" value={name} maxLength={150} onChange={(e) => setName(e.target.value)} /></Field>
            <Field label="Works as" htmlFor="dr-role">
                <select id="dr-role" className={SELECT_CLASS} value={role} onChange={(e) => setRole(e.target.value as DriverRole)}>
                    <option value="driver">Driver</option>
                    <option value="helper">Helper</option>
                </select>
            </Field>
            <Field label="Phone (optional)" htmlFor="dr-phone"><Input id="dr-phone" inputMode="tel" value={phone} maxLength={30} onChange={(e) => setPhone(e.target.value)} /></Field>
            <Field label="Licence number (optional)" htmlFor="dr-lic"><Input id="dr-lic" value={licence} maxLength={50} onChange={(e) => setLicence(e.target.value)} /></Field>
            <Field label="Licence expires" htmlFor="dr-exp"><Input id="dr-exp" type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} /></Field>
            <Field label="Notes (optional)" htmlFor="dr-notes"><Input id="dr-notes" value={notes} maxLength={255} onChange={(e) => setNotes(e.target.value)} /></Field>
            {driver && (
                <label className="flex items-center gap-2 text-sm">
                    <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
                    Working (switch off for someone who has left)
                </label>
            )}
        </FormDialog>
    );
}
