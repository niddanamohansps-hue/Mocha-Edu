"use client";

import { useState, useMemo } from "react";
import {
    Bus,
    Plus,
    Search,
    X,
    MapPin,
    Users,
    Compass,
    CheckCircle2,
    Clock,
    Phone,
    ShieldAlert,
    Pencil,
    Trash2,
    ArrowRight,
    Gauge,
    AlertCircle,
    UserCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { Pagination } from "@/components/ui/pagination";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { RouteDialog, StopsDialog } from "@/components/dashboard/transport/RouteDialogs";
import { useDeleteRoute, useRoutes } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { Route } from "@/types/Transport";
import { formatIndianCurrency } from "@/lib/currency";

const PAGE_SIZE = 20;

export default function TransportRoutesPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_transport");

    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");

    const { data, isLoading, isError, refetch } = useRoutes({ page, search });
    const remove = useDeleteRoute();

    const [editing, setEditing] = useState<Route | null | undefined>(undefined);
    const [stopsOf, setStopsOf] = useState<Route | null>(null);
    const [deleting, setDeleting] = useState<Route | null>(null);

    const routes = data?.results ?? [];
    const totalCount = data?.count ?? 0;

    // Filter routes based on status filter
    const filteredRoutes = useMemo(() => {
        if (statusFilter === "all") return routes;
        if (statusFilter === "active") return routes.filter((r) => r.is_active);
        return routes.filter((r) => !r.is_active);
    }, [routes, statusFilter]);

    // Aggregate metrics
    const metrics = useMemo(() => {
        const total = routes.length;
        const active = routes.filter((r) => r.is_active).length;
        const totalSeats = routes.reduce((acc, r) => acc + (r.capacity || 0), 0);
        const occupiedSeats = routes.reduce((acc, r) => acc + (r.seats_taken || 0), 0);
        const totalStops = routes.reduce((acc, r) => acc + (r.stops_count || 0), 0);
        const occupancyRate = totalSeats > 0 ? Math.round((occupiedSeats / totalSeats) * 100) : 0;
        return { total, active, totalSeats, occupiedSeats, totalStops, occupancyRate };
    }, [routes]);

    if (!can("view_transport")) {
        return <ErrorState message="You do not have permission to view transport." />;
    }

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Bus className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Transport Fleet & Routes Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Live vehicle routing, stop scheduling, passenger seating capacities, and transport fee policies
                    </p>
                </div>

                {canEdit && (
                    <Button
                        onClick={() => setEditing(null)}
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Add New Route</span>
                    </Button>
                )}
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Routes */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Routes</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Compass className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.total}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            {metrics.active} active
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Across {metrics.totalStops} scheduled stops
                    </p>
                </div>

                {/* Fleet Capacity */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Capacity</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Bus className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalSeats}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">passenger seats</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Active registered fleet buses
                    </p>
                </div>

                {/* Occupied Seats */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Assigned Riders</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <Users className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.occupiedSeats}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">students on board</span>
                    </div>
                    <div className="mt-1.5 flex items-center gap-2">
                        <div className="h-1.5 flex-1 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                                style={{ width: `${Math.min(metrics.occupancyRate, 100)}%` }}
                            />
                        </div>
                        <span className="text-[10px] font-bold text-slate-600 dark:text-slate-300">
                            {metrics.occupancyRate}%
                        </span>
                    </div>
                </div>

                {/* Seat Availability */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Vacant Seats</span>
                        <div className="p-1.5 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400">
                            <Gauge className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {Math.max(0, metrics.totalSeats - metrics.occupiedSeats)}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">seats remaining</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Available for fresh student enrollment
                    </p>
                </div>
            </div>

            {/* 3. Search and Status Funnel Controls */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col sm:flex-row items-center justify-between gap-3">
                {/* Search */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search routes by name, bus number, or driver..."
                        value={search}
                        onChange={(e) => {
                            setSearch(e.target.value);
                            setPage(1);
                        }}
                        className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50 focus:border-sky-500 focus:ring-1 focus:ring-sky-500/20"
                    />
                    {search && (
                        <button
                            onClick={() => {
                                setSearch("");
                                setPage(1);
                            }}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600 cursor-pointer"
                        >
                            <X className="h-3.5 w-3.5" />
                        </button>
                    )}
                </div>

                {/* Status Segmented Buttons */}
                <div className="flex items-center gap-1.5 self-start sm:self-auto shrink-0">
                    {(["all", "active", "inactive"] as const).map((s) => (
                        <button
                            key={s}
                            type="button"
                            onClick={() => setStatusFilter(s)}
                            className={`px-3 py-1.5 rounded-lg text-xs font-semibold capitalize transition-all cursor-pointer ${
                                statusFilter === s
                                    ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                    : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                            }`}
                        >
                            {s === "all" ? "All Routes" : s}
                        </button>
                    ))}
                </div>
            </div>

            {/* 4. Routes Table */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load routes. Please try again." onRetry={refetch} />
            ) : filteredRoutes.length === 0 ? (
                <EmptyState
                    title={search ? "No routes matched your query" : "No transport routes configured yet"}
                    description={
                        search
                            ? "Try adjusting your search terms or clearing your filters."
                            : "Set up bus routes, assign vehicles and drivers, and map out stops to begin allocating seats to students."
                    }
                    action={
                        !search && canEdit ? (
                            <Button
                                onClick={() => setEditing(null)}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Create First Route</span>
                            </Button>
                        ) : undefined
                    }
                />
            ) : (
                <div className="space-y-4">
                    <TableShell>
                        <Table>
                            <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                <TableRow className="hover:bg-transparent">
                                    <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Route & Waypoints
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Vehicle Assigned
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Crew Assigned
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Stops
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Capacity & Utilization
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Monthly Fare
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Status
                                    </TableHead>
                                    <TableHead className="text-right pr-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Actions
                                    </TableHead>
                                </TableRow>
                            </TableHeader>
                            <TableBody>
                                {filteredRoutes.map((r) => {
                                    const capacity = r.capacity || 0;
                                    const seatsTaken = r.seats_taken || 0;
                                    const occupancy = capacity > 0 ? Math.round((seatsTaken / capacity) * 100) : 0;
                                    const isFull = capacity > 0 && seatsTaken >= capacity;

                                    return (
                                        <TableRow
                                            key={r.id}
                                            className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                        >
                                            {/* Route & Waypoints */}
                                            <TableCell className="py-3.5 pl-4">
                                                <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                    {r.name}
                                                </div>
                                                {(r.start_point || r.end_point) ? (
                                                    <div className="text-[11px] text-slate-400 flex items-center gap-1.5 mt-1">
                                                        <span>{r.start_point || "Depot"}</span>
                                                        <ArrowRight className="w-3 h-3 text-slate-400 shrink-0" />
                                                        <span>{r.end_point || "Campus"}</span>
                                                    </div>
                                                ) : (
                                                    <div className="text-[10px] text-slate-400 mt-0.5">
                                                        Campus Transit Run
                                                    </div>
                                                )}
                                            </TableCell>

                                            {/* Vehicle */}
                                            <TableCell className="py-3.5">
                                                {r.vehicle_registration ? (
                                                    <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 text-xs font-mono font-semibold">
                                                        <Bus className="w-3 h-3 text-sky-600 dark:text-sky-400" />
                                                        <span>{r.vehicle_registration}</span>
                                                    </div>
                                                ) : (
                                                    <span className="text-xs text-amber-600 dark:text-amber-400 flex items-center gap-1 font-medium">
                                                        <AlertCircle className="w-3 h-3" />
                                                        <span>No bus assigned</span>
                                                    </span>
                                                )}
                                            </TableCell>

                                            {/* Crew */}
                                            <TableCell className="py-3.5">
                                                <div className="space-y-0.5">
                                                    <div className="text-xs font-medium text-slate-800 dark:text-slate-200 flex items-center gap-1.5">
                                                        <UserCheck className="w-3 h-3 text-slate-400" />
                                                        <span>{r.driver_name || "Driver unassigned"}</span>
                                                    </div>
                                                    {r.helper_name && (
                                                        <div className="text-[11px] text-slate-400 pl-4.5">
                                                            Helper: {r.helper_name}
                                                        </div>
                                                    )}
                                                </div>
                                            </TableCell>

                                            {/* Stops Count */}
                                            <TableCell className="py-3.5">
                                                <button
                                                    onClick={() => setStopsOf(r)}
                                                    className="inline-flex items-center gap-1 text-xs font-semibold text-sky-600 dark:text-sky-400 hover:underline cursor-pointer"
                                                >
                                                    <MapPin className="w-3.5 h-3.5 text-sky-500" />
                                                    <span>{r.stops_count} {r.stops_count === 1 ? "Stop" : "Stops"}</span>
                                                </button>
                                            </TableCell>

                                            {/* Capacity & Utilization */}
                                            <TableCell className="py-3.5">
                                                <div className="space-y-1.5 w-32">
                                                    <div className="flex items-center justify-between text-xs">
                                                        <span className="font-bold text-slate-800 dark:text-slate-200">
                                                            {seatsTaken} / {capacity || "—"}
                                                        </span>
                                                        <span
                                                            className={`text-[10px] font-bold ${
                                                                isFull
                                                                    ? "text-rose-600 dark:text-rose-400"
                                                                    : occupancy > 80
                                                                    ? "text-amber-600 dark:text-amber-400"
                                                                    : "text-emerald-600 dark:text-emerald-400"
                                                            }`}
                                                        >
                                                            {occupancy}%
                                                        </span>
                                                    </div>
                                                    <div className="h-1.5 w-full bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                                                        <div
                                                            className={`h-full rounded-full transition-all duration-300 ${
                                                                isFull
                                                                    ? "bg-rose-500"
                                                                    : occupancy > 80
                                                                    ? "bg-amber-500"
                                                                    : "bg-emerald-500"
                                                            }`}
                                                            style={{ width: `${Math.min(occupancy, 100)}%` }}
                                                        />
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Monthly Fare */}
                                            <TableCell className="py-3.5">
                                                <span className="text-xs font-bold text-slate-900 dark:text-white">
                                                    {formatIndianCurrency(r.monthly_fee)}
                                                </span>
                                                <span className="text-[10px] text-slate-400 block font-normal">
                                                    per month
                                                </span>
                                            </TableCell>

                                            {/* Status */}
                                            <TableCell className="py-3.5">
                                                {r.is_active ? (
                                                    <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                                                        Active
                                                    </Badge>
                                                ) : (
                                                    <Badge variant="outline" className="text-[11px] text-slate-400 border-slate-300">
                                                        Inactive
                                                    </Badge>
                                                )}
                                            </TableCell>

                                            {/* Actions */}
                                            <TableCell className="py-3.5 pr-4 text-right">
                                                <div className="flex items-center justify-end gap-1">
                                                    <Button
                                                        size="sm"
                                                        variant="outline"
                                                        onClick={() => setStopsOf(r)}
                                                        className="h-8 px-2.5 text-xs font-semibold border-slate-200 dark:border-slate-800 hover:text-sky-600 cursor-pointer"
                                                    >
                                                        <MapPin className="w-3.5 h-3.5 mr-1 text-slate-400" />
                                                        <span>Stops</span>
                                                    </Button>
                                                    {canEdit && (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setEditing(r)}
                                                            className="h-8 w-8 p-0 text-slate-500 hover:text-sky-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg cursor-pointer"
                                                            title="Edit route"
                                                        >
                                                            <Pencil className="w-3.5 h-3.5" />
                                                        </Button>
                                                    )}
                                                    {canEdit && (
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setDeleting(r)}
                                                            className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg cursor-pointer"
                                                            title="Delete route"
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </Button>
                                                    )}
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    );
                                })}
                            </TableBody>
                        </Table>
                    </TableShell>

                    {/* Pagination */}
                    {totalCount > PAGE_SIZE && (
                        <div className="pt-2">
                            <Pagination
                                page={page}
                                pageSize={PAGE_SIZE}
                                count={totalCount}
                                onPageChange={setPage}
                            />
                        </div>
                    )}
                </div>
            )}

            {/* Dialogs */}
            <RouteDialog route={editing} onClose={() => setEditing(undefined)} />
            <StopsDialog route={stopsOf} onClose={() => setStopsOf(null)} />
            <ConfirmationDialog
                open={Boolean(deleting)}
                onOpenChange={(open) => !open && setDeleting(null)}
                title={`Delete Route "${deleting?.name}"?`}
                description="This route will be permanently removed. This action only succeeds if no student has ever used this route. Otherwise, switch it to Inactive."
                confirmLabel="Yes, Delete Route"
                variant="destructive"
                isLoading={remove.isPending}
                onConfirm={() => deleting && remove.mutate(deleting.id, { onSettled: () => setDeleting(null) })}
            />
        </div>
    );
}
