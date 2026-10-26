"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { DriverDialog, VehicleDialog } from "@/components/dashboard/transport/FleetDialogs";
import { PageHeader, Pill, expiryText, formatDate } from "@/components/dashboard/transport/shared";
import { useAllDrivers, useAllVehicles, useDeleteDriver, useDeleteVehicle, useExpiringDocuments } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { Driver, Vehicle } from "@/types/Transport";

const WARN_DAYS = 30;

function ExpiryWarnings() {
    const { data } = useExpiringDocuments(WARN_DAYS);
    if (!data || data.length === 0) return null;
    return (
        <section className="rounded-2xl border border-amber-300 bg-amber-50 dark:bg-amber-500/10 dark:border-amber-500/30 p-4 space-y-2">
            <h2 className="font-semibold text-amber-900 dark:text-amber-300">Papers to renew</h2>
            <ul className="text-sm space-y-1">
                {data.map((d) => (
                    <li key={`${d.kind}-${d.id}-${d.document}`} className="flex flex-wrap gap-x-2">
                        <span className="font-medium">{d.subject}</span>
                        <span>{d.document}</span>
                        <span className={d.days_left < 0 ? "font-semibold text-red-700" : ""}>{expiryText(d.days_left)} ({formatDate(d.expiry)})</span>
                    </li>
                ))}
            </ul>
        </section>
    );
}

export default function FleetPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_transport");
    const vehicles = useAllVehicles();
    const people = useAllDrivers();
    const removeVehicle = useDeleteVehicle();
    const removePerson = useDeleteDriver();
    const [vehicle, setVehicle] = useState<Vehicle | null | undefined>(undefined);
    const [person, setPerson] = useState<Driver | null | undefined>(undefined);
    const [deletingVehicle, setDeletingVehicle] = useState<Vehicle | null>(null);
    const [deletingPerson, setDeletingPerson] = useState<Driver | null>(null);

    if (!can("view_transport")) return <ErrorState message="You do not have permission to view transport." />;

    return (
        <div className="space-y-6">
            <PageHeader title="Vehicles & drivers" description="The buses, and the people who drive them or help on board." />
            <ExpiryWarnings />

            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                <div className="flex items-center justify-between gap-3">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Vehicles</h2>
                    {canEdit && <Button size="sm" onClick={() => setVehicle(null)}>New vehicle</Button>}
                </div>
                {vehicles.isLoading ? <LoadingState className="py-6" /> : vehicles.isError ? (
                    <ErrorState message="Failed to load vehicles." onRetry={vehicles.refetch} />
                ) : (vehicles.data?.results ?? []).length === 0 ? (
                    <p className="text-sm text-slate-500">None yet.</p>
                ) : (
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                        {(vehicles.data?.results ?? []).map((v) => (
                            <li key={v.id} className="py-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                                <span className="font-medium">{v.registration_number}</span>
                                {v.name && <span className="text-slate-500">{v.name}</span>}
                                {!v.is_active && <Pill className="bg-slate-200 text-slate-600">Out of service</Pill>}
                                <span className="text-xs text-slate-500">{v.capacity} seats · {v.routes_count} route{v.routes_count === 1 ? "" : "s"}</span>
                                {canEdit && (
                                    <span className="ml-auto flex gap-1">
                                        <Button size="sm" variant="ghost" onClick={() => setVehicle(v)}>Edit</Button>
                                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeletingVehicle(v)}>Delete</Button>
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            <section className="rounded-2xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                <div className="flex items-center justify-between gap-3">
                    <h2 className="font-semibold text-slate-900 dark:text-white">Drivers & helpers</h2>
                    {canEdit && <Button size="sm" onClick={() => setPerson(null)}>New person</Button>}
                </div>
                {people.isLoading ? <LoadingState className="py-6" /> : people.isError ? (
                    <ErrorState message="Failed to load drivers." onRetry={people.refetch} />
                ) : (people.data?.results ?? []).length === 0 ? (
                    <p className="text-sm text-slate-500">None yet.</p>
                ) : (
                    <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                        {(people.data?.results ?? []).map((p) => (
                            <li key={p.id} className="py-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
                                <span className="font-medium">{p.full_name}</span>
                                <Pill className={p.role === "driver" ? "bg-sky-100 text-sky-700" : "bg-violet-100 text-violet-700"}>{p.role === "driver" ? "Driver" : "Helper"}</Pill>
                                {!p.is_active && <Pill className="bg-slate-200 text-slate-600">Left</Pill>}
                                <span className="text-xs text-slate-500">{p.phone || "no phone"}{p.license_expiry ? ` · licence to ${formatDate(p.license_expiry)}` : ""}</span>
                                {canEdit && (
                                    <span className="ml-auto flex gap-1">
                                        <Button size="sm" variant="ghost" onClick={() => setPerson(p)}>Edit</Button>
                                        <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeletingPerson(p)}>Delete</Button>
                                    </span>
                                )}
                            </li>
                        ))}
                    </ul>
                )}
            </section>

            <VehicleDialog vehicle={vehicle} onClose={() => setVehicle(undefined)} />
            <DriverDialog driver={person} onClose={() => setPerson(undefined)} />
            <ConfirmationDialog
                open={!!deletingVehicle}
                onOpenChange={(open) => !open && setDeletingVehicle(null)}
                title={`Delete ${deletingVehicle?.registration_number ?? ""}?`}
                description="This only works if no route uses it. Otherwise mark it out of service instead."
                confirmLabel="Delete"
                isLoading={removeVehicle.isPending}
                onConfirm={() => deletingVehicle && removeVehicle.mutate(deletingVehicle.id, { onSettled: () => setDeletingVehicle(null) })}
            />
            <ConfirmationDialog
                open={!!deletingPerson}
                onOpenChange={(open) => !open && setDeletingPerson(null)}
                title={`Delete ${deletingPerson?.full_name ?? ""}?`}
                description="This only works if they are on no route. Otherwise mark them as left instead."
                confirmLabel="Delete"
                isLoading={removePerson.isPending}
                onConfirm={() => deletingPerson && removePerson.mutate(deletingPerson.id, { onSettled: () => setDeletingPerson(null) })}
            />
        </div>
    );
}
