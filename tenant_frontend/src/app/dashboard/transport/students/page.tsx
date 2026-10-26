"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmationDialog } from "@/components/feedback/ConfirmationDialog";
import { ErrorState } from "@/components/feedback/ErrorState";
import { LoadingState } from "@/components/feedback/LoadingState";
import { ResponsiveList } from "@/components/common/ResponsiveList";
import { EmptyHint, FilterBar } from "@/components/common/PageLayout";
import { SeatDialog } from "@/components/dashboard/transport/SeatDialog";
import { FILTER_SELECT_CLASS, PageHeader, Pager, Pill, formatDate, formatMoney } from "@/components/dashboard/transport/shared";
import { useAllRoutes, useEndSeat, useSeats } from "@/hooks/useTransport";
import { usePermissions } from "@/providers/PermissionProvider";
import { SEAT_MODE_LABELS, Seat } from "@/types/Transport";

type OpenFilter = "" | "true" | "false";

export default function TransportStudentsPage() {
    const { can } = usePermissions();
    const canAssign = can("assign_transport");
    const [page, setPage] = useState(1);
    const [search, setSearch] = useState("");
    const [searchText, setSearchText] = useState("");
    const [route, setRoute] = useState("");
    const [open, setOpen] = useState<OpenFilter>("true");
    const { data, isLoading, isError, refetch } = useSeats({ page, search, route, open });
    const routes = useAllRoutes();
    const end = useEndSeat();
    const [giving, setGiving] = useState(false);
    const [moving, setMoving] = useState<Seat | null>(null);
    const [ending, setEnding] = useState<Seat | null>(null);

    if (!can("view_transport")) return <ErrorState message="You do not have permission to view transport." />;
    const rows = data?.results ?? [];

    return (
        <div className="space-y-6">
            <PageHeader
                title="Students on transport"
                description="Who uses which stop. Moving a student keeps their history."
                actions={canAssign && <Button onClick={() => setGiving(true)}>Give a seat</Button>}
            />
            <FilterBar onSubmit={() => { setPage(1); setSearch(searchText.trim()); }}>
                <Input type="text" placeholder="Search name or ID" aria-label="Search students" value={searchText} onChange={(e) => setSearchText(e.target.value)} />
                <select aria-label="Route" className={FILTER_SELECT_CLASS} value={route} onChange={(e) => { setPage(1); setRoute(e.target.value); }}>
                    <option value="">All routes</option>
                    {(routes.data?.results ?? []).map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
                </select>
                <select aria-label="Seat status" className={FILTER_SELECT_CLASS} value={open} onChange={(e) => { setPage(1); setOpen(e.target.value as OpenFilter); }}>
                    <option value="true">Using transport now</option>
                    <option value="false">Past seats</option>
                    <option value="">All</option>
                </select>
                <Button type="submit" variant="outline">Search</Button>
            </FilterBar>

            {isLoading ? (
                <LoadingState className="py-20" />
            ) : isError ? (
                <ErrorState message="Failed to load seats. Please try again." onRetry={refetch} />
            ) : rows.length === 0 ? (
                <EmptyHint
                    title={search || route ? "No one matches." : "No students on transport yet."}
                    hint={search || route ? "Try a different search or route." : "Give a seat to start. The route needs a bus and a stop first."}
                    action={!search && !route && canAssign ? <Button onClick={() => setGiving(true)}>Give the first seat</Button> : undefined}
                />
            ) : (
                <ResponsiveList
                    rows={rows}
                    rowKey={(r) => r.id}
                    columns={[
                        { key: "name", header: "Student", primary: true, cell: (r) => <>{r.student_name} <span className="text-xs font-normal text-slate-500">({r.enrollment_id})</span></> },
                        { key: "route", header: "Route", cell: (r) => r.route_name },
                        { key: "stop", header: "Stop", cell: (r) => r.stop_name || r.pickup_note || <span className="text-slate-400">-</span> },
                        { key: "mode", header: "Rides", hideOnMobile: true, className: "text-slate-500", cell: (r) => SEAT_MODE_LABELS[r.mode] },
                        { key: "fee", header: "Monthly fee", hideOnMobile: true, className: "font-bold", cell: (r) => formatMoney(r.monthly_fee) },
                        {
                            key: "when", header: "Period", hideOnMobile: true, className: "text-slate-500",
                            cell: (r) => (r.is_open ? <>from {formatDate(r.start_date)}</> : <>{formatDate(r.start_date)} to {formatDate(r.end_date)}</>),
                        },
                        { key: "state", header: "Status", cell: (r) => (r.is_open ? <Pill className="bg-emerald-100 text-emerald-700">Using</Pill> : <Pill className="bg-slate-200 text-slate-600">Ended</Pill>) },
                    ]}
                    actionsHeader="Actions"
                    actions={(r) =>
                        canAssign && r.is_open ? (
                            <div className="flex flex-wrap justify-end gap-1">
                                <Button size="sm" variant="outline" onClick={() => setMoving(r)}>Move</Button>
                                <Button size="sm" variant="ghost" className="text-red-600" onClick={() => setEnding(r)}>End</Button>
                            </div>
                        ) : null
                    }
                />
            )}
            <Pager data={data} page={page} onPage={setPage} />

            <SeatDialog open={giving} onClose={() => setGiving(false)} />
            <SeatDialog open={!!moving} onClose={() => setMoving(null)} student={moving ? { id: moving.student, name: moving.student_name } : undefined} />
            <ConfirmationDialog
                open={!!ending}
                onOpenChange={(o) => !o && setEnding(null)}
                title={`End ${ending?.student_name ?? ""}'s seat?`}
                description="The seat ends today and the place is freed. Fees already billed stay as they are."
                confirmLabel="End seat"
                isLoading={end.isPending}
                onConfirm={() => ending && end.mutate({ id: ending.id }, { onSettled: () => setEnding(null) })}
            />
        </div>
    );
}
