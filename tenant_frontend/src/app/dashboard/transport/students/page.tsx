"use client";

import { useState, useMemo } from "react";
import {
    Users,
    Plus,
    Search,
    X,
    MapPin,
    Calendar,
    Phone,
    Bus,
    ArrowRightLeft,
    Clock,
    CheckCircle2,
    RotateCcw,
    AlertCircle,
    UserX,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
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
import { SeatDialog } from "@/components/dashboard/transport/SeatDialog";
import { formatDate } from "@/components/dashboard/transport/shared";
import { useAllRoutes, useEndSeat, useSeats } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { SEAT_MODE_LABELS, Seat } from "@/types/Transport";
import { formatIndianCurrency } from "@/lib/currency";

const PAGE_SIZE = 20;
type OpenFilter = "" | "true" | "false";

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
    if (!name) return "ST";
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
        return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
    }
    return name.slice(0, 2).toUpperCase();
}

export default function TransportStudentsPage() {
    const { can } = usePermissions();
    const canAssign = can("assign_transport");

    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [route, setRoute] = useState("");
    const [open, setOpen] = useState<OpenFilter>("true");

    const { data, isLoading, isError, refetch } = useSeats({ page, search, route, open });
    const routesQuery = useAllRoutes();
    const end = useEndSeat();

    const [giving, setGiving] = useState(false);
    const [moving, setMoving] = useState<Seat | null>(null);
    const [ending, setEnding] = useState<Seat | null>(null);

    const seats = data?.results ?? [];
    const totalCount = data?.count ?? 0;
    const availableRoutes = routesQuery.data?.results ?? [];

    // Metrics
    const metrics = useMemo(() => {
        const activeSeats = seats.filter((s) => s.is_open).length;
        const bothWays = seats.filter((s) => s.mode === "both" && s.is_open).length;
        const oneWay = seats.filter((s) => s.mode !== "both" && s.is_open).length;
        return { totalCount, activeSeats, bothWays, oneWay };
    }, [seats, totalCount]);

    if (!can("view_transport")) {
        return <ErrorState message="You do not have permission to view transport." />;
    }

    return (
        <div className="space-y-6 pb-12 animate-in fade-in duration-300">
            {/* 1. Executive Header */}
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-slate-200/80 dark:border-slate-800">
                <div>
                    <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900 dark:text-white flex items-center gap-2.5">
                        <Users className="w-7 h-7 text-sky-600 dark:text-sky-400" />
                        <span>Student Transport Roster & Allocation</span>
                    </h1>
                    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
                        Active commuter passenger seats, assigned boarding stops, commute modes, and fee records
                    </p>
                </div>

                {canAssign && (
                    <Button
                        onClick={() => setGiving(true)}
                        size="sm"
                        className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg shadow-sm cursor-pointer transition active:scale-95 shrink-0"
                    >
                        <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                        <span>Allocate Bus Seat</span>
                    </Button>
                )}
            </div>

            {/* 2. Executive 4-Card Operational Pulse Strip */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3.5">
                {/* Total Allocations */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Total Roster Seats</span>
                        <div className="p-1.5 rounded-lg bg-sky-50 dark:bg-sky-950/60 text-sky-600 dark:text-sky-400">
                            <Users className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {totalCount}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">all-time records</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Active and concluded seats
                    </p>
                </div>

                {/* Active Commuters */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Active Riders</span>
                        <div className="p-1.5 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400">
                            <CheckCircle2 className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.activeSeats}
                        </span>
                        <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-semibold">
                            boarding daily
                        </span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Assigned to active school buses
                    </p>
                </div>

                {/* Both Ways Commuters */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Two-Way Commute</span>
                        <div className="p-1.5 rounded-lg bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400">
                            <ArrowRightLeft className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.bothWays}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">pick & drop</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Full round-trip transit
                    </p>
                </div>

                {/* One-Way Commuters */}
                <div className="p-4 rounded-xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 shadow-2xs">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Single Trip Only</span>
                        <div className="p-1.5 rounded-lg bg-purple-50 dark:bg-purple-950/60 text-purple-600 dark:text-purple-400">
                            <Clock className="w-4 h-4" />
                        </div>
                    </div>
                    <div className="mt-2 flex items-baseline gap-2">
                        <span className="text-2xl font-bold text-slate-900 dark:text-white">
                            {metrics.oneWay}
                        </span>
                        <span className="text-[11px] text-slate-400 font-medium">morning/evening</span>
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">
                        Single-leg transit riders
                    </p>
                </div>
            </div>

            {/* 3. High-Density Filter Bar */}
            <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 rounded-xl shadow-2xs flex flex-col md:flex-row items-center justify-between gap-2.5">
                {/* Search */}
                <div className="relative flex-1 w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                    <Input
                        placeholder="Search student by name or enrollment ID..."
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

                {/* Filters */}
                <div className="flex items-center gap-2 w-full md:w-auto shrink-0 justify-between sm:justify-start">
                    {/* Route Filter */}
                    <div className="w-44">
                        <Select
                            value={route || "all"}
                            onValueChange={(val) => {
                                setRoute(val === "all" ? "" : val);
                                setPage(1);
                            }}
                        >
                            <SelectTrigger className="h-9 text-xs rounded-lg bg-white dark:bg-slate-900 border-slate-200 dark:border-slate-800">
                                <SelectValue placeholder="All Routes" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="all" className="text-xs">All Bus Routes</SelectItem>
                                {availableRoutes.map((r) => (
                                    <SelectItem key={r.id} value={r.id} className="text-xs">
                                        {r.name}
                                    </SelectItem>
                                ))}
                            </SelectContent>
                        </Select>
                    </div>

                    {/* Status Funnel Pills */}
                    <div className="flex items-center gap-1 shrink-0">
                        {[
                            { value: "true", label: "Active Riders" },
                            { value: "false", label: "Past Seats" },
                            { value: "", label: "All" },
                        ].map((opt) => (
                            <button
                                key={opt.value}
                                type="button"
                                onClick={() => {
                                    setOpen(opt.value as OpenFilter);
                                    setPage(1);
                                }}
                                className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer ${
                                    open === opt.value
                                        ? "bg-slate-900 text-white dark:bg-white dark:text-slate-900 shadow-2xs"
                                        : "bg-white dark:bg-slate-900 text-slate-600 dark:text-slate-400 border border-slate-200/80 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800"
                                }`}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            {/* 4. Student Roster Table */}
            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load student transport seats. Please try again." onRetry={refetch} />
            ) : seats.length === 0 ? (
                <EmptyState
                    title={search || route ? "No matching students found" : "No students assigned to transport yet"}
                    description={
                        search || route
                            ? "Try adjusting your search criteria or selecting a different route."
                            : "Allocate bus seats to enrolled students to track designated pickup points and automated monthly transit billing."
                    }
                    action={
                        !search && !route && canAssign ? (
                            <Button
                                onClick={() => setGiving(true)}
                                size="sm"
                                className="h-9 px-4 gap-1.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg"
                            >
                                <Plus className="h-3.5 w-3.5 stroke-[2.5]" />
                                <span>Assign First Bus Seat</span>
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
                                        Student Passenger
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Assigned Route
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Designated Stop
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Commute Mode
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Monthly Fee
                                    </TableHead>
                                    <TableHead className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                                        Validity Period
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
                                {seats.map((s) => {
                                    const avatarStyle = getAvatarStyle(s.student_name);
                                    const initials = getInitials(s.student_name);

                                    return (
                                        <TableRow
                                            key={s.id}
                                            className="hover:bg-slate-50/60 dark:hover:bg-slate-800/40 border-b border-slate-100 dark:border-slate-800/70"
                                        >
                                            {/* Student Passenger */}
                                            <TableCell className="py-3.5 pl-4">
                                                <div className="flex items-center gap-2.5">
                                                    <div
                                                        className={`h-8 w-8 rounded-full flex items-center justify-center font-bold text-xs shrink-0 border ${avatarStyle.bg} ${avatarStyle.text} ${avatarStyle.border}`}
                                                    >
                                                        {initials}
                                                    </div>
                                                    <div>
                                                        <div className="font-semibold text-xs text-slate-900 dark:text-slate-100">
                                                            {s.student_name}
                                                        </div>
                                                        <code className="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-1 py-0.2 rounded">
                                                            {s.enrollment_id}
                                                        </code>
                                                    </div>
                                                </div>
                                            </TableCell>

                                            {/* Assigned Route */}
                                            <TableCell className="py-3.5">
                                                <div className="flex items-center gap-1.5 font-semibold text-xs text-slate-800 dark:text-slate-200">
                                                    <Bus className="w-3.5 h-3.5 text-sky-600 dark:text-sky-400 shrink-0" />
                                                    <span>{s.route_name}</span>
                                                </div>
                                            </TableCell>

                                            {/* Designated Stop */}
                                            <TableCell className="py-3.5">
                                                <div className="flex items-center gap-1 text-xs text-slate-700 dark:text-slate-300">
                                                    <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                                                    <span className="font-medium">
                                                        {s.stop_name || s.pickup_note || "Main Depot"}
                                                    </span>
                                                </div>
                                            </TableCell>

                                            {/* Commute Mode */}
                                            <TableCell className="py-3.5">
                                                <Badge
                                                    variant="outline"
                                                    className={`text-[11px] font-semibold ${
                                                        s.mode === "both"
                                                            ? "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-300"
                                                            : "bg-slate-50 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300"
                                                    }`}
                                                >
                                                    {SEAT_MODE_LABELS[s.mode]}
                                                </Badge>
                                            </TableCell>

                                            {/* Monthly Fee */}
                                            <TableCell className="py-3.5">
                                                <span className="text-xs font-bold text-slate-900 dark:text-white">
                                                    {formatIndianCurrency(s.monthly_fee)}
                                                </span>
                                            </TableCell>

                                            {/* Validity Period */}
                                            <TableCell className="py-3.5 text-xs text-slate-600 dark:text-slate-400">
                                                {s.is_open ? (
                                                    <span>from {formatDate(s.start_date)}</span>
                                                ) : (
                                                    <span>
                                                        {formatDate(s.start_date)} – {formatDate(s.end_date)}
                                                    </span>
                                                )}
                                            </TableCell>

                                            {/* Status */}
                                            <TableCell className="py-3.5">
                                                {s.is_open ? (
                                                    <Badge className="bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300/80 font-semibold text-[11px]">
                                                        Active Rider
                                                    </Badge>
                                                ) : (
                                                    <Badge variant="outline" className="text-[11px] text-slate-400 border-slate-300">
                                                        Ended
                                                    </Badge>
                                                )}
                                            </TableCell>

                                            {/* Actions */}
                                            <TableCell className="py-3.5 pr-4 text-right">
                                                {canAssign && s.is_open ? (
                                                    <div className="flex items-center justify-end gap-1.5">
                                                        <Button
                                                            size="sm"
                                                            variant="outline"
                                                            onClick={() => setMoving(s)}
                                                            className="h-8 px-2 text-xs font-semibold border-slate-200 dark:border-slate-800 text-slate-700 dark:text-slate-200 hover:text-sky-600 cursor-pointer"
                                                        >
                                                            <RotateCcw className="w-3 h-3 mr-1" />
                                                            <span>Move</span>
                                                        </Button>
                                                        <Button
                                                            size="sm"
                                                            variant="ghost"
                                                            onClick={() => setEnding(s)}
                                                            className="h-8 px-2 text-xs font-semibold text-rose-600 hover:text-rose-700 hover:bg-rose-50 dark:hover:bg-rose-950/40 rounded-lg cursor-pointer"
                                                        >
                                                            <UserX className="w-3.5 h-3.5 mr-1" />
                                                            <span>End Seat</span>
                                                        </Button>
                                                    </div>
                                                ) : (
                                                    <span className="text-xs text-slate-400 font-medium">
                                                        Closed
                                                    </span>
                                                )}
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

            {/* Modals & Dialogs */}
            <SeatDialog open={giving} onClose={() => setGiving(false)} />
            <SeatDialog
                open={Boolean(moving)}
                onClose={() => setMoving(null)}
                student={moving ? { id: moving.student, name: moving.student_name } : undefined}
            />
            <ConfirmationDialog
                open={Boolean(ending)}
                onOpenChange={(o) => !o && setEnding(null)}
                title={`End Bus Seat for ${ending?.student_name}?`}
                description="The seat assignment concludes effective immediately and frees up capacity on this bus. Prior billed transportation fees remain unchanged."
                confirmLabel="Yes, End Seat"
                variant="destructive"
                isLoading={end.isPending}
                onConfirm={() => ending && end.mutate({ id: ending.id }, { onSettled: () => setEnding(null) })}
            />
        </div>
    );
}
