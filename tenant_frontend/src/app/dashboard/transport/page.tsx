"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { RouteDialog, StopsDialog } from "@/components/dashboard/transport/RouteDialogs";
import { PageHeader, Pager, Pill, formatMoney } from "@/components/dashboard/transport/shared";
import { useDeleteRoute, useRoutes } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { Route } from "@/types/Transport";

export default function TransportRoutesPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_transport");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const { data, isLoading, isError, refetch } = useRoutes({ page, search });
    const remove = useDeleteRoute();
    const [editing, setEditing] = useState<Route | null | undefined>(undefined);
    const [stopsOf, setStopsOf] = useState<Route | null>(null);
    const [deleting, setDeleting] = useState<Route | null>(null);

    if (!can("view_transport")) return <ErrorState message="You do not have permission to view transport." />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Routes"
                description="Each route is one bus run with its stops. Add vehicles and drivers first, then build the routes."
                actions={canEdit && <Button onClick={() => setEditing(null)}>New route</Button>}
            />
            <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                <Input type="text" placeholder="Search routes" aria-label="Search routes" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load routes. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={search ? "No route matches your search." : "No routes yet."}
                    hint={search ? "Try a different word." : "A route needs a bus and stops before students can be given seats."}
                    action={!search && canEdit ? <Button onClick={() => setEditing(null)}>Add the first route</Button> : undefined}
                />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        {
                            key: "name", header: "Route", primary: true,
                            cell: (r) => <>{r.name} {!r.is_active && <Pill className="ml-1 bg-slate-200 text-slate-600">Off</Pill>}</>,
                        },
                        { key: "bus", header: "Bus", cell: (r) => r.vehicle_registration || <span className="text-amber-600">No bus</span> },
                        { key: "driver", header: "Driver", hideOnMobile: true, className: "text-slate-500", cell: (r) => r.driver_name || "-" },
                        { key: "stops", header: "Stops", hideOnMobile: true, className: "text-slate-500", cell: (r) => (r.stops_count === 0 ? "none" : r.stops_count) },
                        { key: "fee", header: "Monthly fee", hideOnMobile: true, className: "text-slate-500", cell: (r) => formatMoney(r.monthly_fee) },
                        {
                            key: "seats", header: "Seats used", className: "font-bold",
                            cell: (r) => (r.capacity === null ? `${r.seats_taken}` : `${r.seats_taken} / ${r.capacity}`),
                        },
                    ]}
                    actionsHeader="Actions"
                    actions={(r) => (
                        <div className="flex flex-wrap justify-end gap-1">
                            <Button size="sm" variant="outline" onClick={() => setStopsOf(r)}>Stops</Button>
                            {canEdit && <Button size="sm" variant="ghost" onClick={() => setEditing(r)}>Edit</Button>}
                            {canEdit && <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setDeleting(r)}>Delete</Button>}
                        </div>
                    )}
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />

            <RouteDialog route={editing} onClose={() => setEditing(undefined)} />
            <StopsDialog route={stopsOf} onClose={() => setStopsOf(null)} />
            <ConfirmationDialog
                open={!!deleting}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Delete ${deleting?.name ?? ""}?`}
                description="This only works if no student has ever used the route. Otherwise switch it off instead."
                confirmLabel="Delete"
                isLoading={remove.isPending}
                onConfirm={() => deleting && remove.mutate(deleting.id, { onSettled: () => setDeleting(null) })}
            />
        </div>
    );
}
