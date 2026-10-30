"use client";

import { useState, useMemo } from "react";
import {
    Bus,
    UserCheck,
    Plus,
    Search,
    X,
    Calendar,
    Phone,
    ShieldAlert,
    AlertTriangle,
    Pencil,
    Trash2,
    Users,
    CheckCircle2,
    FileCheck,
    Car,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { TableShell } from "@/components/common/table/TableShell";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { EmptyState } from "@/components/feedback/EmptyState";
import { DriverDialog, VehicleDialog } from "@/components/dashboard/transport/FleetDialogs";
import { expiryText, formatDate } from "@/components/dashboard/transport/shared";
import {
    useAllDrivers,
    useAllVehicles,
    useDeleteDriver,
    useDeleteVehicle,
    useExpiringDocuments,
} from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { Driver, Vehicle } from "@/types/Transport";

const WARN_DAYS = 30;

const AVATAR_PALETTES = [
    { bg: "bg-sky-100 dark:bg-sky-950/70", text: "text-sky-700 dark:text-sky-300", border: "border-sky-300/60 dark:border-sky-800" },
    { bg: "bg-emerald-100 dark:bg-emerald-950/70", text: "text-emerald-700 dark:text-emerald-300", border: "border-emerald-300/60 dark:border-emerald-800" },
    { bg: "bg-indigo-100 dark:bg-indigo-950/70", text: "text-indigo-700 dark:text-indigo-300", border: "border-indigo-300/60 dark:border-indigo-800" },
    { bg: "bg-purple-100 dark:bg-purple-950/70", text: "text-purple-700 dark:text-purple-300", border: "border-purple-300/60 dark:border-purple-800" },
    { bg: "bg-amber-100 dark:bg-amber-950/70", text: "text-amber-700 dark:text-amber-300", border: "border-amber-300/60 dark:border-amber-800" },
    { bg: "bg-rose-100 dark:bg-rose-950/70", text: "text-rose-700 dark:text-rose-300", border: "border-rose-300/60 dark:border-rose-800" },
    { bg: "bg-teal-100 dark:bg-teal-950/70", text: "text-teal-700 dark:text-teal-300", border: "border-teal-300/60 dark:border-teal-800" },
];

function getAvatarStyle(name?: string | null) {
    if (!name || typeof name !== "string") return AVATAR_PALETTES[0];
    let hash = 0;
    for (let i = 0; i < name.length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    const index = Math.abs(hash) % AVATAR_PALETTES.length;
    return AVATAR_PALETTES[index];
}

function getInitials(name: string) {
    if (!name) return "DR";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
}

export default function FleetPage() {
    const { can } = usePermissions();
    const canEdit = can("manage_transport");

    const vehiclesQuery = useAllVehicles();
    const peopleQuery = useAllDrivers();
    const expiringQuery = useExpiringDocuments(WARN_DAYS);

    const removeVehicle = useDeleteVehicle();
    const removePerson = useDeleteDriver();

    const [activeTab, setActiveTab] = useState<"vehicles" | "crew">("vehicles");
    const [vehicleSearch, setVehicleSearch] = useState("");
    const [crewSearch, setCrewSearch] = useState("");

    const [vehicle, setVehicle] = useState<Vehicle | null | undefined>(undefined);
    const [person, setPerson] = useState<Driver | null | undefined>(undefined);
    const [deletingVehicle, setDeletingVehicle] = useState<Vehicle | null>(null);
    const [deletingPerson, setDeletingPerson] = useState<Driver | null>(null);

    const vehicles = vehiclesQuery.data?.results ?? [];
    const crewMembers = peopleQuery.data?.results ?? [];
    const expiringDocs = expiringQuery.data ?? [];

    // Filter vehicles
    const filteredVehicles = useMemo(() => {
        if (!vehicleSearch.trim()) return vehicles;
        const q = vehicleSearch.toLowerCase();
        return vehicles.filter(
            (v) =>
                v.registration_number.toLowerCase().includes(q) ||
                (v.name && v.name.toLowerCase().includes(q)) ||
                (v.make_model && v.make_model.toLowerCase().includes(q))
        );
    }, [vehicles, vehicleSearch]);

    // Filter crew
    const filteredCrew = useMemo(() => {
        if (!crewSearch.trim()) return crewMembers;
        const q = crewSearch.toLowerCase();
        return crewMembers.filter(
            (c) =>
                c.full_name.toLowerCase().includes(q) ||
                (c.phone && c.phone.toLowerCase().includes(q)) ||
                (c.license_number && c.license_number.toLowerCase().includes(q))
        );
    }, [crewMembers, crewSearch]);

    // Metrics
    const metrics = useMemo(() => {
        const totalVehicles = vehicles.length;
        const activeVehicles = vehicles.filter((v) => v.is_active).length;
        const totalCapacity = vehicles.reduce((sum, v) => sum + (v.capacity || 0), 0);
        const driversCount = crewMembers.filter((c) => c.role === "driver" && c.is_active).length;
        const helpersCount = crewMembers.filter((c) => c.role === "helper" && c.is_active).length;
        return { totalVehicles, activeVehicles, totalCapacity, driversCount, helpersCount };
    }, [vehicles, crewMembers]);

    if (!can("view_transport")) {
        return <ErrorState message="You do not have permission to view transport." />;
    }

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Car className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Fleet Vehicles & Crew Desk</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Institutional bus fleet registry, licensed commercial drivers, in-transit helpers, and compliance certificate tracking
                    </p>
                </div>

                {canEdit && (
                    <div className="flex items-center gap-2 shrink-0">
                        <Button
                            onClick={() => setVehicle(null)}
                            size="sm"
                            className="h-9 px-3.5 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95"
                        >
                            <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                            <span>Add Bus Vehicle</span>
                        </Button>
                        <Button
                            onClick={() => setPerson(null)}
                            variant="outline"
                            size="sm"
                            className="h-9 px-3 gap-1.5 border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-200 text-xs font-semibold cursor-pointer shadow-2xs"
                        >
                            <Plus className="h-3.5 w-3.5 stroke-[2.5] text-slate-500" />
                            <span>Add Driver/Helper</span>
                        </Button>
                    </div>
                )}
            </div>

            {/* 2. Compliance Expiry Warning Banner (If Any Papers Expiring in 30 Days) */}
            {expiringDocs.length > 0 && (
                <div className="rounded-xl border border-amber-300 dark:border-amber-500/40 bg-amber-50/80 dark:bg-amber-950/30 p-4 space-y-2.5 shadow-2xs">
                    <div className="flex items-center gap-2 text-amber-900 dark:text-amber-300">
                        <ShieldAlert className="w-4 h-4 text-amber-600 dark:text-amber-400" />
                        <h3 className="text-xs font-bold uppercase tracking-wider">
                            Statutory Papers Expiring Soon ({expiringDocs.length} Documents)
                        </h3>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {expiringDocs.map((d) => {
                            const isOverdue = d.days_left < 0;
                            return (
                                <div
                                    key={`${d.kind}-${d.id}-${d.document}`}
                                    className="p-2.5 rounded-lg bg-white/90 dark:bg-slate-900/80 border border-amber-200/80 dark:border-amber-900/60 flex items-center justify-between text-xs"
                                >
                                    <div>
                                        <div className="font-semibold text-slate-900 dark:text-white">
                                            {d.subject}
                                        </div>
                                        <div className="text-[10px] text-slate-400 capitalize">
                                            {d.document}
                                        </div>
                                    </div>
                                    <Badge
                                        variant="outline"
                                        className={`text-[10px] font-bold ${
                                            isOverdue
                                                ? "border-rose-400 text-rose-700 bg-rose-50 dark:bg-rose-950/40"
                                                : "border-amber-400 text-amber-700 bg-amber-50 dark:bg-amber-950/40"
                                        }`}
                                    >
                                        {expiryText(d.days_left)}
                                    </Badge>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* 3. Executive Pulse Metrics Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Fleet */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Fleet</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Bus className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalVehicles}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            {metrics.activeVehicles} in service
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        School-owned and contracted buses
                    </p>
                </div>

                {/* Total Seating Capacity */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Passenger Capacity</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <Users className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.totalCapacity}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">certified seats</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Across active fleet buses
                    </p>
                </div>

                {/* Licensed Drivers */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Active Drivers</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <UserCheck className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.driversCount}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">on duty</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Commercial badge holders
                    </p>
                </div>

                {/* In-Transit Helpers */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">In-Bus Helpers</span>
                        <div className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                            <Users className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.helpersCount}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">attendants</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Student safety assistants
                    </p>
                </div>
            </div>

            {/* 4. Main Tabs: Vehicles vs Drivers & Helpers */}
            <Tabs value={activeTab} onValueChange={(v) => setActiveTab(v as any)} className="space-y-4">
                <div className="border-b border-slate-200 dark:border-slate-800">
                    <TabsList className="bg-transparent h-10 p-0 gap-6">
                        <TabsTrigger
                            value="vehicles"
                            className="h-10 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                        >
                            <Bus className="w-4 h-4" />
                            <span>Fleet Vehicles ({vehicles.length})</span>
                        </TabsTrigger>
                        <TabsTrigger
                            value="crew"
                            className="h-10 rounded-none border-b-2 border-transparent px-1 font-semibold text-xs text-slate-500 data-[state=active]:border-sky-600 data-[state=active]:text-sky-600 dark:data-[state=active]:text-sky-400 transition-all flex items-center gap-2 cursor-pointer"
                        >
                            <UserCheck className="w-4 h-4" />
                            <span>Drivers & Crew ({crewMembers.length})</span>
                        </TabsTrigger>
                    </TabsList>
                </div>

                {/* Tab 1: Vehicles */}
                <TabsContent value="vehicles" className="space-y-4 outline-none">
                    <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex items-center justify-between gap-3">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                            <Input
                                placeholder="Search vehicles by registration plate, bus name, or make..."
                                value={vehicleSearch}
                                onChange={(e) => setVehicleSearch(e.target.value)}
                                className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                            />
                            {vehicleSearch && (
                                <button
                                    onClick={() => setVehicleSearch("")}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600"
                                >
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            )}
                        </div>
                    </div>

                    {vehiclesQuery.isLoading ? (
                        <LoadingState className="py-12" />
                    ) : vehiclesQuery.isError ? (
                        <ErrorState message="Failed to load vehicles." onRetry={vehiclesQuery.refetch} />
                    ) : filteredVehicles.length === 0 ? (
                        <EmptyState
                            title={vehicleSearch ? "No vehicles matched your search" : "No fleet vehicles configured yet"}
                            description="Add school buses with passenger capacity and registration details to map transport routes."
                            action={
                                !vehicleSearch && canEdit ? (
                                    <Button
                                        onClick={() => setVehicle(null)}
                                        size="sm"
                                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                                    >
                                        <Plus className="h-3.5 w-3.5" />
                                        <span>Add First Vehicle</span>
                                    </Button>
                                ) : undefined
                            }
                        />
                    ) : (
                        <TableShell>
                            <Table>
                                <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                    <TableRow className="hover:bg-transparent">
                                        <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Registration Number
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Make & Model
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Seating Capacity
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Routes Assigned
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Statutory Expiries
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
                                    {filteredVehicles.map((v) => (
                                        <TableRow
                                            key={v.id}
                                            className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                        >
                                            {/* Registration */}
                                            <TableCell className="py-3.5 pl-4">
                                                <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 font-mono font-bold text-xs">
                                                    <Bus className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400" />
                                                    <span>{v.registration_number}</span>
                                                </div>
                                                {v.name && (
                                                    <div className="text-[11px] text-slate-500 font-medium mt-1">
                                                        {v.name}
                                                    </div>
                                                )}
                                            </TableCell>

                                            {/* Make & Model */}
                                            <TableCell className="py-3.5 text-xs text-slate-700 dark:text-slate-300">
                                                {v.make_model || "—"}
                                            </TableCell>

                                            {/* Capacity */}
                                            <TableCell className="py-3.5">
                                                <span className="text-xs font-bold text-slate-900 dark:text-white">
                                                    {v.capacity} Seats
                                                </span>
                                            </TableCell>

                                            {/* Routes */}
                                            <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-400">
                                                <span className="font-semibold text-slate-800 dark:text-slate-200">
                                                    {v.routes_count}
                                                </span>{" "}
                                                {v.routes_count === 1 ? "route" : "routes"}
                                            </TableCell>

                                            {/* Compliance Expiries */}
                                            <TableCell className="py-3.5">
                                                <div className="space-y-0.5 text-[11px]">
                                                    <div className="text-slate-500">
                                                        Insurance: <span className="font-medium text-slate-800 dark:text-slate-200">{formatDate(v.insurance_expiry)}</span>
                                                    </div>
                                                    <div className="text-slate-500">
                                                        Fitness: <span className="font-medium text-slate-800 dark:text-slate-200">{formatDate(v.fitness_expiry)}</span>
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Status */}
                                            <TableCell className="py-3.5">
                                                {v.is_active ? (
                                                    <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                                                        In Service
                                                    </Badge>
                                                ) : (
                                                    <Badge variant="outline" className="text-[11px] text-slate-400 border-slate-300">
                                                        Out of Service
                                                    </Badge>
                                                )}
                                            </TableCell>

                                            {/* Actions */}
                                            <TableCell className="py-3.5 pr-4 text-right">
                                                {canEdit && (
                                                    <div className="flex items-center justify-end gap-1">
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setVehicle(v)}
                                                            className="h-8 w-8 p-0 text-slate-500 hover:text-sky-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg cursor-pointer"
                                                            title="Edit vehicle"
                                                        >
                                                            <Pencil className="w-3.5 h-3.5" />
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setDeletingVehicle(v)}
                                                            className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg cursor-pointer"
                                                            title="Delete vehicle"
                                                        >
                                                            <Trash2 className="w-3.5 h-3.5" />
                                                        </Button>
                                                    </div>
                                                )}
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableShell>
                    )}
                </TabsContent>

                {/* Tab 2: Crew (Drivers & Helpers) */}
                <TabsContent value="crew" className="space-y-4 outline-none">
                    <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex items-center justify-between gap-3">
                        <div className="relative flex-1">
                            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                            <Input
                                placeholder="Search crew members by name, phone number, or license plate..."
                                value={crewSearch}
                                onChange={(e) => setCrewSearch(e.target.value)}
                                className="pl-9 pr-8 h-9 text-xs rounded-lg border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-950/50"
                            />
                            {crewSearch && (
                                <button
                                    onClick={() => setCrewSearch("")}
                                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded text-slate-400 hover:text-slate-600"
                                >
                                    <X className="h-3.5 w-3.5" />
                                </button>
                            )}
                        </div>
                    </div>

                    {peopleQuery.isLoading ? (
                        <LoadingState className="py-12" />
                    ) : peopleQuery.isError ? (
                        <ErrorState message="Failed to load crew members." onRetry={peopleQuery.refetch} />
                    ) : filteredCrew.length === 0 ? (
                        <EmptyState
                            title={crewSearch ? "No crew members matched your search" : "No transport crew registered yet"}
                            description="Add licensed drivers and helpers to operate bus routes and oversee student transit safety."
                            action={
                                !crewSearch && canEdit ? (
                                    <Button
                                        onClick={() => setPerson(null)}
                                        size="sm"
                                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                                    >
                                        <Plus className="h-3.5 w-3.5" />
                                        <span>Add First Crew Member</span>
                                    </Button>
                                ) : undefined
                            }
                        />
                    ) : (
                        <TableShell>
                            <Table>
                                <TableHeader className="bg-slate-50/80 dark:bg-slate-800/60 border-b border-slate-200/80 dark:border-slate-800">
                                    <TableRow className="hover:bg-transparent">
                                        <TableHead className="py-3.5 pl-4 text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Crew Member
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Role
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Phone Contact
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            Driving License
                                        </TableHead>
                                        <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                            License Expiry
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
                                    {filteredCrew.map((p) => {
                                        const avatarStyle = getAvatarStyle(p.full_name);
                                        const initials = getInitials(p.full_name);

                                        return (
                                            <TableRow
                                                key={p.id}
                                                className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                            >
                                                {/* Crew Member with Avatar */}
                                                <TableCell className="py-3.5 pl-4">
                                                    <div className="flex items-center gap-2.5">
                                                        <div
                                                            className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                        >
                                                            {initials}
                                                        </div>
                                                        <div>
                                                            <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                                {p.full_name}
                                                            </div>
                                                            {p.staff_name && (
                                                                <div className="text-[10px] text-slate-400">
                                                                    Linked: {p.staff_name}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                </TableCell>

                                                {/* Role */}
                                                <TableCell className="py-3.5">
                                                    {p.role === "driver" ? (
                                                        <Badge className="bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300 border border-sky-300/80 font-semibold text-[11px]">
                                                            Driver
                                                        </Badge>
                                                    ) : (
                                                        <Badge className="bg-purple-50 text-purple-700 dark:bg-purple-950/60 dark:text-purple-300 border border-purple-300/80 font-semibold text-[11px]">
                                                            In-Bus Helper
                                                        </Badge>
                                                    )}
                                                </TableCell>

                                                {/* Phone */}
                                                <TableCell className="py-3.5 text-xs text-slate-700 dark:text-slate-300">
                                                    {p.phone ? (
                                                        <a
                                                            href={`tel:${p.phone}`}
                                                            className="flex items-center gap-1.5 font-medium hover:text-sky-600 transition-colors"
                                                        >
                                                            <Phone className="w-3.5 h-3.5 text-slate-400" />
                                                            <span>{p.phone}</span>
                                                        </a>
                                                    ) : (
                                                        <span className="text-slate-400">—</span>
                                                    )}
                                                </TableCell>

                                                {/* License Number */}
                                                <TableCell className="py-3.5">
                                                    {p.license_number ? (
                                                        <code className="text-xs font-mono font-semibold text-slate-800 dark:text-slate-200 bg-slate-100 dark:bg-slate-800 px-1.5 py-0.5 rounded">
                                                            {p.license_number}
                                                        </code>
                                                    ) : (
                                                        <span className="text-xs text-slate-400">Not recorded</span>
                                                    )}
                                                </TableCell>

                                                {/* License Expiry */}
                                                <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-300">
                                                    {formatDate(p.license_expiry)}
                                                </TableCell>

                                                {/* Status */}
                                                <TableCell className="py-3.5">
                                                    {p.is_active ? (
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
                                                    {canEdit && (
                                                        <div className="flex items-center justify-end gap-1">
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={() => setPerson(p)}
                                                                className="h-8 w-8 p-0 text-slate-500 hover:text-sky-600 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg cursor-pointer"
                                                                title="Edit person"
                                                            >
                                                                <Pencil className="w-3.5 h-3.5" />
                                                            </Button>
                                                            <Button
                                                                size="sm"
                                                                variant="ghost"
                                                                onClick={() => setDeletingPerson(p)}
                                                                className="h-8 w-8 p-0 text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg cursor-pointer"
                                                                title="Delete person"
                                                            >
                                                                <Trash2 className="w-3.5 h-3.5" />
                                                            </Button>
                                                        </div>
                                                    )}
                                                </TableCell>
                                            </TableRow>
                                        );
                                    })}
                                </TableBody>
                            </Table>
                        </TableShell>
                    )}
                </TabsContent>
            </Tabs>

            {/* Modals & Dialogs */}
            <VehicleDialog vehicle={vehicle} onClose={() => setVehicle(undefined)} />
            <DriverDialog driver={person} onClose={() => setPerson(undefined)} />
            <ConfirmationDialog
                open={Boolean(deletingVehicle)}
                onOpenChange={(open) => !open && setDeletingVehicle(null)}
                title={`Delete Vehicle "${deletingVehicle?.registration_number}"?`}
                description="This will permanently delete the vehicle record. This only works if no route currently uses it. Otherwise, mark it as Out of Service."
                confirmLabel="Yes, Delete Vehicle"
                variant="destructive"
                isLoading={removeVehicle.isPending}
                onConfirm={() => deletingVehicle && removeVehicle.mutate(deletingVehicle.id, { onSettled: () => setDeletingVehicle(null) })}
            />
            <ConfirmationDialog
                open={Boolean(deletingPerson)}
                onOpenChange={(open) => !open && setDeletingPerson(null)}
                title={`Delete "${deletingPerson?.full_name}"?`}
                description="This only works if they are not assigned to any active route. Otherwise, mark them as Inactive."
                confirmLabel="Yes, Delete Crew Member"
                variant="destructive"
                isLoading={removePerson.isPending}
                onConfirm={() => deletingPerson && removePerson.mutate(deletingPerson.id, { onSettled: () => setDeletingPerson(null) })}
            />
        </div>
    );
}
